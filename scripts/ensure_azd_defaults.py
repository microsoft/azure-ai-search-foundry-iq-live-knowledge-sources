#!/usr/bin/env python3
"""Cross-platform azd preprovision defaults for direct azd users."""

from __future__ import annotations

import json
import subprocess


def run(command: list[str], *, check: bool = True) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stdout}")
    return result.stdout.strip()


def azd_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in run(["azd", "env", "get-values"], check=False).splitlines():
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
    env_name = values.get("AZURE_ENV_NAME", "dev")
    defaults = {
        "AZURE_HOSTING_MODE": "staticwebapp",
        "AZURE_STATIC_WEB_APP_LOCATION": "eastus2",
        "AZURE_APP_SERVICE_SKU": "F1",
        "AZURE_BASE_NAME": "fiqliveks",
        "AZURE_SEARCH_SKU": "basic",
        "AZURE_SEARCH_API_VERSION": "2026-05-01-preview",
        "AZURE_OPENAI_DEPLOYMENT_ID": "gpt-5-mini",
        "AZURE_OPENAI_MODEL_NAME": "gpt-5-mini",
        "AZURE_OPENAI_MODEL_VERSION": "2025-08-07",
        "AZURE_OPENAI_DEPLOYMENT_CAPACITY": "10",
        "DEPLOYMENT_MODE": "mcp-only",
        "FABRIC_CAPACITY_MODE": "skip",
        "FABRIC_CAPACITY_SKU": "F2",
        "FABRIC_CAPACITY_NAME": "",
        "FABRIC_CAPACITY_ADMIN": "",
        "AZURE_RESOURCE_GROUP": f"rg-{env_name}",
        "AZURE_NAME_SALT": env_name,
        "AIRLINE_OPS_INDEX_NAME": "airline-ops-regulatory-docs",
        "MCP_KNOWLEDGE_SOURCE_NAME": "microsoft-learn-mcp-ks",
        "FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME": "fabric-ontology-ks",
        "MCP_ONLY_KNOWLEDGE_BASE_NAME": "live-knowledge-sources-mcp-kb",
        "FABRIC_ONLY_KNOWLEDGE_BASE_NAME": "live-knowledge-sources-fabric-kb",
        "KNOWLEDGE_BASE_NAME": "live-knowledge-sources-kb",
        "MCP_SERVER_URL": "https://learn.microsoft.com/api/mcp",
        "MCP_TOOL_NAME": "microsoft_docs_search",
    }
    defaults["FABRIC_LOCATION"] = values.get("AZURE_LOCATION", "eastus")
    for key, value in defaults.items():
        if key not in values or values[key] == "":
            run(["azd", "env", "set", key, value])
            print(f"[azd-defaults] {key} configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
