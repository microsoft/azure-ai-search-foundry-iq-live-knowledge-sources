#!/usr/bin/env python3
"""Post-provision configuration for the live Knowledge Sources sample.

This script is designed for Azure Developer CLI hooks and manual execution:

    python3 scripts/postprovision.py
    python3 scripts/postprovision.py --dry-run

It configures:
- Microsoft Learn MCP Server Knowledge Source
- MCP-only Knowledge Base
- Combined Knowledge Base skeleton
- Airline Ops regulatory Search index
- Secret-free deployment summary markdown
"""

from __future__ import annotations

import argparse
import csv
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
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
VALID_DEPLOYMENT_MODES = {"byo-fabric", "mcp-only", "full"}

from ks_factory import create_fabric_ontology_knowledge_source, create_knowledge_base, create_mcp_server_knowledge_source
from ks_factory.diagnostics import summarize_activity, summarize_references


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure Knowledge Sources after azd provision.")
    parser.add_argument("--dry-run", action="store_true", help="Print intended operations without calling Azure.")
    return parser.parse_args()


def run(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}")
    return completed.stdout.strip()


def run_with_retries(command: list[str], *, attempts: int = 12, delay_seconds: int = 10) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return run(command)
        except Exception as error:  # noqa: BLE001 - keep CLI detail for setup diagnostics.
            last_error = error
            if attempt == attempts:
                break
            print(f"Waiting for Azure resource readiness ({attempt}/{attempts})...")
            time.sleep(delay_seconds)
    raise RuntimeError(str(last_error)) from last_error


def load_azd_env() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        output = run(["azd", "env", "get-values"])
    except (FileNotFoundError, RuntimeError):
        return values

    for raw_line in output.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def get_setting(name: str, azd_values: dict[str, str], default: str = "") -> str:
    return os.environ.get(name) or azd_values.get(name) or default


def search_request(
    *,
    method: str,
    endpoint: str,
    api_key: str,
    api_version: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    request_headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if headers:
        request_headers.update(headers)

    data = None if body is None else json.dumps(body).encode("utf-8")
    url = f"{endpoint.rstrip('/')}{path}?api-version={api_version}"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {error.code}\n{detail}") from error


def get_search_admin_key(settings: dict[str, str]) -> str:
    if settings.get("AZURE_SEARCH_API_KEY"):
        return settings["AZURE_SEARCH_API_KEY"]

    service_name = settings["AZURE_SEARCH_SERVICE_NAME"]
    resource_group = settings["AZURE_RESOURCE_GROUP"]
    return run_with_retries(
        [
            "az",
            "search",
            "admin-key",
            "show",
            "--service-name",
            service_name,
            "--resource-group",
            resource_group,
            "--query",
            "primaryKey",
            "-o",
            "tsv",
        ]
    )


def create_regulatory_index_payload(index_name: str) -> dict[str, Any]:
    return {
        "name": index_name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "title", "type": "Edm.String", "searchable": True},
            {"name": "content", "type": "Edm.String", "searchable": True},
            {"name": "applicable_scope", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "applicable_delay_category", "type": "Edm.String", "searchable": True, "filterable": True, "facetable": True},
            {"name": "trigger_condition", "type": "Edm.String", "searchable": True},
            {"name": "source_type", "type": "Edm.String", "filterable": True, "facetable": True},
        ],
    }


def load_regulatory_documents() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = REPO_ROOT / "samples" / "data" / "airline-ops" / "regulatory_references.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "@search.action": "upload",
                    "id": row["reference_id"],
                    "title": row["reference_title"],
                    "content": row["summary"],
                    "applicable_scope": row["applicable_scope"],
                    "applicable_delay_category": row["applicable_delay_category"],
                    "trigger_condition": row["trigger_condition"],
                    "source_type": row["source_type"],
                }
            )
    return rows


