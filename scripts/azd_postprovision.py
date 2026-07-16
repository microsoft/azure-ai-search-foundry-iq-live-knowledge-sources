#!/usr/bin/env python3
"""Cross-platform azd postprovision hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def azd_values() -> dict[str, str]:
    result = subprocess.run(["azd", "env", "get-values"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        try:
            values[key] = str(json.loads(raw))
        except json.JSONDecodeError:
            values[key] = raw.strip('"')
    return values


def configured_guid(value: str) -> bool:
    return bool(value and not value.startswith("00000000-") and "<" not in value)


def main() -> int:
    values = azd_values()
    if values.get("DEPLOYMENT_MODE") == "full":
        workspace_id = values.get("FABRIC_WORKSPACE_ID", "")
        ontology_id = values.get("FABRIC_ONTOLOGY_ID", "")
        if not configured_guid(workspace_id) or not configured_guid(ontology_id):
            if values.get("FABRIC_CAPACITY_MODE") == "skip":
                print("Full mode Fabric creation is skipped; postprovision will emit checklist behavior.")
            else:
                run([sys.executable, "scripts/fabric-provision.py"])
    run([sys.executable, "scripts/postprovision.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
