#!/usr/bin/env python3
"""Delete Fabric assets created by scripts/fabric-provision.py."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up generated Fabric sample assets.")
    parser.add_argument("--env-name", help="Deployment environment name.")
    parser.add_argument("--yes", action="store_true", help="Delete without interactive confirmation.")
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
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 404:
            print(f"[skip] Fabric item already deleted: {path}")
            return
        raise RuntimeError(f"DELETE {path} failed: {error.code}\n{detail}") from error


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


def delete_capacity_resource_group(summary: dict[str, Any], azd_values: dict[str, str]) -> None:
    if not summary.get("capacityCreated"):
        return
    rg = str(summary.get("capacityResourceGroup") or "")
    if not rg:
        return
    azure_rg = azd_values.get("AZURE_RESOURCE_GROUP", "")
    if rg == azure_rg:
        print(f"[skip] Fabric capacity is in azd resource group {rg}; azd down will delete it.")
        return
    print(f"[delete] Azure resource group for generated Fabric capacity: {rg}")
    run(["az", "group", "delete", "--name", rg, "--yes", "--no-wait"], allow_failure=True)


def main() -> None:
    args = parse_args()
    azd_values = load_azd_env()
    env_name = args.env_name or os.environ.get("AZURE_ENV_NAME") or azd_values.get("AZURE_ENV_NAME") or "dev"
    summary = load_summary(env_name)
    if not summary:
        print(f"No Fabric summary found for {env_name}; nothing to delete.")
        return
    if not args.yes:
        confirm(summary)

    token = get_token()
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

    delete_capacity_resource_group(summary, azd_values)
    print("Fabric cleanup complete.")


if __name__ == "__main__":
    main()
