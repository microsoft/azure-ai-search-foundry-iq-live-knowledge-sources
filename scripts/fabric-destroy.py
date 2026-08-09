#!/usr/bin/env python3
"""Delete Fabric assets created by scripts/fabric-provision.py."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
FABRIC_DELETE_ATTEMPTS = 60
FABRIC_DELETE_DELAY_SECONDS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up generated Fabric sample assets.")
    parser.add_argument("--env-name", help="Deployment environment name.")
    parser.add_argument("--yes", action="store_true", help="Delete without interactive confirmation.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify that generated Fabric assets are absent without deleting anything.",
    )
    return parser.parse_args()


def run(command: list[str], *, allow_failure: bool = False) -> str:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 and not allow_failure:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}")
    return completed.stdout.strip()


def load_azd_env() -> dict[str, str]:
    values: dict[str, str] = {}
    output = run(["azd", "env", "get-values"], allow_failure=True)
    for raw_line in output.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def get_token() -> str:
    return run(["az", "account", "get-access-token", "--resource", FABRIC_RESOURCE, "--query", "accessToken", "-o", "tsv"])


def fabric_delete(path: str, token: str) -> None:
    request = urllib.request.Request(f"{FABRIC_API}{path}", headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status not in (200, 202, 204):
                raise RuntimeError(f"DELETE {path} returned {response.status}")
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")
        finally:
            error.close()
        if error.code == 404:
            print(f"[skip] Fabric item already deleted: {path}")
            return
        raise RuntimeError(f"DELETE {path} failed: {error.code}\n{detail}") from error


def fabric_exists(path: str, token: str) -> bool:
    request = urllib.request.Request(
        f"{FABRIC_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status in (200, 202, 204)
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")
        finally:
            error.close()
        if error.code == 404:
            return False
        raise RuntimeError(f"GET {path} failed: {error.code}\n{detail}") from error


def wait_for_fabric_absent(path: str, token: str, label: str) -> None:
    for attempt in range(FABRIC_DELETE_ATTEMPTS):
        if not fabric_exists(path, token):
            print(f"[verify] Generated {label} is absent.")
            return
        if attempt < FABRIC_DELETE_ATTEMPTS - 1:
            time.sleep(FABRIC_DELETE_DELAY_SECONDS)
    raise RuntimeError(f"Generated {label} still exists after cleanup: {path}")


def load_summary(env_name: str) -> dict[str, Any] | None:
    path = REPO_ROOT / "deployments" / env_name / "fabric-summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def confirm(summary: dict[str, Any]) -> None:
    print("This will delete generated Fabric assets:")
    print(json.dumps({k: summary.get(k) for k in ("workspaceName", "workspaceId", "capacityName", "capacityResourceGroup")}, indent=2))
    answer = input("Type 'delete' to continue: ").strip()
    if answer != "delete":
        raise SystemExit("Fabric cleanup cancelled.")


def resource_group_exists(name: str) -> bool:
    output = run(["az", "group", "exists", "--name", name]).strip().lower()
    if output not in {"true", "false"}:
        raise RuntimeError(f"Could not determine whether resource group {name} exists: {output}")
    return output == "true"


def arm_capacity_exists(name: str) -> bool:
    output = run(["az", "resource", "list", "--resource-type", "Microsoft.Fabric/capacities", "--output", "json"])
    try:
        capacities = json.loads(output or "[]")
    except json.JSONDecodeError as error:
        raise RuntimeError("Could not parse the Fabric capacity inventory returned by Azure CLI.") from error
    return any(
        str(capacity.get("name") or "") == name
        for capacity in capacities
        if isinstance(capacity, dict)
    )


def fabric_capacity_exists(name: str, token: str) -> bool:
    request = urllib.request.Request(
        f"{FABRIC_API}/capacities",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")
        finally:
            error.close()
        raise RuntimeError(f"GET /capacities failed: {error.code}\n{detail}") from error
    return any(
        str(capacity.get("displayName") or "") == name
        for capacity in payload.get("value", [])
        if isinstance(capacity, dict)
    )


def wait_for_capacity_absent(name: str, token: str) -> None:
    arm_present = False
    fabric_present = False
    for attempt in range(FABRIC_DELETE_ATTEMPTS):
        arm_present = arm_capacity_exists(name)
        fabric_present = fabric_capacity_exists(name, token)
        if not arm_present and not fabric_present:
            print(f"[verify] Generated Fabric capacity {name} is absent from ARM and Fabric API.")
            return
        if attempt < FABRIC_DELETE_ATTEMPTS - 1:
            time.sleep(FABRIC_DELETE_DELAY_SECONDS)
    raise RuntimeError(
        f"Generated Fabric capacity still exists after cleanup: {name} "
        f"(ARM={arm_present}, Fabric API={fabric_present})"
    )


def delete_capacity_resource_group(summary: dict[str, Any], azd_values: dict[str, str]) -> bool:
    if not summary.get("capacityCreated"):
        return False
    rg = str(summary.get("capacityResourceGroup") or "")
    if not rg:
        raise RuntimeError("Generated Fabric capacity is missing capacityResourceGroup in the cleanup summary.")
    azure_rg = azd_values.get("AZURE_RESOURCE_GROUP", "")
    if rg.lower() == azure_rg.lower():
        print(f"[skip] Fabric capacity is in azd resource group {rg}; azd down will delete it.")
        return True
    if resource_group_exists(rg):
        print(f"[delete] Azure resource group for generated Fabric capacity: {rg}")
        run(["az", "group", "delete", "--name", rg, "--yes", "--no-wait"])
        run(["az", "group", "wait", "--name", rg, "--deleted", "--timeout", "1800"])
    return False


def verify_cleanup(summary: dict[str, Any], token: str, *, verify_capacity: bool = True) -> None:
    generated_items = (
        (
            "ontology",
            "ontologyCreated",
            "ontologyId",
            lambda workspace_id, item_id: f"/workspaces/{workspace_id}/ontologies/{item_id}",
        ),
        (
            "Lakehouse",
            "lakehouseCreated",
            "lakehouseId",
            lambda workspace_id, item_id: f"/workspaces/{workspace_id}/lakehouses/{item_id}",
        ),
    )
    workspace_id = str(summary.get("workspaceId") or "")
    for label, created_key, id_key, path_for in generated_items:
        if not summary.get(created_key):
            continue
        item_id = str(summary.get(id_key) or "")
        if not workspace_id or not item_id:
            raise RuntimeError(f"Generated {label} is missing its workspace or item ID in the cleanup summary.")
        wait_for_fabric_absent(path_for(workspace_id, item_id), token, label)

    if summary.get("workspaceCreated"):
        if not workspace_id:
            raise RuntimeError("Generated Fabric workspace is missing workspaceId in the cleanup summary.")
        wait_for_fabric_absent(f"/workspaces/{workspace_id}", token, "workspace")

    if summary.get("capacityCreated") and verify_capacity:
        capacity_name = str(summary.get("capacityName") or "")
        capacity_group = str(summary.get("capacityResourceGroup") or "")
        if not capacity_name or not capacity_group:
            raise RuntimeError("Generated Fabric capacity is missing its name or resource group in the cleanup summary.")
        if resource_group_exists(capacity_group):
            raise RuntimeError(f"Generated Fabric capacity resource group still exists: {capacity_group}")
        wait_for_capacity_absent(capacity_name, token)
        print(f"[verify] Generated Fabric capacity resource group {capacity_group} is absent.")
    elif summary.get("capacityCreated"):
        print("[verify] Generated Fabric capacity release is deferred to azd down.")
    else:
        capacity_name = str(summary.get("capacityName") or "")
        if not capacity_name:
            raise RuntimeError("Reused Fabric capacity is missing capacityName in the cleanup summary.")
        if not fabric_capacity_exists(capacity_name, token):
            raise RuntimeError(f"Reused Fabric capacity is no longer present: {capacity_name}")
        print(f"[verify] Reused Fabric capacity {capacity_name} is preserved.")


def main() -> None:
    args = parse_args()
    azd_values = load_azd_env()
    env_name = args.env_name or os.environ.get("AZURE_ENV_NAME") or azd_values.get("AZURE_ENV_NAME") or "dev"
    summary = load_summary(env_name)
    if not summary:
        if args.verify_only:
            raise RuntimeError(f"Fabric cleanup summary is missing for {env_name}; release cannot be verified.")
        print(f"No Fabric summary found for {env_name}; nothing to delete.")
        return
    token = get_token()
    if args.verify_only:
        verify_cleanup(summary, token)
        print("Fabric release verified.")
        return
    if not args.yes:
        confirm(summary)

    workspace_id = str(summary.get("workspaceId") or "")
    ontology_id = str(summary.get("ontologyId") or "")
    lakehouse_id = str(summary.get("lakehouseId") or "")

    if workspace_id and ontology_id and summary.get("ontologyCreated"):
        print(f"[delete] Ontology {ontology_id}")
        fabric_delete(f"/workspaces/{workspace_id}/ontologies/{ontology_id}", token)
    if workspace_id and lakehouse_id and summary.get("lakehouseCreated"):
        print(f"[delete] Lakehouse {lakehouse_id}")
        fabric_delete(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}", token)
    if workspace_id and summary.get("workspaceCreated"):
        print(f"[delete] Workspace {workspace_id}")
        fabric_delete(f"/workspaces/{workspace_id}", token)

    capacity_release_deferred = delete_capacity_resource_group(summary, azd_values)
    verify_cleanup(summary, token, verify_capacity=not capacity_release_deferred)
    print("Fabric cleanup and release verification complete.")


if __name__ == "__main__":
    main()
