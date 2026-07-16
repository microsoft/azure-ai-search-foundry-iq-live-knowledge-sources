#!/usr/bin/env python3
"""Build and deploy the Static Web Apps frontend and managed API."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{detail}")
    return (result.stdout or "").strip()


def azd_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in run(["azd", "env", "get-values"], capture=True).splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        try:
            values[key] = str(json.loads(raw))
        except json.JSONDecodeError:
            values[key] = raw.strip('"')
    return values


def main() -> int:
    values = azd_values()
    if values.get("AZURE_HOSTING_MODE", "staticwebapp") != "staticwebapp":
        print("Static Web Apps hosting is disabled; skipping managed API deployment.")
        return 0
    resource_group = values.get("AZURE_RESOURCE_GROUP", "")
    app_name = values.get("AZURE_STATIC_WEB_APP_NAME", "")
    if not resource_group or not app_name:
        raise SystemExit("AZURE_RESOURCE_GROUP and AZURE_STATIC_WEB_APP_NAME are required.")
    run(["npm", "--prefix", "static-app", "ci"])
    run(["npm", "--prefix", "static-app", "run", "build"])
    token = run(
        [
            "az",
            "staticwebapp",
            "secrets",
            "list",
            "--name",
            app_name,
            "--resource-group",
            resource_group,
            "--query",
            "properties.apiKey",
            "-o",
            "tsv",
        ],
        capture=True,
    )
    if not token:
        raise SystemExit("Unable to read the Static Web Apps deployment token.")
    run(
        [
            "npx",
            "--yes",
            "@azure/static-web-apps-cli@2.0.6",
            "deploy",
            "static-app/dist",
            "--api-location",
            "static-app/.build/api",
            "--api-language",
            "node",
            "--api-version",
            "22",
            "--deployment-token",
            token,
            "--env",
            "production",
        ]
    )
    print("Static Web Apps frontend and managed API deployment complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