def write_summary(settings: dict[str, str], smoke: dict[str, Any]) -> Path:
    env_name = settings.get("AZURE_ENV_NAME") or "dev"
    summary_dir = REPO_ROOT / "deployments" / env_name
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "deployment-summary.md"

    lines = [
        "# Deployment Summary",
        "",
        "This file is generated by `scripts/postprovision.py` and is ignored by git.",
        "",
        "## Endpoints",
        "",
        f"- Deployment mode: {settings.get('DEPLOYMENT_MODE', 'mcp-only')}",
        f"- App URL: {settings.get('AZURE_WEBAPP_URL', '')}",
        f"- Hosting mode: {settings.get('AZURE_HOSTING_MODE', '')}",
        f"- Static Web Apps region: {settings.get('AZURE_STATIC_WEB_APP_LOCATION', '')}",
        f"- Azure AI Search endpoint: {settings.get('AZURE_SEARCH_ENDPOINT', '')}",
        f"- Azure OpenAI endpoint: {settings.get('AZURE_OPENAI_ENDPOINT', '')}",
        "",
        "## Resource Names",
        "",
        f"- Resource group: {settings.get('AZURE_RESOURCE_GROUP', '')}",
        f"- Search service: {settings.get('AZURE_SEARCH_SERVICE_NAME', '')}",
        f"- Static Web App: {settings.get('AZURE_STATIC_WEB_APP_NAME', '')}",
        f"- App Service: {settings.get('AZURE_WEBAPP_NAME', '')}",
        f"- Storage account: {settings.get('AZURE_STORAGE_ACCOUNT_NAME', '')}",
        "",
        "## Knowledge Sources And Knowledge Bases",
        "",
        f"- MCP KS: {settings.get('MCP_KNOWLEDGE_SOURCE_NAME', '')}",
        f"- Fabric KS: {settings.get('FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME', '')}",
        f"- Fabric workspace configured: {'yes' if fabric_configured(settings) else 'no'}",
        f"- Fabric capacity ID: {settings.get('FABRIC_CAPACITY_ID', '')}",
        f"- Fabric workspace ID: {settings.get('FABRIC_WORKSPACE_ID', '')}",
        f"- Fabric lakehouse ID: {settings.get('FABRIC_LAKEHOUSE_ID', '')}",
        f"- Fabric ontology ID: {settings.get('FABRIC_ONTOLOGY_ID', '')}",
        f"- Fabric source created: {'yes' if should_create_fabric_source(settings) else 'no'}",
        f"- Fabric automation status: {fabric_automation_status(settings)}",
        f"- MCP-only KB: {settings.get('MCP_ONLY_KNOWLEDGE_BASE_NAME', '')}",
        f"- Combined KB: {settings.get('KNOWLEDGE_BASE_NAME', '')}",
        f"- Airline Ops Search index: {settings.get('AIRLINE_OPS_INDEX_NAME', '')}",
        "",
        "## Notebook Values",
        "",
        "```bash",
        f"DEPLOYMENT_MODE={settings.get('DEPLOYMENT_MODE', 'mcp-only')}",
        f"SEARCH_ENDPOINT={settings.get('AZURE_SEARCH_ENDPOINT', '')}",
        f"SEARCH_API_VERSION={settings.get('AZURE_SEARCH_API_VERSION', '2026-05-01-preview')}",
        f"KNOWLEDGE_BASE_NAME={settings.get('KNOWLEDGE_BASE_NAME', '')}",
        f"MCP_ONLY_KNOWLEDGE_BASE_NAME={settings.get('MCP_ONLY_KNOWLEDGE_BASE_NAME', '')}",
        f"MCP_KNOWLEDGE_SOURCE_NAME={settings.get('MCP_KNOWLEDGE_SOURCE_NAME', '')}",
        f"FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME={settings.get('FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME', '')}",
        f"FABRIC_WORKSPACE_ID={settings.get('FABRIC_WORKSPACE_ID', '')}",
        f"FABRIC_ONTOLOGY_ID={settings.get('FABRIC_ONTOLOGY_ID', '')}",
        f"AZURE_OPENAI_ENDPOINT={settings.get('AZURE_OPENAI_ENDPOINT', '')}",
        f"AZURE_OPENAI_DEPLOYMENT_ID={settings.get('AZURE_OPENAI_DEPLOYMENT_ID', '')}",
        f"AZURE_OPENAI_MODEL_NAME={settings.get('AZURE_OPENAI_MODEL_NAME', '')}",
        "RUN_LIVE_CALLS=true",
        "```",
        "",
        "Add `SEARCH_API_KEY` locally from Azure Portal or Azure CLI. Do not commit it.",
        "",
        "## Smoke Test",
        "",
        "```json",
        json.dumps(smoke, indent=2),
        "```",
        "",
        "## Troubleshooting",
        "",
        "- MCP path: `docs/03-mcp-server-ks.md`",
        "- Fabric path: `docs/04-fabric-ontology-ks.md`",
        "- Offline replay: `docs/09-offline-replay.md`",
        "- Test queries: `docs/08-test-queries.md`",
    ]

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def is_real_config_value(value: str) -> bool:
    return bool(value and not value.startswith("00000000") and "<" not in value)


