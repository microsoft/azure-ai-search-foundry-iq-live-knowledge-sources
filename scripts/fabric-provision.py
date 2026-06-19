#!/usr/bin/env python3
"""Provision the Microsoft Fabric side of the live Knowledge Sources sample.

The script intentionally writes only non-secret outputs under deployments/<env>/.
It can run standalone for Fabric validation or as the full-mode pre-step before
Azure AI Search postprovision creates the Fabric Ontology Knowledge Source.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "samples" / "data" / "airline-ops"
DEPLOYMENTS_DIR = REPO_ROOT / "deployments"
FABRIC_API = "https://api.fabric.microsoft.com/v1"
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
STORAGE_RESOURCE = "https://storage.azure.com"
FABRIC_CAPACITY_API_VERSION = "2023-11-01"
GRAPH_DATA_SOURCES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/graphInstance/definition/dataSources/1.0.0/schema.json"
GRAPH_DEFINITION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/graphInstance/definition/graphDefinition/1.0.0/schema.json"
GRAPH_TYPE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/graphInstance/definition/graphType/1.0.0/schema.json"
GRAPH_STYLING_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/graphInstance/definition/stylingConfiguration/1.0.0/schema.json"
TRANSIENT_HTTP_STATUS_CODES = {429, 503}
TRANSIENT_RETRY_DELAYS_SECONDS = (2, 4, 8)
FABRIC_CAPACITY_LIST_ATTEMPTS = 72
FABRIC_GRAPH_PROBE_ATTEMPTS = 60
FABRIC_GRAPH_SECOND_PROBE_ATTEMPTS = 45
FABRIC_GRAPH_PROBE_DELAY_SECONDS = 20

ENTITY_SPECS = [
    ("Airline", "airlines.csv", "airline_code"),
    ("Airport", "airports.csv", "airport_code"),
    ("Route", "routes.csv", "route_id"),
    ("Flight", "flights.csv", "flight_id"),
    ("DelayEvent", "delay_events.csv", "delay_event_id"),
    ("PassengerCarePolicy", "passenger_care_policies.csv", "policy_id"),
    ("RegulatoryReference", "regulatory_references.csv", "reference_id"),
]

# Relationship contextualization binds each side to entity key properties through
# a Lakehouse table. Policy/regulation joins stay in the Search-index semantic
# join path because they are condition-based, not row-level key relationships.
RELATIONSHIP_SPECS = [
    ("AirlineOperatesFlight", "Airline", "Flight", "flights", "airline_code", "flight_id"),
    ("RouteHasOriginAirport", "Route", "Airport", "routes", "route_id", "origin_airport_code"),
    ("RouteHasDestinationAirport", "Route", "Airport", "routes", "route_id", "destination_airport_code"),
    ("FlightUsesRoute", "Flight", "Route", "flights", "flight_id", "route_id"),
    ("FlightHasDelayEvent", "Flight", "DelayEvent", "delay_events", "flight_id", "delay_event_id"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision Fabric capacity/workspace/lakehouse/ontology for the sample.")
    parser.add_argument("--dry-run", action="store_true", help="Validate settings and generated definition without Azure/Fabric calls.")
    parser.add_argument("--env-name", help="Deployment environment name. Defaults to azd env or AZURE_ENV_NAME.")
    parser.add_argument("--fabric-location", help="Fabric capacity region override, for example westus3.")
    parser.add_argument("--capacity-mode", choices=["create", "byo", "skip"], help="Override FABRIC_CAPACITY_MODE.")
    return parser.parse_args()


def run(command: list[str], *, allow_failure: bool = False) -> str:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 and not allow_failure:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}")
    return completed.stdout.strip()


def load_azd_env() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        output = run(["azd", "env", "get-values"], allow_failure=True)
    except FileNotFoundError:
        return values
    for raw_line in output.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def get_setting(name: str, azd_values: dict[str, str], default: str = "") -> str:
    return os.environ.get(name) or azd_values.get(name) or default


def azd_set(name: str, value: str, *, dry_run: bool) -> None:
    if not value:
        return
    if dry_run:
        print(f"[dry-run] azd env set {name}=<non-secret>")
        return
    run(["azd", "env", "set", name, value])


def sanitize_capacity_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", value.lower())
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"fab{cleaned}"
    return cleaned[:63]


def sanitize_display_suffix(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:48] or "dev"


def deterministic_int_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    number = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return str(number or 1)


def deterministic_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "foundry-iq-live-ks|" + "|".join(parts)))


def b64_json(value: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).decode("ascii")


def get_token(resource: str) -> str:
    return run(["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"])


def request_json(
    *,
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | bytes | None = None,
    expected: tuple[int, ...] = (200, 201, 202),
    extra_headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> tuple[int, dict[str, str], dict[str, Any] | None]:
    headers = {"Authorization": f"Bearer {token}"}
    data: bytes | None = None
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif isinstance(body, bytes):
        data = body
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_error: urllib.error.HTTPError | None = None
    retry_delays = (*TRANSIENT_RETRY_DELAYS_SECONDS, None)

    for retry_delay in retry_delays:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
                parsed = json.loads(payload) if payload else None
                if response.status not in expected:
                    raise RuntimeError(f"{method} {url} returned {response.status}: {payload}")
                return response.status, dict(response.headers), parsed
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code in TRANSIENT_HTTP_STATUS_CODES and retry_delay is not None:
                retry_after = error.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else retry_delay
                print(f"[warn] {method} {url} returned {error.code}; retrying in {delay}s.", file=sys.stderr)
                time.sleep(delay)
                continue
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed: {error.code}\n{detail}") from error

    if last_error:
        detail = last_error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {last_error.code}\n{detail}") from last_error
    raise RuntimeError(f"{method} {url} failed without an HTTP response.")


def fabric_request(method: str, path: str, token: str, body: dict[str, Any] | None = None, expected: tuple[int, ...] = (200, 201, 202)) -> tuple[int, dict[str, str], dict[str, Any] | None]:
    return request_json(method=method, url=f"{FABRIC_API}{path}", token=token, body=body, expected=expected)


def poll_fabric_operation(location: str, token: str, *, attempts: int = 120, delay_seconds: int = 5) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(attempts):
        _, _, payload = request_json(method="GET", url=location, token=token, expected=(200, 202))
        last = payload or {}
        status = str(last.get("status") or last.get("Status") or "").lower()
        if status in {"succeeded", "success", "completed"}:
            return last
        if status in {"failed", "failure", "cancelled", "canceled"}:
            raise RuntimeError(f"Fabric operation failed: {json.dumps(last, indent=2)}")
        time.sleep(delay_seconds)
    raise RuntimeError(
        "Fabric operation did not complete before the sample timeout. "
        f"The service may still be processing the item; retry the command after a few minutes. Last status: {json.dumps(last, indent=2)}"
    )


def az_rest(method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["az", "rest", "--method", method, "--url", url, "-o", "json"]
    if body is not None:
        command.extend(["--body", json.dumps(body)])
    output = run(command)
    return json.loads(output) if output else {}


def wait_for_arm_capacity(resource_id: str, *, attempts: int = 60, delay_seconds: int = 5) -> dict[str, Any]:
    url = f"https://management.azure.com{resource_id}?api-version={FABRIC_CAPACITY_API_VERSION}"
    last: dict[str, Any] = {}
    for _ in range(attempts):
        last = az_rest("get", url)
        state = str(last.get("properties", {}).get("provisioningState") or "").lower()
        if state == "succeeded":
            return last
        if state == "failed":
            raise RuntimeError(f"Fabric capacity provisioning failed: {json.dumps(last, indent=2)}")
        time.sleep(delay_seconds)
    raise RuntimeError(f"Fabric capacity did not become ready: {json.dumps(last, indent=2)}")


def list_fabric_capacities(token: str) -> list[dict[str, Any]]:
    _, _, payload = fabric_request("GET", "/capacities", token)
    return list((payload or {}).get("value", []))


def capacity_by_name(token: str, name: str) -> dict[str, Any] | None:
    for capacity in list_fabric_capacities(token):
        if capacity.get("displayName") == name:
            return capacity
    return None


def capacity_by_name_with_retry(token: str, name: str, *, attempts: int = 3, delay_seconds: int = 5) -> dict[str, Any] | None:
    for attempt in range(1, attempts + 1):
        found = capacity_by_name(token, name)
        if found:
            return found
        if attempt < attempts:
            time.sleep(delay_seconds)
    return None


def create_arm_capacity(settings: dict[str, str], *, dry_run: bool) -> str:
    subscription_id = run(["az", "account", "show", "--query", "id", "-o", "tsv"])
    resource_group = settings["FABRIC_CAPACITY_RESOURCE_GROUP"]
    location = settings["FABRIC_LOCATION"]
    name = settings["FABRIC_CAPACITY_NAME"]
    admin = settings["FABRIC_CAPACITY_ADMIN"]
    sku = settings["FABRIC_CAPACITY_SKU"]
    if dry_run:
        print(f"[dry-run] create Microsoft.Fabric/capacities {name} ({sku}, {location}) in {resource_group}")
        return f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Fabric/capacities/{name}"

    run(["az", "group", "create", "--name", resource_group, "--location", location, "-o", "none"])
    check_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Fabric/locations/{location}/checkNameAvailability?api-version={FABRIC_CAPACITY_API_VERSION}"
    availability = az_rest("post", check_url, {"name": name, "type": "Microsoft.Fabric/capacities"})
    if availability.get("nameAvailable") is False:
        raise RuntimeError(f"Fabric capacity name is not available: {name} ({availability})")

    resource_url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Fabric/capacities/{name}?api-version={FABRIC_CAPACITY_API_VERSION}"
    body = {
        "location": location,
        "sku": {"name": sku, "tier": "Fabric"},
        "properties": {"administration": {"members": [admin]}},
    }
    created = az_rest("put", resource_url, body)
    resource_id = created.get("id") or f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Fabric/capacities/{name}"
    wait_for_arm_capacity(resource_id)
    return resource_id


def ensure_capacity(settings: dict[str, str], token: str, *, dry_run: bool) -> tuple[str, dict[str, Any]]:
    mode = settings["FABRIC_CAPACITY_MODE"]
    if mode == "skip":
        raise RuntimeError("FABRIC_CAPACITY_MODE=skip cannot create a greenfield Fabric workspace.")

    capacity_id = settings.get("FABRIC_CAPACITY_ID", "")
    capacity_name = settings["FABRIC_CAPACITY_NAME"]
    if capacity_id:
        return capacity_id, {"displayName": capacity_name, "id": capacity_id, "state": "Configured", "created": False}

    existing = capacity_by_name_with_retry(token, capacity_name) if not dry_run else None
    if existing:
        return str(existing["id"]), {**existing, "created": False}

    if mode != "create":
        raise RuntimeError(f"Fabric capacity '{capacity_name}' was not found and FABRIC_CAPACITY_MODE={mode}.")

    arm_id = settings.get("FABRIC_CAPACITY_ARM_ID", "")
    if arm_id and not dry_run:
        wait_for_arm_capacity(arm_id)
    else:
        arm_id = create_arm_capacity(settings, dry_run=dry_run)

    if dry_run:
        return "00000000-0000-0000-0000-000000000010", {"displayName": capacity_name, "id": "dry-run-capacity", "state": "DryRun", "created": True, "armId": arm_id}

    for _ in range(FABRIC_CAPACITY_LIST_ATTEMPTS):
        found = capacity_by_name(token, capacity_name)
        if found:
            return str(found["id"]), {**found, "created": True, "armId": arm_id}
        time.sleep(5)
    raise RuntimeError(
        f"Created Fabric capacity '{capacity_name}' in ARM, but Fabric API did not list it before the sample timeout. "
        "The capacity may still be propagating. Run scripts/fabric-destroy.py with this environment if you stop here."
    )


def list_by_display_name(path: str, token: str, display_name: str) -> dict[str, Any] | None:
    _, _, payload = fabric_request("GET", path, token)
    values = (payload or {}).get("value") or (payload or {}).get("data") or []
    for item in values:
        if item.get("displayName") == display_name:
            return item
    return None


def ensure_workspace(settings: dict[str, str], token: str, capacity_id: str, *, dry_run: bool) -> tuple[str, dict[str, Any]]:
    if settings.get("FABRIC_WORKSPACE_ID"):
        return settings["FABRIC_WORKSPACE_ID"], {"id": settings["FABRIC_WORKSPACE_ID"], "displayName": settings["FABRIC_WORKSPACE_NAME"], "created": False}
    name = settings["FABRIC_WORKSPACE_NAME"]
    if dry_run:
        return "00000000-0000-0000-0000-000000000020", {"id": "dry-run-workspace", "displayName": name, "created": True}
    existing = list_by_display_name("/workspaces", token, name)
    if existing:
        return str(existing["id"]), {**existing, "created": False}
    body = {
        "displayName": name,
        "description": "Synthetic Airline Ops workspace for the Foundry IQ live Knowledge Sources sample.",
        "capacityId": capacity_id,
    }
    status, headers, payload = fabric_request("POST", "/workspaces", token, body)
    if status == 202 and headers.get("Location"):
        poll_fabric_operation(headers["Location"], token)
        payload = list_by_display_name("/workspaces", token, name)
    if not payload or not payload.get("id"):
        raise RuntimeError(f"Workspace creation did not return an id: {payload}")
    return str(payload["id"]), {**payload, "created": True}


def ensure_lakehouse(settings: dict[str, str], token: str, workspace_id: str, *, dry_run: bool) -> tuple[str, dict[str, Any]]:
    if settings.get("FABRIC_LAKEHOUSE_ID"):
        return settings["FABRIC_LAKEHOUSE_ID"], {"id": settings["FABRIC_LAKEHOUSE_ID"], "displayName": settings["FABRIC_LAKEHOUSE_NAME"], "created": False}
    name = settings["FABRIC_LAKEHOUSE_NAME"]
    if dry_run:
        return "00000000-0000-0000-0000-000000000030", {"id": "dry-run-lakehouse", "displayName": name, "created": True}
    existing = list_by_display_name(f"/workspaces/{workspace_id}/lakehouses", token, name)
    if existing:
        return str(existing["id"]), {**existing, "created": False}
    status, headers, payload = fabric_request(
        "POST",
        f"/workspaces/{workspace_id}/lakehouses",
        token,
        {"displayName": name, "description": "Airline Ops sample lakehouse."},
    )
    if status == 202 and headers.get("Location"):
        poll_fabric_operation(headers["Location"], token)
        payload = list_by_display_name(f"/workspaces/{workspace_id}/lakehouses", token, name)
    if not payload or not payload.get("id"):
        raise RuntimeError(f"Lakehouse creation did not return an id: {payload}")
    return str(payload["id"]), {**payload, "created": True}


def onelake_path(workspace_id: str, lakehouse_id: str, relative_path: str) -> str:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in relative_path.split("/"))
    return f"{ONELAKE_DFS}/{workspace_id}/{lakehouse_id}/{encoded}"


def onelake_request(method: str, url: str, token: str, body: bytes | None = None, *, extra_headers: dict[str, str] | None = None, ok_statuses: tuple[int, ...] = (200, 201)) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-version": "2021-06-08",
    }
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status not in ok_statuses:
                raise RuntimeError(f"{method} {url} returned {response.status}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {error.code}\n{detail}") from error


def upload_to_onelake(workspace_id: str, lakehouse_id: str, storage_token: str, *, dry_run: bool) -> list[str]:
    uploaded: list[str] = []
    if dry_run:
        return [path.name for path in sorted(DATA_DIR.glob("*.csv"))]

    directory_url = onelake_path(workspace_id, lakehouse_id, "Files/airline-ops") + "?resource=directory"
    try:
        onelake_request("PUT", directory_url, storage_token, ok_statuses=(201,))
    except RuntimeError as error:
        if "409" not in str(error):
            raise

    for path in sorted(DATA_DIR.glob("*.csv")):
        relative_path = f"Files/airline-ops/{path.name}"
        file_url = onelake_path(workspace_id, lakehouse_id, relative_path)
        data = path.read_bytes()
        try:
            onelake_request("PUT", file_url + "?resource=file", storage_token, ok_statuses=(201,))
        except RuntimeError as error:
            if "409" not in str(error):
                raise
        onelake_request(
            "PATCH",
            file_url + "?action=append&position=0",
            storage_token,
            body=data,
            extra_headers={"Content-Type": "application/octet-stream", "Content-Length": str(len(data))},
            ok_statuses=(202,),
        )
        onelake_request(
            "PATCH",
            file_url + f"?action=flush&position={len(data)}",
            storage_token,
            body=b"",
            extra_headers={"Content-Length": "0"},
            ok_statuses=(200,),
        )
        uploaded.append(path.name)
    return uploaded


def load_tables(workspace_id: str, lakehouse_id: str, token: str, *, dry_run: bool) -> list[str]:
    table_names: list[str] = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        table = path.stem
        table_names.append(table)
        if dry_run:
            continue
        body = {
            "relativePath": f"Files/airline-ops/{path.name}",
            "pathType": "File",
            "mode": "Overwrite",
            "formatOptions": {"header": True, "delimiter": ",", "format": "Csv"},
        }
        status, headers, _ = fabric_request("POST", f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table}/load", token, body, expected=(202,))
        if status == 202 and headers.get("Location"):
            poll_fabric_operation(headers["Location"], token, attempts=120, delay_seconds=5)
    return table_names


def list_lakehouse_tables(workspace_id: str, lakehouse_id: str, token: str) -> list[str]:
    _, _, payload = fabric_request("GET", f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables", token)
    return [str(item.get("name")) for item in (payload or {}).get("data", [])]


def wait_for_lakehouse_tables(workspace_id: str, lakehouse_id: str, token: str, expected: list[str]) -> list[str]:
    last: list[str] = []
    for _ in range(36):
        last = list_lakehouse_tables(workspace_id, lakehouse_id, token)
        if set(expected).issubset(set(last)):
            return last
        time.sleep(5)
    return last


def read_csv_columns(file_name: str) -> list[str]:
    with (DATA_DIR / file_name).open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)


def csv_file_for_entity(entity: str) -> str:
    for name, file_name, _ in ENTITY_SPECS:
        if name == entity:
            return file_name
    raise KeyError(entity)


def pascal_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\W]+", value) if part)


def value_type_for_column(column: str) -> str:
    if column.endswith("_usd") or column.endswith("_miles") or column.endswith("_minutes") or column in {"distance_miles"}:
        return "Double"
    return "String"


def graph_value_type_for_column(column: str) -> str:
    if column.endswith("_usd") or column.endswith("_miles") or column.endswith("_minutes") or column in {"distance_miles"}:
        return "INT"
    return "STRING"


def choose_display_column(columns: list[str], primary_key: str) -> str:
    for suffix in ("_name", "_title", "summary"):
        for column in columns:
            if column.endswith(suffix) or column == suffix:
                return column
    return primary_key


def build_ontology_definition(workspace_id: str, lakehouse_id: str, ontology_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    entity_ids: dict[str, str] = {}
    property_ids: dict[tuple[str, str], str] = {}
    entity_sources: dict[str, tuple[str, str, list[str]]] = {}
    parts: list[dict[str, str]] = [
        {"path": "definition.json", "payload": b64_json({}), "payloadType": "InlineBase64"},
        {
            "path": ".platform",
            "payload": b64_json(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                    "metadata": {"type": "Ontology", "displayName": ontology_name},
                    "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
                }
            ),
            "payloadType": "InlineBase64",
        },
    ]

    for entity_name, file_name, primary_key in ENTITY_SPECS:
        entity_id = deterministic_int_id("entity", entity_name)
        entity_ids[entity_name] = entity_id
        table_name = Path(file_name).stem
        columns = read_csv_columns(file_name)
        entity_sources[entity_name] = (table_name, primary_key, columns)
        for column in columns:
            property_ids[(entity_name, column)] = deterministic_int_id("property", entity_name, column)
        display_column = choose_display_column(columns, primary_key)
        entity_definition = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/entityType/1.0.0/schema.json",
            "id": entity_id,
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": entity_name,
            "entityIdParts": [property_ids[(entity_name, primary_key)]],
            "displayNamePropertyId": property_ids[(entity_name, display_column)],
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {
                    "id": property_ids[(entity_name, column)],
                    "name": pascal_case(column),
                    "redefines": None,
                    "baseTypeNamespaceType": None,
                    "valueType": value_type_for_column(column),
                }
                for column in columns
            ],
            "timeseriesProperties": [],
            "untypedProperties": [],
        }
        parts.append({"path": f"EntityTypes/{entity_id}/definition.json", "payload": b64_json(entity_definition), "payloadType": "InlineBase64"})
        binding_id = deterministic_uuid("binding", entity_name, table_name)
        binding = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/dataBinding/1.0.0/schema.json",
            "id": binding_id,
            "dataBindingConfiguration": {
                "dataBindingType": "NonTimeSeries",
                "propertyBindings": [
                    {"sourceColumnName": column, "targetPropertyId": property_ids[(entity_name, column)]}
                    for column in columns
                ],
                "sourceTableProperties": {
                    "sourceType": "LakehouseTable",
                    "workspaceId": workspace_id,
                    "itemId": lakehouse_id,
                    "sourceTableName": table_name,
                    "sourceSchema": "dbo",
                },
            },
        }
        parts.append({"path": f"EntityTypes/{entity_id}/DataBindings/{binding_id}.json", "payload": b64_json(binding), "payloadType": "InlineBase64"})

    primary_keys = {entity_name: primary_key for entity_name, _, primary_key in ENTITY_SPECS}

    for relationship_name, from_entity, to_entity, binding_table, source_column, target_column in RELATIONSHIP_SPECS:
        rel_id = deterministic_int_id("relationship", relationship_name)
        relationship_definition = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/relationshipType/1.0.0/schema.json",
            "namespace": "usertypes",
            "id": rel_id,
            "name": relationship_name,
            "namespaceType": "Custom",
            "source": {"entityTypeId": entity_ids[from_entity]},
            "target": {"entityTypeId": entity_ids[to_entity]},
        }
        parts.append({"path": f"RelationshipTypes/{rel_id}/definition.json", "payload": b64_json(relationship_definition), "payloadType": "InlineBase64"})

        context_id = deterministic_uuid("context", relationship_name, binding_table)
        contextualization = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/contextualization/1.0.0/schema.json",
            "id": context_id,
            "dataBindingTable": {
                "sourceTableName": binding_table,
                "sourceSchema": "dbo",
                "sourceType": "LakehouseTable",
                "workspaceId": workspace_id,
                "itemId": lakehouse_id,
            },
            "sourceKeyRefBindings": [{"sourceColumnName": source_column, "targetPropertyId": property_ids[(from_entity, primary_keys[from_entity])]}],
            "targetKeyRefBindings": [{"sourceColumnName": target_column, "targetPropertyId": property_ids[(to_entity, primary_keys[to_entity])]}],
        }
        parts.append({"path": f"RelationshipTypes/{rel_id}/Contextualizations/{context_id}.json", "payload": b64_json(contextualization), "payloadType": "InlineBase64"})

    manifest = {
        "entityCount": len(ENTITY_SPECS),
        "relationshipCount": len(RELATIONSHIP_SPECS),
        "partCount": len(parts),
        "tables": [Path(file_name).stem for _, file_name, _ in ENTITY_SPECS],
        "entityIds": entity_ids,
        "relationshipIds": {name: deterministic_int_id("relationship", name) for name, *_ in RELATIONSHIP_SPECS},
    }
    return {"parts": parts}, manifest


def graph_table_path(workspace_id: str, lakehouse_id: str, table_name: str) -> str:
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{table_name}"


def build_graph_model_definition(workspace_id: str, lakehouse_id: str, ontology_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _, ontology_manifest = build_ontology_definition(workspace_id, lakehouse_id, ontology_name)
    entity_ids: dict[str, str] = ontology_manifest["entityIds"]
    relationship_ids: dict[str, str] = ontology_manifest["relationshipIds"]
    table_names = sorted({Path(file_name).stem for _, file_name, _ in ENTITY_SPECS} | {table for _, _, _, table, _, _ in RELATIONSHIP_SPECS})
    data_source_names = {table: f"{lakehouse_id}_{table}" for table in table_names}
    data_sources = [
        {
            "name": data_source_names[table],
            "type": "DeltaTable",
            "properties": {"path": graph_table_path(workspace_id, lakehouse_id, table)},
        }
        for table in table_names
    ]

    node_tables: list[dict[str, Any]] = []
    node_types: list[dict[str, Any]] = []
    positions: dict[str, dict[str, int]] = {}
    styles: dict[str, dict[str, int]] = {}
    primary_keys = {entity_name: primary_key for entity_name, _, primary_key in ENTITY_SPECS}

    for index, (entity_name, file_name, primary_key) in enumerate(ENTITY_SPECS):
        table_name = Path(file_name).stem
        columns = read_csv_columns(file_name)
        alias = entity_ids[entity_name]
        node_tables.append(
            {
                "nodeTypeAlias": alias,
                "id": deterministic_uuid("graph-node-table", entity_name),
                "dataSourceName": data_source_names[table_name],
                "propertyMappings": [{"propertyName": pascal_case(column), "sourceColumn": column} for column in columns],
            }
        )
        node_types.append(
            {
                "primaryKeyProperties": [pascal_case(primary_key)],
                "alias": alias,
                "labels": [entity_name],
                "properties": [{"name": pascal_case(column), "type": graph_value_type_for_column(column)} for column in columns],
            }
        )
        positions[alias] = {"x": 100 + (index % 4) * 220, "y": 100 + (index // 4) * 180}
        styles[alias] = {"size": 30}

    edge_tables: list[dict[str, Any]] = []
    edge_types: list[dict[str, Any]] = []
    for relationship_name, from_entity, to_entity, binding_table, source_column, target_column in RELATIONSHIP_SPECS:
        alias = relationship_ids[relationship_name]
        columns = read_csv_columns(f"{binding_table}.csv")
        edge_tables.append(
            {
                "edgeTypeAlias": alias,
                "id": deterministic_uuid("graph-edge-table", relationship_name),
                "dataSourceName": data_source_names[binding_table],
                "sourceNodeKeyColumns": [source_column],
                "destinationNodeKeyColumns": [target_column],
                "propertyMappings": [{"propertyName": pascal_case(column), "sourceColumn": column} for column in columns],
            }
        )
        edge_types.append(
            {
                "alias": alias,
                "labels": [relationship_name],
                "sourceNodeType": {"alias": entity_ids[from_entity]},
                "destinationNodeType": {"alias": entity_ids[to_entity]},
                "properties": [{"name": pascal_case(column), "type": graph_value_type_for_column(column)} for column in columns],
            }
        )
        styles[alias] = {"size": 30}

    parts = [
        {
            "path": "graphType.json",
            "payload": b64_json({"$schema": GRAPH_TYPE_SCHEMA, "nodeTypes": node_types, "edgeTypes": edge_types}),
            "payloadType": "InlineBase64",
        },
        {
            "path": "dataSources.json",
            "payload": b64_json({"$schema": GRAPH_DATA_SOURCES_SCHEMA, "dataSources": data_sources}),
            "payloadType": "InlineBase64",
        },
        {
            "path": "graphDefinition.json",
            "payload": b64_json({"$schema": GRAPH_DEFINITION_SCHEMA, "nodeTables": node_tables, "edgeTables": edge_tables}),
            "payloadType": "InlineBase64",
        },
        {
            "path": "stylingConfiguration.json",
            "payload": b64_json(
                {
                    "$schema": GRAPH_STYLING_SCHEMA,
                    "modelLayout": {"positions": positions, "styles": styles, "pan": {"x": 0.0, "y": 0.0}, "zoomLevel": 1.0},
                    "visualFormat": None,
                    "scenario": "Ontology",
                }
            ),
            "payloadType": "InlineBase64",
        },
        {
            "path": ".platform",
            "payload": b64_json(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                    "metadata": {"type": "GraphModel", "displayName": f"{ontology_name}_graph"},
                    "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
                }
            ),
            "payloadType": "InlineBase64",
        },
    ]
    manifest = {
        "partCount": len(parts),
        "nodeCount": len(node_types),
        "edgeCount": len(edge_types),
        "dataSourceCount": len(data_sources),
    }
    return {"format": "json", "parts": parts}, manifest


def ensure_ontology(settings: dict[str, str], token: str, workspace_id: str, lakehouse_id: str, *, dry_run: bool) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if settings.get("FABRIC_ONTOLOGY_ID"):
        definition, manifest = build_ontology_definition(workspace_id, lakehouse_id, settings["FABRIC_ONTOLOGY_NAME"])
        return settings["FABRIC_ONTOLOGY_ID"], {"id": settings["FABRIC_ONTOLOGY_ID"], "displayName": settings["FABRIC_ONTOLOGY_NAME"], "created": False}, manifest

    name = settings["FABRIC_ONTOLOGY_NAME"]
    definition, manifest = build_ontology_definition(workspace_id, lakehouse_id, name)
    if dry_run:
        return "00000000-0000-0000-0000-000000000040", {"id": "dry-run-ontology", "displayName": name, "created": True}, manifest

    existing = list_by_display_name(f"/workspaces/{workspace_id}/ontologies", token, name)
    if existing:
        ontology_id = str(existing["id"])
        fabric_request("POST", f"/workspaces/{workspace_id}/ontologies/{ontology_id}/updateDefinition", token, {"definition": definition}, expected=(200, 202))
        return ontology_id, {**existing, "created": False, "definitionUpdated": True}, manifest

    body = {
        "displayName": name,
        "description": "Synthetic Airline Ops ontology for Azure AI Search Fabric Ontology Knowledge Source validation.",
        "definition": definition,
    }
    status, headers, payload = fabric_request("POST", f"/workspaces/{workspace_id}/ontologies", token, body)
    if status == 202 and headers.get("Location"):
        poll_fabric_operation(headers["Location"], token)
        payload = list_by_display_name(f"/workspaces/{workspace_id}/ontologies", token, name)
    if not payload or not payload.get("id"):
        raise RuntimeError(f"Ontology creation did not return an id: {payload}")
    return str(payload["id"]), {**payload, "created": True}, manifest


def validate_ontology_definition(workspace_id: str, ontology_id: str, token: str, expected_parts: int, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "partCount": expected_parts}
    _, _, payload = fabric_request("POST", f"/workspaces/{workspace_id}/ontologies/{ontology_id}/getDefinition", token, {})
    parts = ((payload or {}).get("definition") or payload or {}).get("parts", [])
    paths = [part.get("path") for part in parts]
    return {
        "status": "ok" if len(parts) >= expected_parts else "mismatch",
        "partCount": len(parts),
        "hasPlatform": ".platform" in paths,
        "hasRoot": "definition.json" in paths,
    }


def list_graph_models(workspace_id: str, token: str) -> list[dict[str, Any]]:
    _, _, payload = fabric_request("GET", f"/workspaces/{workspace_id}/graphModels", token)
    return list((payload or {}).get("value", []))


def find_ontology_graph_model(workspace_id: str, ontology_id: str, ontology_name: str, token: str) -> dict[str, Any] | None:
    compact_ontology_id = ontology_id.replace("-", "").lower()
    graph_models = list_graph_models(workspace_id, token)
    for graph_model in graph_models:
        display_name = str(graph_model.get("displayName", ""))
        if compact_ontology_id and compact_ontology_id in display_name.lower():
            return graph_model
    for graph_model in graph_models:
        display_name = str(graph_model.get("displayName", ""))
        if display_name.startswith(f"{ontology_name}_graph"):
            return graph_model
    return graph_models[0] if len(graph_models) == 1 else None


def poll_lro(location: str, token: str, *, attempts: int = 60, delay_seconds: int = 5) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(attempts):
        _, _, payload = request_json(method="GET", url=location, token=token, expected=(200, 202))
        last = payload or {}
        status = str(last.get("status") or "").lower()
        if status in {"succeeded", "completed"}:
            return last
        if status in {"failed", "cancelled", "canceled"}:
            return last
        time.sleep(delay_seconds)
    return last


def update_graph_model_definition(workspace_id: str, graph_model_id: str, token: str, definition: dict[str, Any]) -> dict[str, Any]:
    status, headers, payload = fabric_request(
        "POST",
        f"/workspaces/{workspace_id}/graphModels/{graph_model_id}/updateDefinition",
        token,
        {"definition": definition},
        expected=(200, 202),
    )
    if status == 202 and headers.get("Location"):
        return poll_lro(headers["Location"], token, attempts=120, delay_seconds=5)
    return payload or {"status": "Succeeded"}


def refresh_graph_model(workspace_id: str, graph_model_id: str, token: str) -> dict[str, Any]:
    status, headers, payload = request_json(
        method="POST",
        url=f"{FABRIC_API}/workspaces/{workspace_id}/graphModels/{graph_model_id}/jobs/refreshGraph/instances",
        token=token,
        body=b"",
        expected=(200, 202),
        extra_headers={"Content-Type": "application/json", "Content-Length": "0"},
    )
    if status == 202 and headers.get("Location"):
        return poll_lro(headers["Location"], token, attempts=120, delay_seconds=10)
    return payload or {"status": "Succeeded"}


def execute_graph_probe(workspace_id: str, graph_model_id: str, token: str) -> dict[str, Any]:
    body = {"query": "MATCH (node_airline:`Airline`) RETURN TO_JSON_STRING(node_airline) AS `Airline` LIMIT 5;"}
    _, _, payload = request_json(
        method="POST",
        url=f"{FABRIC_API}/workspaces/{workspace_id}/graphModels/{graph_model_id}/executeQuery?beta=True",
        token=token,
        body=body,
        expected=(200,),
    )
    rows = (((payload or {}).get("result") or {}).get("data") or [])
    return {"status": "ok", "rowCount": len(rows), "query": body["query"]}


def wait_for_graph_probe(
    workspace_id: str,
    graph_model_id: str,
    token: str,
    *,
    attempts: int = FABRIC_GRAPH_PROBE_ATTEMPTS,
    delay_seconds: int = FABRIC_GRAPH_PROBE_DELAY_SECONDS,
) -> dict[str, Any]:
    last_error = ""
    last_graph_model: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        for graph_model in list_graph_models(workspace_id, token):
            if str(graph_model.get("id")) == graph_model_id:
                last_graph_model = graph_model
                break
        try:
            probe = execute_graph_probe(workspace_id, graph_model_id, token)
            if probe.get("rowCount", 0) > 0:
                return {
                    "status": "ok",
                    "attempt": attempt,
                    "queryReadiness": (last_graph_model.get("properties") or {}).get("queryReadiness", ""),
                    "probe": probe,
                }
        except Exception as error:
            last_error = str(error)
        time.sleep(delay_seconds)
    return {
        "status": "failed",
        "attempts": attempts,
        "queryReadiness": (last_graph_model.get("properties") or {}).get("queryReadiness", ""),
        "lastDataLoadingStatus": (last_graph_model.get("properties") or {}).get("lastDataLoadingStatus", {}),
        "error": last_error,
        "message": "The GraphModel did not become queryable before the sample timeout. It may still be indexing; retry the run or cleanup generated Fabric assets if you stop here.",
    }


def validate_graph_model(workspace_id: str, lakehouse_id: str, ontology_id: str, ontology_name: str, token: str, *, dry_run: bool) -> dict[str, Any]:
    definition, manifest = build_graph_model_definition(workspace_id, lakehouse_id, ontology_name)
    if dry_run:
        return {"status": "dry-run", "manifest": manifest}
    graph_model = find_ontology_graph_model(workspace_id, ontology_id, ontology_name, token)
    if not graph_model:
        return {"status": "missing", "message": "No GraphModel item was found for the ontology.", "manifest": manifest}

    graph_model_id = str(graph_model["id"])
    validation: dict[str, Any] = {
        "status": "running",
        "graphModelId": graph_model_id,
        "graphModelName": graph_model.get("displayName", ""),
        "initialQueryReadiness": (graph_model.get("properties") or {}).get("queryReadiness", ""),
        "manifest": manifest,
    }
    try:
        update_result = update_graph_model_definition(workspace_id, graph_model_id, token, definition)
        validation["updateDefinition"] = update_result
        first_wait = wait_for_graph_probe(workspace_id, graph_model_id, token)
        validation["firstProbeWait"] = first_wait
        if first_wait.get("status") != "ok":
            refresh_result = refresh_graph_model(workspace_id, graph_model_id, token)
            validation["refreshGraph"] = refresh_result
            if str((refresh_result.get("failureReason") or {}).get("errorCode")) == "RefreshAlreadyInProgress":
                validation["refreshGraphNote"] = "Refresh was already running after updateDefinition; waiting for the active load."
            second_wait = wait_for_graph_probe(
                workspace_id,
                graph_model_id,
                token,
                attempts=FABRIC_GRAPH_SECOND_PROBE_ATTEMPTS,
                delay_seconds=FABRIC_GRAPH_PROBE_DELAY_SECONDS,
            )
            validation["secondProbeWait"] = second_wait
            final_wait = second_wait
        else:
            final_wait = first_wait
        refreshed = find_ontology_graph_model(workspace_id, ontology_id, ontology_name, token) or {}
        validation["queryReadiness"] = (refreshed.get("properties") or {}).get("queryReadiness", "")
        validation["probe"] = final_wait.get("probe", {})
        validation["status"] = "ok" if final_wait.get("status") == "ok" else "failed"
        if final_wait.get("status") != "ok":
            validation["error"] = final_wait.get("error", "")
    except Exception as error:  # Keep the generated IDs available for cleanup and troubleshooting.
        validation["status"] = "failed"
        validation["error"] = str(error)
        refreshed = find_ontology_graph_model(workspace_id, ontology_id, ontology_name, token) or {}
        validation["queryReadiness"] = (refreshed.get("properties") or {}).get("queryReadiness", "")
    return validation


def write_outputs(settings: dict[str, str], summary: dict[str, Any]) -> None:
    env_name = settings["AZURE_ENV_NAME"]
    output_dir = DEPLOYMENTS_DIR / env_name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "fabric-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    env_lines = [
        f"FABRIC_CAPACITY_ID={summary.get('capacityId', '')}",
        f"FABRIC_CAPACITY_NAME={summary.get('capacityName', '')}",
        f"FABRIC_CAPACITY_ARM_ID={summary.get('capacityArmId', '')}",
        f"FABRIC_CAPACITY_RESOURCE_GROUP={summary.get('capacityResourceGroup', '')}",
        f"FABRIC_LOCATION={summary.get('fabricLocation', '')}",
        f"FABRIC_WORKSPACE_ID={summary.get('workspaceId', '')}",
        f"FABRIC_LAKEHOUSE_ID={summary.get('lakehouseId', '')}",
        f"FABRIC_ONTOLOGY_ID={summary.get('ontologyId', '')}",
    ]
    (output_dir / "fabric.env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    md_lines = [
        "# Fabric Provisioning Summary",
        "",
        "This file is generated by `scripts/fabric-provision.py` and is ignored by git.",
        "",
        f"- Environment: `{env_name}`",
        f"- Fabric location: `{summary.get('fabricLocation', '')}`",
        f"- Capacity: `{summary.get('capacityName', '')}` / `{summary.get('capacitySku', '')}`",
        f"- Capacity state: `{summary.get('capacityState', '')}`",
        f"- Workspace: `{summary.get('workspaceName', '')}` / `{summary.get('workspaceId', '')}`",
        f"- Lakehouse: `{summary.get('lakehouseName', '')}` / `{summary.get('lakehouseId', '')}`",
        f"- Ontology: `{summary.get('ontologyName', '')}` / `{summary.get('ontologyId', '')}`",
        f"- Tables loaded: `{', '.join(summary.get('tablesLoaded', []))}`",
        f"- Ontology parts: `{summary.get('ontologyValidation', {}).get('partCount', '')}`",
        f"- GraphModel: `{summary.get('graphValidation', {}).get('graphModelName', '')}` / `{summary.get('graphValidation', {}).get('graphModelId', '')}`",
        f"- Graph readiness: `{summary.get('graphValidation', {}).get('status', '')}` / `{summary.get('graphValidation', {}).get('queryReadiness', '')}`",
        "",
        "## Values For Azure AI Search Postprovision",
        "",
        "```bash",
        f"FABRIC_WORKSPACE_ID={summary.get('workspaceId', '')}",
        f"FABRIC_ONTOLOGY_ID={summary.get('ontologyId', '')}",
        "```",
    ]
    (output_dir / "fabric-summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def build_settings(args: argparse.Namespace, azd_values: dict[str, str]) -> dict[str, str]:
    env_name = args.env_name or get_setting("AZURE_ENV_NAME", azd_values, "dev")
    suffix = sanitize_display_suffix(env_name)
    capacity_name = sanitize_capacity_name(get_setting("FABRIC_CAPACITY_NAME", azd_values, f"fab{suffix}"))
    location = args.fabric_location or get_setting("FABRIC_LOCATION", azd_values, get_setting("AZURE_LOCATION", azd_values, "westus3"))
    capacity_mode = args.capacity_mode or get_setting("FABRIC_CAPACITY_MODE", azd_values, "create")
    account_user = run(["az", "account", "show", "--query", "user.name", "-o", "tsv"], allow_failure=True).strip()
    resource_group = get_setting("FABRIC_CAPACITY_RESOURCE_GROUP", azd_values, get_setting("AZURE_RESOURCE_GROUP", azd_values, f"rg-{env_name}-fabric"))
    return {
        "DEPLOYMENT_MODE": get_setting("DEPLOYMENT_MODE", azd_values, "full"),
        "AZURE_ENV_NAME": env_name,
        "AZURE_RESOURCE_GROUP": get_setting("AZURE_RESOURCE_GROUP", azd_values, ""),
        "FABRIC_CAPACITY_MODE": capacity_mode,
        "FABRIC_CAPACITY_SKU": get_setting("FABRIC_CAPACITY_SKU", azd_values, "F2"),
        "FABRIC_CAPACITY_NAME": capacity_name,
        "FABRIC_CAPACITY_ID": get_setting("FABRIC_CAPACITY_ID", azd_values, ""),
        "FABRIC_CAPACITY_ARM_ID": get_setting("FABRIC_CAPACITY_ARM_ID", azd_values, ""),
        "FABRIC_CAPACITY_RESOURCE_GROUP": resource_group,
        "FABRIC_CAPACITY_ADMIN": get_setting("FABRIC_CAPACITY_ADMIN", azd_values, account_user),
        "FABRIC_LOCATION": location,
        "FABRIC_WORKSPACE_ID": get_setting("FABRIC_WORKSPACE_ID", azd_values, ""),
        "FABRIC_WORKSPACE_NAME": get_setting("FABRIC_WORKSPACE_NAME", azd_values, f"liveks_airline_ops_{suffix}"),
        "FABRIC_LAKEHOUSE_ID": get_setting("FABRIC_LAKEHOUSE_ID", azd_values, ""),
        "FABRIC_LAKEHOUSE_NAME": get_setting("FABRIC_LAKEHOUSE_NAME", azd_values, "airline_ops_lakehouse"),
        "FABRIC_ONTOLOGY_ID": get_setting("FABRIC_ONTOLOGY_ID", azd_values, ""),
        "FABRIC_ONTOLOGY_NAME": get_setting("FABRIC_ONTOLOGY_NAME", azd_values, "AirlineOpsOntology"),
    }


def base_summary(settings: dict[str, str]) -> dict[str, Any]:
    return {
        "status": "running",
        "environmentName": settings["AZURE_ENV_NAME"],
        "fabricLocation": settings["FABRIC_LOCATION"],
        "capacityMode": settings["FABRIC_CAPACITY_MODE"],
        "capacityId": settings.get("FABRIC_CAPACITY_ID", ""),
        "capacityName": settings["FABRIC_CAPACITY_NAME"],
        "capacitySku": settings["FABRIC_CAPACITY_SKU"],
        "capacityState": "",
        "capacityArmId": settings.get("FABRIC_CAPACITY_ARM_ID", ""),
        "capacityResourceGroup": settings["FABRIC_CAPACITY_RESOURCE_GROUP"],
        "capacityCreated": False,
        "workspaceId": settings.get("FABRIC_WORKSPACE_ID", ""),
        "workspaceName": settings["FABRIC_WORKSPACE_NAME"],
        "workspaceCreated": False,
        "lakehouseId": settings.get("FABRIC_LAKEHOUSE_ID", ""),
        "lakehouseName": settings["FABRIC_LAKEHOUSE_NAME"],
        "lakehouseCreated": False,
        "ontologyId": settings.get("FABRIC_ONTOLOGY_ID", ""),
        "ontologyName": settings["FABRIC_ONTOLOGY_NAME"],
        "ontologyCreated": False,
        "uploadedFiles": [],
        "tablesLoaded": [],
        "availableTables": [],
        "ontologyManifest": {},
        "ontologyValidation": {},
        "graphValidation": {},
    }


def write_partial_outputs(settings: dict[str, str], summary: dict[str, Any], *, status: str | None = None) -> None:
    if status:
        summary["status"] = status
    write_outputs(settings, summary)


def sync_capacity_to_azd(summary: dict[str, Any], *, dry_run: bool) -> None:
    for key, value in {
        "FABRIC_CAPACITY_ID": str(summary.get("capacityId", "")),
        "FABRIC_CAPACITY_NAME": str(summary.get("capacityName", "")),
        "FABRIC_CAPACITY_ARM_ID": str(summary.get("capacityArmId", "")),
        "FABRIC_CAPACITY_RESOURCE_GROUP": str(summary.get("capacityResourceGroup", "")),
        "FABRIC_LOCATION": str(summary.get("fabricLocation", "")),
    }.items():
        azd_set(key, value, dry_run=dry_run)


def sync_all_fabric_ids_to_azd(summary: dict[str, Any], *, dry_run: bool) -> None:
    sync_capacity_to_azd(summary, dry_run=dry_run)
    for key, value in {
        "FABRIC_WORKSPACE_ID": str(summary.get("workspaceId", "")),
        "FABRIC_LAKEHOUSE_ID": str(summary.get("lakehouseId", "")),
        "FABRIC_ONTOLOGY_ID": str(summary.get("ontologyId", "")),
    }.items():
        azd_set(key, value, dry_run=dry_run)


def print_cleanup_hint(settings: dict[str, str], error: BaseException) -> None:
    env_name = settings["AZURE_ENV_NAME"]
    print("", file=sys.stderr)
    print(f"Fabric provisioning failed: {error}", file=sys.stderr)
    print("A partial Fabric deployment may remain. To clean up generated Fabric assets:", file=sys.stderr)
    print(f"  python3 scripts/fabric-destroy.py --env-name {env_name} --yes", file=sys.stderr)
    print("If Azure resources were also provisioned, run:", file=sys.stderr)
    print(f"  bash scripts/destroy.sh --env-name {env_name} --yes", file=sys.stderr)


def main() -> None:
    args = parse_args()
    azd_values = load_azd_env()
    settings = build_settings(args, azd_values)

    if settings["DEPLOYMENT_MODE"] != "full" and not args.dry_run:
        print(f"Skipping Fabric greenfield provisioning because DEPLOYMENT_MODE={settings['DEPLOYMENT_MODE']}.")
        return

    if settings["FABRIC_CAPACITY_MODE"] == "create" and not settings["FABRIC_CAPACITY_ADMIN"]:
        raise SystemExit("FABRIC_CAPACITY_ADMIN is required when FABRIC_CAPACITY_MODE=create.")

    print("Fabric provision settings loaded")
    print(json.dumps(settings, indent=2))

    if args.dry_run:
        definition, manifest = build_ontology_definition(
            "00000000-0000-0000-0000-000000000020",
            "00000000-0000-0000-0000-000000000030",
            settings["FABRIC_ONTOLOGY_NAME"],
        )
        print(json.dumps({"dryRun": True, "ontologyManifest": manifest, "definitionPartCount": len(definition["parts"])}, indent=2))
        return

    summary = base_summary(settings)

    try:
        fabric_token = get_token(FABRIC_RESOURCE)
        storage_token = get_token(STORAGE_RESOURCE)

        capacity_id, capacity = ensure_capacity(settings, fabric_token, dry_run=False)
        summary.update(
            {
                "capacityId": capacity_id,
                "capacityName": capacity.get("displayName") or settings["FABRIC_CAPACITY_NAME"],
                "capacitySku": capacity.get("sku") or settings["FABRIC_CAPACITY_SKU"],
                "capacityState": capacity.get("state", ""),
                "capacityArmId": capacity.get("armId") or settings.get("FABRIC_CAPACITY_ARM_ID", ""),
                "capacityResourceGroup": settings["FABRIC_CAPACITY_RESOURCE_GROUP"],
                "capacityCreated": bool(capacity.get("created")),
            }
        )
        write_partial_outputs(settings, summary)
        sync_capacity_to_azd(summary, dry_run=False)

        workspace_id, workspace = ensure_workspace(settings, fabric_token, capacity_id, dry_run=False)
        summary.update(
            {
                "workspaceId": workspace_id,
                "workspaceName": workspace.get("displayName") or settings["FABRIC_WORKSPACE_NAME"],
                "workspaceCreated": bool(workspace.get("created")),
            }
        )
        write_partial_outputs(settings, summary)

        lakehouse_id, lakehouse = ensure_lakehouse(settings, fabric_token, workspace_id, dry_run=False)
        summary.update(
            {
                "lakehouseId": lakehouse_id,
                "lakehouseName": lakehouse.get("displayName") or settings["FABRIC_LAKEHOUSE_NAME"],
                "lakehouseCreated": bool(lakehouse.get("created")),
            }
        )
        write_partial_outputs(settings, summary)

        uploaded_files = upload_to_onelake(workspace_id, lakehouse_id, storage_token, dry_run=False)
        summary["uploadedFiles"] = uploaded_files
        write_partial_outputs(settings, summary)

        tables_loaded = load_tables(workspace_id, lakehouse_id, fabric_token, dry_run=False)
        summary["tablesLoaded"] = tables_loaded
        write_partial_outputs(settings, summary)

        available_tables = wait_for_lakehouse_tables(workspace_id, lakehouse_id, fabric_token, tables_loaded)
        summary["availableTables"] = available_tables
        write_partial_outputs(settings, summary)
        missing_tables = sorted(set(tables_loaded) - set(available_tables))
        if missing_tables:
            raise RuntimeError(f"Lakehouse tables did not appear after load: {missing_tables}")

        ontology_id, ontology, manifest = ensure_ontology(settings, fabric_token, workspace_id, lakehouse_id, dry_run=False)
        summary.update(
            {
                "ontologyId": ontology_id,
                "ontologyName": ontology.get("displayName") or settings["FABRIC_ONTOLOGY_NAME"],
                "ontologyCreated": bool(ontology.get("created")),
                "ontologyManifest": manifest,
            }
        )
        write_partial_outputs(settings, summary)

        ontology_validation = validate_ontology_definition(workspace_id, ontology_id, fabric_token, manifest["partCount"], dry_run=False)
        summary["ontologyValidation"] = ontology_validation
        write_partial_outputs(settings, summary)
        if ontology_validation["status"] != "ok":
            raise RuntimeError(f"Ontology definition validation failed: {ontology_validation}")

        graph_validation = validate_graph_model(workspace_id, lakehouse_id, ontology_id, settings["FABRIC_ONTOLOGY_NAME"], fabric_token, dry_run=False)
        summary["graphValidation"] = graph_validation
        write_partial_outputs(settings, summary, status="complete" if graph_validation.get("status") == "ok" else "failed")

        if graph_validation.get("status") != "ok":
            raise RuntimeError(
                "Fabric GraphModel is not queryable after ontology provisioning. "
                "It may still be indexing; retry later or clean up generated Fabric assets if you stop here. "
                f"Graph validation: {json.dumps(graph_validation, indent=2)}"
            )

        sync_all_fabric_ids_to_azd(summary, dry_run=False)
        print(f"Fabric provision complete. Summary written to deployments/{settings['AZURE_ENV_NAME']}/fabric-summary.md")
    except Exception as error:
        summary["status"] = "failed"
        summary["error"] = str(error)
        write_partial_outputs(settings, summary)
        print_cleanup_hint(settings, error)
        raise


if __name__ == "__main__":
    main()