def fabric_configured(settings: dict[str, str]) -> bool:
    workspace_id = settings.get("FABRIC_WORKSPACE_ID", "")
    ontology_id = settings.get("FABRIC_ONTOLOGY_ID", "")
    return is_real_config_value(workspace_id) and is_real_config_value(ontology_id)


def should_create_fabric_source(settings: dict[str, str]) -> bool:
    mode = settings.get("DEPLOYMENT_MODE", "mcp-only")
    return mode in {"byo-fabric", "full"} and fabric_configured(settings)


def fabric_automation_status(settings: dict[str, str]) -> str:
    mode = settings.get("DEPLOYMENT_MODE", "mcp-only")
    if mode == "mcp-only":
        return "skipped"
    if mode == "byo-fabric":
        return "byo-connected" if fabric_configured(settings) else "byo-missing"
    if fabric_configured(settings):
        return "full-fabric-provisioned-or-connected"
    return "full-fabric-provision-required"


def write_full_mode_checklist(settings: dict[str, str]) -> Path:
    env_name = settings.get("AZURE_ENV_NAME") or "dev"
    checklist_dir = REPO_ROOT / "deployments" / env_name
    checklist_dir.mkdir(parents=True, exist_ok=True)
    checklist_path = checklist_dir / "fabric-full-mode-checklist.md"
    checklist_path.write_text(
        "\n".join(
            [
                "# Full Greenfield Fabric Automation Checklist",
                "",
                "This file is generated and ignored by git.",
                "",
                "Full Greenfield Mode is the target one-command path for tenants that do not already have Fabric assets.",
                "",
                "## Current Automated Scope",
                "",
                "- Azure AI Search",
                "- Azure OpenAI / Foundry model deployment",
                "- Microsoft Learn MCP Server Knowledge Source",
                "- MCP-only and combined Knowledge Bases",
                "- Airline Ops Search index",
                "- Static Web Apps demo UI and managed Functions API",
                "",
                "## Fabric Automation Required Before Search Postprovision",
                "",
                "Run `scripts/fabric-provision.py` before this Search postprovision step, or provide existing Fabric IDs:",
                "",
                "1. Create or select Fabric capacity.",
                "2. Create a Fabric workspace.",
                "3. Load the Airline Ops sample data.",
                "4. Create the Fabric ontology item.",
                "5. Map entities, relationships, measures, and synonyms.",
                "6. Export `FABRIC_WORKSPACE_ID` and `FABRIC_ONTOLOGY_ID`.",
                "7. Re-run `scripts/postprovision.py` so Azure AI Search creates the Fabric Ontology Knowledge Source.",
                "",
                "`scripts/postprovision.sh` performs this automatically for `DEPLOYMENT_MODE=full` when Fabric creation is enabled.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return checklist_path


def validate_mode_settings(settings: dict[str, str]) -> None:
    mode = settings.get("DEPLOYMENT_MODE", "mcp-only")
    if mode not in VALID_DEPLOYMENT_MODES:
        raise SystemExit(f"Invalid DEPLOYMENT_MODE '{mode}'. Allowed values: {', '.join(sorted(VALID_DEPLOYMENT_MODES))}")

    if mode == "byo-fabric" and not fabric_configured(settings):
        raise SystemExit("DEPLOYMENT_MODE=byo-fabric requires FABRIC_WORKSPACE_ID and FABRIC_ONTOLOGY_ID.")


def main() -> None:
    args = parse_args()
    azd_values = load_azd_env()

    settings = {
        "DEPLOYMENT_MODE": get_setting("DEPLOYMENT_MODE", azd_values, "mcp-only"),
        "AZURE_ENV_NAME": get_setting("AZURE_ENV_NAME", azd_values, "dev"),
        "AZURE_RESOURCE_GROUP": get_setting("AZURE_RESOURCE_GROUP", azd_values),
        "AZURE_SEARCH_SERVICE_NAME": get_setting("AZURE_SEARCH_SERVICE_NAME", azd_values),
        "AZURE_SEARCH_ENDPOINT": get_setting("AZURE_SEARCH_ENDPOINT", azd_values),
        "AZURE_SEARCH_API_VERSION": get_setting("AZURE_SEARCH_API_VERSION", azd_values, "2026-05-01-preview"),
        "AZURE_SEARCH_API_KEY": get_setting("AZURE_SEARCH_API_KEY", azd_values),
        "AZURE_OPENAI_ENDPOINT": get_setting("AZURE_OPENAI_ENDPOINT", azd_values),
        "AZURE_OPENAI_ACCOUNT_NAME": get_setting("AZURE_OPENAI_ACCOUNT_NAME", azd_values),
        "AZURE_OPENAI_DEPLOYMENT_ID": get_setting("AZURE_OPENAI_DEPLOYMENT_ID", azd_values),
        "AZURE_OPENAI_MODEL_NAME": get_setting("AZURE_OPENAI_MODEL_NAME", azd_values, "gpt-4o-mini"),
        "AZURE_OPENAI_API_KEY": get_setting("AZURE_OPENAI_API_KEY", azd_values),
        "AZURE_STORAGE_ACCOUNT_NAME": get_setting("AZURE_STORAGE_ACCOUNT_NAME", azd_values),
        "AZURE_HOSTING_MODE": get_setting("AZURE_HOSTING_MODE", azd_values, "staticwebapp"),
        "AZURE_STATIC_WEB_APP_LOCATION": get_setting("AZURE_STATIC_WEB_APP_LOCATION", azd_values, "eastus2"),
        "AZURE_STATIC_WEB_APP_NAME": get_setting("AZURE_STATIC_WEB_APP_NAME", azd_values),
        "AZURE_WEBAPP_NAME": get_setting("AZURE_WEBAPP_NAME", azd_values),
        "AZURE_WEBAPP_URL": get_setting("AZURE_WEBAPP_URL", azd_values),
        "AIRLINE_OPS_INDEX_NAME": get_setting("AIRLINE_OPS_INDEX_NAME", azd_values, "airline-ops-regulatory-docs"),
        "MCP_KNOWLEDGE_SOURCE_NAME": get_setting("MCP_KNOWLEDGE_SOURCE_NAME", azd_values, "microsoft-learn-mcp-ks"),
        "MCP_ONLY_KNOWLEDGE_BASE_NAME": get_setting("MCP_ONLY_KNOWLEDGE_BASE_NAME", azd_values, "live-knowledge-sources-mcp-kb"),
        "KNOWLEDGE_BASE_NAME": get_setting("KNOWLEDGE_BASE_NAME", azd_values, "live-knowledge-sources-kb"),
        "FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME": get_setting("FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME", azd_values, "fabric-ontology-ks"),
        "FABRIC_CAPACITY_ID": get_setting("FABRIC_CAPACITY_ID", azd_values),
        "FABRIC_LAKEHOUSE_ID": get_setting("FABRIC_LAKEHOUSE_ID", azd_values),
        "FABRIC_WORKSPACE_ID": get_setting("FABRIC_WORKSPACE_ID", azd_values),
        "FABRIC_ONTOLOGY_ID": get_setting("FABRIC_ONTOLOGY_ID", azd_values),
    }
    validate_mode_settings(settings)

    required = [
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_SERVICE_NAME",
        "AZURE_RESOURCE_GROUP",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_ID",
    ]
    missing = [name for name in required if not settings.get(name)]
    if missing and not args.dry_run:
        raise SystemExit(f"Missing required deployment settings: {', '.join(missing)}")

    print("Postprovision settings loaded")
    print(json.dumps({k: v for k, v in settings.items() if "KEY" not in k and "TOKEN" not in k}, indent=2))

    smoke: dict[str, Any] = {"dryRun": args.dry_run, "steps": []}
    if settings["DEPLOYMENT_MODE"] == "full" and not fabric_configured(settings):
        checklist_path = write_full_mode_checklist(settings)
        smoke["steps"].append({"name": "fabric_full_automation", "status": "pending", "checklist": str(checklist_path.relative_to(REPO_ROOT))})

    if args.dry_run:
        summary_path = write_summary(settings, smoke)
        print(f"Dry run complete. Summary written to {summary_path}")
        return

    search_api_key = get_search_admin_key(settings)
    openai_api_key = settings.get("AZURE_OPENAI_API_KEY") or None
    if not openai_api_key:
        print("Azure OpenAI API key not provided; using Search managed identity RBAC for model access.")

    mcp_source = create_mcp_server_knowledge_source(
        name=settings["MCP_KNOWLEDGE_SOURCE_NAME"],
        server_url="https://learn.microsoft.com/api/mcp",
        tool_name="microsoft_docs_search",
        description="Microsoft Learn MCP grounding source for official documentation.",
    )
    mcp_only_kb = create_knowledge_base(
        name=settings["MCP_ONLY_KNOWLEDGE_BASE_NAME"],
        knowledge_source_names=[settings["MCP_KNOWLEDGE_SOURCE_NAME"]],
        azure_openai_endpoint=settings["AZURE_OPENAI_ENDPOINT"],
        azure_openai_deployment_id=settings["AZURE_OPENAI_DEPLOYMENT_ID"],
        azure_openai_model_name=settings["AZURE_OPENAI_MODEL_NAME"],
        azure_openai_api_key=openai_api_key,
        description="Knowledge Base for validating MCP Server live grounding.",
        retrieval_instructions="Use Microsoft Learn MCP Server for Azure AI Search and Foundry IQ implementation guidance.",
    )
    combined_source_names = [settings["MCP_KNOWLEDGE_SOURCE_NAME"]]
    if should_create_fabric_source(settings):
        combined_source_names.append(settings["FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME"])

    combined_kb = create_knowledge_base(
        name=settings["KNOWLEDGE_BASE_NAME"],
        knowledge_source_names=combined_source_names,
        azure_openai_endpoint=settings["AZURE_OPENAI_ENDPOINT"],
        azure_openai_deployment_id=settings["AZURE_OPENAI_DEPLOYMENT_ID"],
        azure_openai_model_name=settings["AZURE_OPENAI_MODEL_NAME"],
        azure_openai_api_key=openai_api_key,
        description="Combined Knowledge Base skeleton for MCP Server and optional Fabric Ontology Knowledge Sources.",
        retrieval_instructions=(
            "Use MCP Server for Microsoft Learn implementation guidance. "
            "When Fabric Ontology is configured, use it for Airline Ops business semantics."
        ),
    )

    endpoint = settings["AZURE_SEARCH_ENDPOINT"]
    api_version = settings["AZURE_SEARCH_API_VERSION"]

    search_request(method="PUT", endpoint=endpoint, api_key=search_api_key, api_version=api_version, path=f"/knowledgesources/{settings['MCP_KNOWLEDGE_SOURCE_NAME']}", body=mcp_source)
    smoke["steps"].append({"name": "create_mcp_knowledge_source", "status": "ok"})

    if should_create_fabric_source(settings):
        fabric_source = create_fabric_ontology_knowledge_source(
            name=settings["FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME"],
            workspace_id=settings["FABRIC_WORKSPACE_ID"],
            ontology_id=settings["FABRIC_ONTOLOGY_ID"],
            description="Governed Airline Ops business-semantic grounding source from Microsoft Fabric.",
        )
        search_request(
            method="PUT",
            endpoint=endpoint,
            api_key=search_api_key,
            api_version=api_version,
            path=f"/knowledgesources/{settings['FABRIC_ONTOLOGY_KNOWLEDGE_SOURCE_NAME']}",
            body=fabric_source,
        )
        smoke["steps"].append({"name": "create_fabric_ontology_knowledge_source", "status": "ok"})
    else:
        smoke["steps"].append({
            "name": "create_fabric_ontology_knowledge_source",
            "status": "skipped",
            "reason": f"deployment mode is {settings['DEPLOYMENT_MODE']} and Fabric IDs are {'configured' if fabric_configured(settings) else 'not configured'}",
        })

    search_request(method="PUT", endpoint=endpoint, api_key=search_api_key, api_version=api_version, path=f"/knowledgebases/{settings['MCP_ONLY_KNOWLEDGE_BASE_NAME']}", body=mcp_only_kb)
    smoke["steps"].append({"name": "create_mcp_only_kb", "status": "ok"})

    search_request(method="PUT", endpoint=endpoint, api_key=search_api_key, api_version=api_version, path=f"/knowledgebases/{settings['KNOWLEDGE_BASE_NAME']}", body=combined_kb)
    smoke["steps"].append({"name": "create_combined_kb_skeleton", "status": "ok"})

    index_name = settings["AIRLINE_OPS_INDEX_NAME"]
    search_request(method="PUT", endpoint=endpoint, api_key=search_api_key, api_version=api_version, path=f"/indexes/{index_name}", body=create_regulatory_index_payload(index_name))
    search_request(method="POST", endpoint=endpoint, api_key=search_api_key, api_version=api_version, path=f"/indexes/{index_name}/docs/index", body={"value": load_regulatory_documents()})
    smoke["steps"].append({"name": "upload_airline_ops_regulatory_index", "status": "ok"})

    retrieve_body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What must be configured to create an Azure AI Search MCP Server knowledge source?",
                    }
                ],
            }
        ],
        "includeActivity": True,
        "knowledgeSourceParams": [
            {
                "kind": "mcpServer",
                "knowledgeSourceName": settings["MCP_KNOWLEDGE_SOURCE_NAME"],
                "includeReferences": True,
                "includeReferenceSourceData": True,
            }
        ],
        "outputMode": "answerSynthesis",
        "retrievalReasoningEffort": {"kind": "low"},
        "maxRuntimeInSeconds": 60,
    }
    response = search_request(method="POST", endpoint=endpoint, api_key=search_api_key, api_version=api_version, path=f"/knowledgebases/{settings['MCP_ONLY_KNOWLEDGE_BASE_NAME']}/retrieve", body=retrieve_body)
    smoke["mcpRetrieve"] = {
        "activity": summarize_activity(response),
        "references": summarize_references(response),
    }

    summary_path = write_summary(settings, smoke)
    print(f"Postprovision complete. Summary written to {summary_path}")


if __name__ == "__main__":
    main()
