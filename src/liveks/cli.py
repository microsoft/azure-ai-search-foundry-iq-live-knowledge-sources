"""LiveKS plan-first command line interface."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from . import __version__
from .config import (
    ConfigError,
    ResolvedConfig,
    available_profiles,
    find_config,
    parse_legacy_env,
    profile_table,
    resolve_config,
    unflatten,
    write_lock,
    write_user_config,
)
from .evidence import generated_at, repository_revision, runtime_summary, sha256_file, write_json
from .mcp_search_index import (
    build_payloads as build_mcp_search_index_payloads,
    redacted_payloads as redact_mcp_search_index_payloads,
)
from .runtime import (
    CommandRunner,
    EnvironmentOperationLock,
    http_json,
    http_mcp_json,
    parse_azd_values,
    parse_version,
    reset_retry_telemetry,
    retry_telemetry_summary,
)
from .search_index import (
    acquire_bearer_token as acquire_search_bearer_token,
    build_payloads as build_search_index_payloads,
    inspect_index,
    object_path as search_object_path,
    reference_source_data_text,
    request as search_index_request,
    response_text as search_index_response_text,
)


ROOT = Path(__file__).resolve().parents[2]
LIVE_PROFILES = {"search-index", "mcp-search-index", "mcp-only", "byo-fabric", "full"}
DIRECT_SEARCH_PROFILES = {"search-index", "mcp-search-index"}
MCP_SEARCH_INDEX_MANAGED_KEYS = {
    "searchIndexKnowledgeSource",
    "mcpKnowledgeSource",
    "combinedKnowledgeBase",
}
ACTIVE_OWNERSHIP_STATUSES = {
    "deployment-in-progress",
    "deployed",
    "verification-failed",
    "deployment-failed",
    "cleanup-incomplete",
}
SAFE_REPLANNABLE_STATUSES = {
    "planned",
    "plan-failed",
    "confirmation-required",
    "cleaned",
    "destroyed",
}
GENERATED_FABRIC_AZD_KEYS = (
    "FABRIC_CAPACITY_ID",
    "FABRIC_CAPACITY_ARM_ID",
    "FABRIC_WORKSPACE_ID",
    "FABRIC_LAKEHOUSE_ID",
    "FABRIC_ONTOLOGY_ID",
)


def envelope(command: str, status: str, **values: Any) -> dict[str, Any]:
    return {"schemaVersion": 2, "command": command, "status": status, **values}


def emit(report: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    command = report.get("command", "liveks")
    print(f"LiveKS {command}: {str(report.get('status', 'unknown')).upper()}")
    if report.get("profile"):
        print(f"Profile: {report['profile']}")
    if report.get("environment"):
        print(f"Environment: {report['environment']}")
    for check in report.get("checks", []):
        print(f"[{str(check.get('status', 'unknown')).upper()}] {check.get('name')}: {check.get('message', '')}")
    for resource in report.get("resources", []):
        print(f"- {resource}")
    if report.get("cost"):
        print(f"Cost: {report['cost']}")
    if report.get("estimatedDuration"):
        print(f"Estimated duration: {report['estimatedDuration']}")
    for action in report.get("nextActions", []):
        print(f"Next: {action}")
    for artifact in report.get("artifacts", []):
        print(f"Artifact: {artifact}")


def _check(name: str, status: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "message": message, **extra}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _operation_lock_path(config: ResolvedConfig) -> Path:
    return ROOT / ".liveks" / f"{config.environment}.operation.lock"


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|").strip()


def _sanitized_e2e_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for phase_name in ("up", "down"):
        phase = report.get("phases", {}).get(phase_name)
        if not isinstance(phase, dict):
            continue
        for check in phase.get("checks", []):
            if not isinstance(check, dict):
                continue
            safe_check: dict[str, Any] = {
                "phase": phase_name,
                "name": str(check.get("name", "unknown")),
                "status": str(check.get("status", "unknown")),
            }
            source_types = check.get("sourceTypes")
            if isinstance(source_types, list):
                safe_check["sourceTypes"] = sorted(
                    {str(item) for item in source_types if item in {"fabricOntology", "mcpServer", "searchIndex"}}
                )
            evidence_count = check.get("evidenceCount")
            if isinstance(evidence_count, int) and evidence_count >= 0:
                safe_check["evidenceCount"] = evidence_count
            source_counts = check.get("sourceCounts")
            if isinstance(source_counts, dict):
                safe_check["sourceCounts"] = {
                    str(key): int(value)
                    for key, value in source_counts.items()
                    if key in {"fabricOntology", "mcpServer", "searchIndex"}
                    and isinstance(value, int)
                    and value >= 0
                }
            checks.append(safe_check)
    return checks


def _write_e2e_evidence_capsule(
    config: ResolvedConfig,
    report: dict[str, Any],
    *,
    cleanup_requested: bool,
    source_report: Path,
    json_path: Path,
    markdown_path: Path,
) -> None:
    checks = _sanitized_e2e_checks(report)
    status_counts: dict[str, int] = {}
    for check in checks:
        status = str(check["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    successful_names = {check["name"] for check in checks if check["status"] == "pass"}
    source_types: list[str] = []
    if "fabric-retrieve" in successful_names:
        source_types.append("fabricOntology")
    if "mcp-retrieve" in successful_names:
        source_types.append("mcpServer")
    if "search-index-retrieve" in successful_names:
        source_types.append("searchIndex")
    mcp_status = next(
        (str(check["status"]) for check in checks if check["name"] == "knowledge-base-mcp"),
        "not-run",
    )
    combined_status = next(
        (str(check["status"]) for check in checks if check["name"] == "combined-retrieve"),
        "not-run",
    )

    capsule = {
        "schemaVersion": 1,
        "kind": "liveks-evidence-capsule",
        "scope": "live-e2e-sanitized",
        "status": str(report.get("status", "unknown")),
        "generatedAt": generated_at(),
        "repositoryRevision": repository_revision(ROOT),
        "profile": config.profile,
        "command": {
            "entryPoint": "./liveks e2e",
            "environment": "redacted",
            "cleanupRequested": cleanup_requested,
        },
        "runtime": runtime_summary(),
        "declaredContracts": (
            {
                "searchIndexKnowledgeSource": "2026-04-01-stable",
                "retrieval": "minimal-extractive",
                "existingIndexOwnership": "reuse",
            }
            if config.profile == "search-index"
            else {
                "searchIndexKnowledgeSource": "2026-04-01-stable",
                "mcpServerKnowledgeSource": "2026-05-01-preview",
                "knowledgeBase": "2026-05-01-preview",
                "existingIndexOwnership": "reuse",
                "liveGrounding": "protected-integration",
            }
            if config.profile == "mcp-search-index"
            else {
                "mcpServerKnowledgeSourceTransport": "remote-https",
                "knowledgeBaseMcpTransport": "stateless-json-rpc-http",
                "liveGrounding": "protected-integration",
            }
        ),
        "observedEvidence": {
            "sourceTypes": sorted(source_types),
            "knowledgeBaseMcp": mcp_status,
            "combinedRouting": combined_status,
        },
        "summary": {
            "checkCount": len(checks),
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "assertions": checks,
        "sourceReport": {
            "kind": "e2e-report",
            "sha256": sha256_file(source_report),
        },
        "privacy": {
            "environmentIncluded": False,
            "messagesIncluded": False,
            "resourceIdentifiersIncluded": False,
            "serviceEndpointsIncluded": False,
            "rawResponsesIncluded": False,
            "credentialsIncluded": False,
        },
    }
    write_json(json_path, capsule)

    revision = str(capsule["repositoryRevision"])
    lines = [
        "# LiveKS Evidence Capsule",
        "",
        "> Ignored, allowlist-sanitized evidence. Review before sharing.",
        "",
        f"- Status: `{str(capsule['status']).upper()}`",
        f"- Profile: `{config.profile}`",
        f"- Repository revision: `{revision}`",
        f"- Cleanup requested: `{'yes' if cleanup_requested else 'no'}`",
        f"- Source types proved: `{', '.join(sorted(source_types)) or 'none'}`",
        f"- Knowledge Base MCP: `{mcp_status}`",
        f"- Source report SHA-256: `{capsule['sourceReport']['sha256']}`",
        "",
        "| Phase | Status | Assertion |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{check['phase']}` | `{str(check['status']).upper()}` | {check['name']} |" for check in checks)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_e2e_reports(config: ResolvedConfig, report: dict[str, Any], *, cleanup_requested: bool) -> list[str]:
    """Persist ignored machine and maintainer reports for the complete lifecycle."""
    report_dir = ROOT / "deployments" / config.environment
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "e2e-report.json"
    markdown_path = report_dir / "test-report.md"
    capsule_json_path = report_dir / "evidence-capsule.json"
    capsule_markdown_path = report_dir / "evidence-capsule.md"
    artifacts = [
        _display_path(json_path),
        _display_path(markdown_path),
        _display_path(capsule_json_path),
        _display_path(capsule_markdown_path),
    ]
    report["artifacts"] = list(dict.fromkeys(report.get("artifacts", []) + artifacts))
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    status_map = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "warn": "SKIP", "unknown": "SKIP"}
    checks: list[tuple[str, str, str]] = []
    for phase_name in ("up", "down"):
        phase = report.get("phases", {}).get(phase_name)
        if not isinstance(phase, dict):
            continue
        for check in phase.get("checks", []):
            if not isinstance(check, dict):
                continue
            status = status_map.get(str(check.get("status", "unknown")).lower(), "SKIP")
            checks.append((status, _markdown_cell(check.get("name")), _markdown_cell(check.get("message"))))

    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        "# LiveKS E2E Test Report",
        "",
        "> Ignored local evidence. Sanitize before sharing.",
        "",
        f"- Deployment mode: `{config.profile}`",
        f"- Location: `{_markdown_cell(config.get('azure.location'))}`",
        f"- Fabric location: `{_markdown_cell(config.get('fabric.location'))}`",
        f"- Cleanup requested: `{'yes' if cleanup_requested else 'no'}`",
        f"- Generated: `{generated}`",
        f"- Hosting mode: `{_markdown_cell(config.get('azure.hosting_mode'))}`",
        f"- Overall status: `{str(report.get('status', 'unknown')).upper()}`",
        "",
        "| Status | Check | Note |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{status}` | {name} | {message} |" for status, name, message in checks)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_e2e_evidence_capsule(
        config,
        report,
        cleanup_requested=cleanup_requested,
        source_report=json_path,
        json_path=capsule_json_path,
        markdown_path=capsule_markdown_path,
    )
    return artifacts


def _command_version(command: list[str], config: ResolvedConfig) -> tuple[int, str]:
    result = CommandRunner(root=ROOT, env=config.child_env(), quiet=True).run(command)
    return result.returncode, result.stdout.strip()


def _search_index_doctor_checks(
    config: ResolvedConfig,
    *,
    api_version: str | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not shutil.which("az"):
        return checks
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=True)
    account = runner.run(["az", "account", "show", "-o", "json"])
    account_data: dict[str, Any] = {}
    if account.returncode == 0:
        try:
            account_data = json.loads(account.stdout)
        except json.JSONDecodeError:
            pass
    checks.append(
        _check(
            "azure-login",
            "pass" if account_data.get("id") else "fail",
            "Azure CLI account is active" if account_data.get("id") else "Run az login for the target tenant",
        )
    )

    configured_tenant = str(config.get("azure.tenant_id", ""))
    configured_subscription = str(config.get("azure.subscription_id", ""))
    if configured_tenant:
        matches = configured_tenant == str(account_data.get("tenantId", ""))
        checks.append(_check("tenant-match", "pass" if matches else "fail", "Configured tenant matches Azure CLI" if matches else "Configured tenant differs from Azure CLI"))
    if configured_subscription:
        matches = configured_subscription == str(account_data.get("id", ""))
        checks.append(_check("subscription-match", "pass" if matches else "fail", "Configured subscription matches Azure CLI" if matches else "Configured subscription differs from Azure CLI"))
    if not account_data.get("id"):
        return checks

    try:
        token = acquire_search_bearer_token(runner)
        checks.append(_check("search-auth", "pass", "A transient Azure AI Search bearer token was acquired."))
        status_code, index = search_index_request(
            config,
            token,
            method="GET",
            path=search_object_path("indexes", str(config.get("search.index_name"))),
            api_version=api_version,
            timeout=30,
        )
    except Exception:
        checks.append(_check("search-index", "fail", "The configured Search index could not be read with the current identity."))
        return checks

    index_ready = status_code == 200
    checks.append(
        _check(
            "search-index",
            "pass" if index_ready else "fail",
            "The existing Search index is readable."
            if index_ready
            else f"Azure AI Search returned HTTP {status_code} for the configured index.",
        )
    )
    if index_ready:
        checks.extend(_check(name, status, message) for name, status, message in inspect_index(index, config))
    return checks


def doctor_report(config: ResolvedConfig, *, cloud: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    required_tools = list(config.manifest.get("required_tools", []))
    for tool in required_tools:
        if tool == "python3":
            ready = sys.version_info >= (3, 11)
            checks.append(_check("python", "pass" if ready else "fail", f"{sys.version.split()[0]} (requires 3.11+)"))
            continue
        path = shutil.which(tool)
        checks.append(_check(f"tool:{tool}", "pass" if path else "fail", path or f"{tool} is not installed"))

    if "azd" in required_tools and shutil.which("azd"):
        code, output = _command_version(["azd", "version"], config)
        version = parse_version(output)
        ready = code == 0 and version >= (1, 27, 0)
        checks.append(_check("azd-version", "pass" if ready else "fail", output.splitlines()[0] if output else "unknown; requires 1.27+"))
    if "node" in required_tools and shutil.which("node"):
        code, output = _command_version(["node", "--version"], config)
        ready = code == 0 and parse_version(output) >= (22, 0, 0)
        checks.append(_check("node-version", "pass" if ready else "fail", f"{output} (requires 22+)"))

    if config.profile in DIRECT_SEARCH_PROFILES and cloud:
        checks.extend(
            _search_index_doctor_checks(
                config,
                api_version=(
                    str(config.get("search.index_api_version"))
                    if config.profile == "mcp-search-index"
                    else None
                ),
            )
        )
        if config.profile == "mcp-search-index":
            checks.append(
                _check(
                    "openai-runtime-access",
                    "unknown",
                    "Search managed identity access to the reused Azure OpenAI deployment is proved only by live retrieve.",
                )
            )
    elif config.profile in LIVE_PROFILES and cloud:
        runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=True)
        account = runner.run(["az", "account", "show", "-o", "json"])
        account_data: dict[str, Any] = {}
        if account.returncode == 0:
            try:
                account_data = json.loads(account.stdout)
            except json.JSONDecodeError:
                pass
        checks.append(_check("azure-login", "pass" if account_data.get("id") else "fail", "Azure CLI account is active" if account_data.get("id") else "Run az login for the target tenant"))
        azd_auth = runner.run(["azd", "auth", "login", "--check-status", "--no-prompt"])
        checks.append(_check("azd-login", "pass" if azd_auth.returncode == 0 else "fail", "Azure Developer CLI authentication is active" if azd_auth.returncode == 0 else "Run azd auth login"))

        configured_tenant = str(config.get("azure.tenant_id", ""))
        configured_subscription = str(config.get("azure.subscription_id", ""))
        actual_tenant = str(account_data.get("tenantId", ""))
        actual_subscription = str(account_data.get("id", ""))
        if configured_tenant:
            checks.append(_check("tenant-match", "pass" if configured_tenant == actual_tenant else "fail", "Configured tenant matches Azure CLI" if configured_tenant == actual_tenant else "Configured tenant differs from Azure CLI"))
        if configured_subscription:
            checks.append(_check("subscription-match", "pass" if configured_subscription == actual_subscription else "fail", "Configured subscription matches Azure CLI" if configured_subscription == actual_subscription else "Configured subscription differs from Azure CLI"))

        providers = ["Microsoft.Search", "Microsoft.CognitiveServices", "Microsoft.Storage", "Microsoft.Web"]
        if config.profile == "full":
            providers.append("Microsoft.Fabric")
        for namespace in providers:
            result = runner.run(["az", "provider", "show", "--namespace", namespace, "--query", "registrationState", "-o", "tsv"])
            state = result.stdout.strip()
            checks.append(_check(f"provider:{namespace}", "pass" if result.returncode == 0 and state == "Registered" else "fail", state or "not registered"))

        location = str(config.get("azure.location"))
        sku_probe = runner.run(["az", "cognitiveservices", "account", "list-skus", "--kind", "OpenAI", "--location", location, "-o", "json"])
        model_region = "pass" if sku_probe.returncode == 0 and sku_probe.stdout.strip() not in {"", "[]"} else "warn"
        checks.append(_check("openai-region", model_region, f"OpenAI account SKU probe for {location}" if model_region == "pass" else f"Could not confirm OpenAI SKU availability in {location}; azd preview remains authoritative"))
        checks.append(_check("search-preview-region", "warn", f"Search agentic preview availability for {location} is verified by azd preview and live E2E, not inferred from account metadata"))
        if config.profile == "byo-fabric":
            token_result = runner.run(
                ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com", "--query", "accessToken", "-o", "tsv"]
            )
            fabric_token = token_result.stdout.strip()
            checks.append(
                _check(
                    "fabric-api-token",
                    "pass" if fabric_token else "fail",
                    "Fabric API token acquired transiently" if fabric_token else "Unable to acquire a Fabric API token for the configured tenant",
                )
            )
            if fabric_token:
                fabric_base = "https://api.fabric.microsoft.com/v1"
                fabric_headers = {"Authorization": f"Bearer {fabric_token}"}
                fabric_reads = [
                    ("fabric-workspace", f"{fabric_base}/workspaces/{config.get('fabric.workspace_id')}"),
                    (
                        "fabric-ontology",
                        f"{fabric_base}/workspaces/{config.get('fabric.workspace_id')}/items/{config.get('fabric.ontology_id')}",
                    ),
                ]
                for check_name, url in fabric_reads:
                    try:
                        status_code, _ = http_json(url, headers=fabric_headers, attempts=2, delay_seconds=2, timeout=30)
                        ready = status_code == 200
                        status = "pass" if ready else "warn" if status_code == 429 else "fail"
                        message = "Configured Fabric asset is readable" if ready else f"Fabric API returned HTTP {status_code}"
                    except Exception as error:
                        status = "fail"
                        message = f"Fabric API read failed: {error}"
                    checks.append(_check(check_name, status, message))
        if config.profile == "full":
            checks.append(_check("fabric-quota", "unknown", f"Fabric {config.get('fabric.capacity_sku')} quota in {config.get('fabric.location')} cannot be proven without ARM validation; explicit acceptance is required"))

    statuses = [check["status"] for check in checks]
    status = "fail" if "fail" in statuses else "warn" if any(item in {"warn", "unknown"} for item in statuses) else "pass"
    return envelope(
        "doctor",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        nextActions=["Resolve failed checks before running liveks up"] if status == "fail" else [f"Run ./liveks plan --profile {config.profile} --env {config.environment}"],
    )


def _search_index_lock_state(
    config: ResolvedConfig,
) -> tuple[dict[str, str], dict[str, str], bool, str]:
    try:
        lock = _load_lock(config.environment)
    except ConfigError as error:
        return {}, {}, False, f"invalid environment lock: {error}"
    if lock is None:
        return {}, {}, True, "environment lock is not present"

    matches = (
        lock.get("profile") == config.profile
        and lock.get("environment") == config.environment
        and lock.get("configDigest") == config.config_digest
    )
    managed = lock.get("managedObjects")
    all_managed = (
        {str(key): str(value) for key, value in managed.items() if value}
        if isinstance(managed, dict)
        else {}
    )
    managed_objects = {
        str(key): str(value)
        for key, value in managed.items()
        if isinstance(managed, dict) and key in {"knowledgeSource", "knowledgeBase"} and value
    } if isinstance(managed, dict) else {}
    managed_etags = lock.get("managedObjectEtags")
    all_etags = (
        {str(key): str(value) for key, value in managed_etags.items() if value}
        if isinstance(managed_etags, dict)
        else {}
    )
    etags = (
        {
            str(key): str(value)
            for key, value in managed_etags.items()
            if key in {"knowledgeSource", "knowledgeBase"} and value
        }
        if isinstance(managed_etags, dict)
        else {}
    )
    if not matches and all_managed:
        return all_managed, all_etags, False, "environment lock does not match the resolved configuration"
    return (
        managed_objects,
        etags,
        matches,
        "matching environment lock" if matches else "environment lock does not match the resolved configuration",
    )


def _mcp_search_index_lock_state(
    config: ResolvedConfig,
) -> tuple[dict[str, str], dict[str, str], bool, str]:
    try:
        lock = _load_lock(config.environment)
    except ConfigError as error:
        return {}, {}, False, f"invalid environment lock: {error}"
    if lock is None:
        return {}, {}, True, "environment lock is not present"

    matches = (
        lock.get("profile") == config.profile
        and lock.get("environment") == config.environment
        and lock.get("configDigest") == config.config_digest
    )
    managed = lock.get("managedObjects")
    all_managed = (
        {str(key): str(value) for key, value in managed.items() if value}
        if isinstance(managed, dict)
        else {}
    )
    managed_objects = (
        {
            str(key): str(value)
            for key, value in managed.items()
            if key in MCP_SEARCH_INDEX_MANAGED_KEYS and value
        }
        if isinstance(managed, dict)
        else {}
    )
    managed_etags = lock.get("managedObjectEtags")
    all_etags = (
        {str(key): str(value) for key, value in managed_etags.items() if value}
        if isinstance(managed_etags, dict)
        else {}
    )
    etags = (
        {
            str(key): str(value)
            for key, value in managed_etags.items()
            if key in MCP_SEARCH_INDEX_MANAGED_KEYS and value
        }
        if isinstance(managed_etags, dict)
        else {}
    )
    if not matches and all_managed:
        return all_managed, all_etags, False, "environment lock does not match the resolved configuration"
    return (
        managed_objects,
        etags,
        matches,
        "matching environment lock" if matches else "environment lock does not match the resolved configuration",
    )


def _search_object_etag(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("@odata.etag") or payload.get("etag") or "")


def _environment_lock_conflict(config: ResolvedConfig) -> str | None:
    try:
        lock = _load_lock(config.environment)
    except ConfigError as error:
        return f"Invalid environment lock must be restored before planning: {error}"
    if lock is None:
        return None

    matches = (
        lock.get("profile") == config.profile
        and lock.get("environment") == config.environment
        and lock.get("configDigest") == config.config_digest
    )
    managed = lock.get("managedObjects")
    has_managed_objects = isinstance(managed, dict) and any(managed.values())
    status = str(lock.get("status") or "")
    if matches and config.profile in DIRECT_SEARCH_PROFILES:
        return None
    if has_managed_objects or status not in SAFE_REPLANNABLE_STATUSES:
        return (
            "An active or unrecognized environment lock must be cleaned up with its original "
            "profile and configuration before planning."
        )
    if matches:
        return None
    return None


def _generic_cleanup_lock(config: ResolvedConfig) -> tuple[dict[str, Any] | None, str | None]:
    try:
        lock = _load_lock(config.environment)
    except ConfigError as error:
        return None, f"Invalid environment lock: {error}"
    if lock is None:
        return None, None
    if lock.get("profile") != config.profile or lock.get("environment") != config.environment:
        return None, "Environment lock profile or environment does not match the requested cleanup."
    authored_digest = str(lock.get("authoredConfigDigest") or "")
    if authored_digest:
        accepted_digests = {
            str(value)
            for value in (lock.get("configDigest"), authored_digest)
            if value
        }
        if config.config_digest not in accepted_digests:
            return None, "Environment lock configuration digest does not match the requested cleanup."
    status = str(lock.get("status") or "")
    if status and status not in ACTIVE_OWNERSHIP_STATUSES:
        return None, "Environment lock does not record an active or partial deployment to clean up."
    return lock, None


def _failed_up_started_mutation(config: ResolvedConfig) -> bool:
    lock, error = _generic_cleanup_lock(config)
    if config.profile in DIRECT_SEARCH_PROFILES:
        try:
            direct_lock = _load_lock(config.environment)
        except ConfigError:
            return False
        return bool(
            direct_lock
            and direct_lock.get("profile") == config.profile
            and direct_lock.get("environment") == config.environment
            and direct_lock.get("configDigest") == config.config_digest
            and str(direct_lock.get("status") or "") in ACTIVE_OWNERSHIP_STATUSES
        )
    return (
        lock is not None
        and error is None
        and str(lock.get("status") or "") in ACTIVE_OWNERSHIP_STATUSES
    )


def _preserved_cleanup_metadata(lock: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(lock, dict):
        return {}
    return {
        key: lock[key]
        for key in ("authoredConfigDigest", "resourceGroupPreexisting")
        if key in lock
    }


def _payload_is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _payload_is_subset(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_payload_is_subset(left, right) for left, right in zip(expected, actual))
        )
    return expected == actual


def _mcp_search_index_contracts(config: ResolvedConfig) -> list[dict[str, str]]:
    stable = str(config.get("search.index_api_version"))
    preview = str(config.get("search.preview_api_version"))
    return [
        {
            "kind": "searchIndex",
            "name": str(config.get("search.index_name")),
            "apiVersion": stable,
            "ownership": "reuse",
        },
        {
            "kind": "searchIndexKnowledgeSource",
            "name": str(config.get("search.index_knowledge_source_name")),
            "apiVersion": stable,
            "ownership": "create",
        },
        {
            "kind": "mcpServerKnowledgeSource",
            "name": str(config.get("search.mcp_knowledge_source_name")),
            "apiVersion": preview,
            "ownership": "create",
        },
        {
            "kind": "knowledgeBase",
            "name": str(config.get("search.combined_knowledge_base_name")),
            "apiVersion": preview,
            "ownership": "create",
        },
        {
            "kind": "azureOpenAI",
            "name": str(config.get("openai.deployment_name")),
            "apiVersion": "external-existing-deployment",
            "ownership": "reuse",
        },
    ]


def _mcp_search_index_cleanup_order(config: ResolvedConfig) -> list[dict[str, str]]:
    return [
        {
            "action": "delete",
            "kind": "knowledgeBase",
            "name": str(config.get("search.combined_knowledge_base_name")),
            "apiVersion": str(config.get("search.preview_api_version")),
        },
        {
            "action": "delete",
            "kind": "mcpServerKnowledgeSource",
            "name": str(config.get("search.mcp_knowledge_source_name")),
            "apiVersion": str(config.get("search.preview_api_version")),
        },
        {
            "action": "delete",
            "kind": "searchIndexKnowledgeSource",
            "name": str(config.get("search.index_knowledge_source_name")),
            "apiVersion": str(config.get("search.index_api_version")),
        },
        {
            "action": "preserve",
            "kind": "searchIndex",
            "name": str(config.get("search.index_name")),
            "apiVersion": str(config.get("search.index_api_version")),
        },
        {
            "action": "preserve",
            "kind": "azureOpenAI",
            "name": str(config.get("openai.deployment_name")),
            "apiVersion": "external-existing-deployment",
        },
    ]


def _search_index_plan_report(config: ResolvedConfig, checks: list[dict[str, Any]]) -> dict[str, Any]:
    managed, managed_etags, lock_matches, lock_message = _search_index_lock_state(config)
    if managed and not lock_matches:
        checks.append(
            _check(
                "environment-lock",
                "fail",
                "A different configuration owns generated Search objects; use its original ledger for cleanup before planning again.",
            )
        )
        return envelope(
            "plan",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=checks,
            resources=config.manifest.get("resources", []),
            nextActions=["Restore the original environment ledger and run liveks down."],
        )
    checks.append(_check("environment-lock", "pass", lock_message))

    payloads = build_search_index_payloads(
        config,
        query="What information is available in this index?",
    )
    knowledge_source = payloads["knowledgeSource"]
    knowledge_base = payloads["knowledgeBase"]
    retrieve = payloads["retrieve"]
    payload_ready = (
        knowledge_source.get("kind") == "searchIndex"
        and "searchIndexParameters" in knowledge_source
        and not {"models", "outputMode", "retrievalReasoningEffort"}.intersection(knowledge_base)
        and "intents" in retrieve
        and "messages" not in retrieve
    )
    checks.append(
        _check(
            "stable-payload-contract",
            "pass" if payload_ready else "fail",
            "Search Index KS, extractive Knowledge Base, and intents retrieve payloads match the stable lane."
            if payload_ready
            else "The stable payload contract is internally inconsistent.",
        )
    )

    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=True)
    try:
        token = acquire_search_bearer_token(runner)
        names = {
            "knowledgeSource": ("knowledgesources", str(config.get("search.index_knowledge_source_name"))),
            "knowledgeBase": ("knowledgebases", str(config.get("search.index_knowledge_base_name"))),
        }
        for label, (kind, name) in names.items():
            status_code, existing = search_index_request(
                config,
                token,
                method="GET",
                path=search_object_path(kind, name),
                timeout=30,
            )
            remote_etag = _search_object_etag(existing)
            owned = (
                managed.get(label) == name
                and bool(managed_etags.get(label))
                and managed_etags.get(label) == remote_etag
            )
            collision = status_code == 200 and not owned
            ready = status_code == 404 or (status_code == 200 and owned)
            checks.append(
                _check(
                    f"{label}-name",
                    "pass" if ready else "fail",
                    "Name is available."
                    if status_code == 404
                    else "Existing object and ETag are owned by this environment."
                    if ready
                    else "An existing unowned object uses this name; choose another environment or explicit name.",
                )
            )
    except Exception:
        checks.append(_check("search-object-collision-check", "fail", "Existing Search object names could not be checked."))

    output_dir = ROOT / ".deployment" / config.environment
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_path = output_dir / "search-index-plan.json"
    write_json(
        payload_path,
        {
            "schemaVersion": 1,
            "apiVersion": config.get("search.api_version"),
            "payloads": payloads,
            "ownership": config.ownership(),
        },
    )
    status = "fail" if any(check["status"] == "fail" for check in checks) else "warn" if any(check["status"] in {"warn", "unknown"} for check in checks) else "pass"
    lock = write_lock(
        config,
        status="planned" if status != "fail" else "plan-failed",
        extra={
            "checks": checks,
            "resources": config.manifest.get("resources", []),
            "estimatedDuration": config.manifest.get("estimated_duration"),
            "cost": config.manifest.get("cost"),
            "managedObjects": managed,
            "managedObjectEtags": managed_etags,
        },
    )
    return envelope(
        "plan",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        resources=config.manifest.get("resources", []),
        cost=config.manifest.get("cost"),
        estimatedDuration=config.manifest.get("estimated_duration"),
        ownership=config.ownership(),
        artifacts=[_display_path(lock), _display_path(payload_path)],
        nextActions=[f"Run ./liveks up --env {config.environment}" if status != "fail" else "Fix plan failures before creating Search objects"],
    )


def _mcp_search_index_plan_report(config: ResolvedConfig, checks: list[dict[str, Any]]) -> dict[str, Any]:
    managed, managed_etags, lock_matches, lock_message = _mcp_search_index_lock_state(config)
    contracts = _mcp_search_index_contracts(config)
    cleanup_order = _mcp_search_index_cleanup_order(config)
    if managed and not lock_matches:
        checks.append(
            _check(
                "environment-lock",
                "fail",
                "A different configuration owns generated Search objects; restore its ledger and clean it up first.",
            )
        )
        return envelope(
            "plan",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=checks,
            resources=config.manifest.get("resources", []),
            contracts=contracts,
            cleanupOrder=cleanup_order,
            nextActions=["Restore the original environment ledger and run liveks down."],
        )
    checks.append(_check("environment-lock", "pass", lock_message))

    payloads = build_mcp_search_index_payloads(
        config,
        index_query="Inspect the existing index.",
        mcp_query="Find current Azure AI Search Knowledge Base guidance.",
        combined_query="Use indexed domain evidence and current Microsoft Learn implementation guidance.",
    )
    knowledge_base = payloads["knowledgeBase"]
    source_names = {
        str(item.get("name"))
        for item in knowledge_base.get("knowledgeSources", [])
        if isinstance(item, dict) and item.get("name")
    }
    retrieve = payloads["retrieve"]
    payload_ready = (
        payloads["searchIndexKnowledgeSource"].get("kind") == "searchIndex"
        and payloads["mcpKnowledgeSource"].get("kind") == "mcpServer"
        and source_names
        == {
            str(config.get("search.index_knowledge_source_name")),
            str(config.get("search.mcp_knowledge_source_name")),
        }
        and bool(knowledge_base.get("models"))
        and knowledge_base.get("outputMode") == "answerSynthesis"
        and knowledge_base.get("retrievalReasoningEffort") == {"kind": "low"}
        and all("messages" in request and "intents" not in request for request in retrieve.values())
        and retrieve["searchIndex"]["knowledgeSourceParams"][0]["kind"] == "searchIndex"
        and retrieve["mcp"]["knowledgeSourceParams"][0]["kind"] == "mcpServer"
    )
    checks.append(
        _check(
            "version-separated-payload-contract",
            "pass" if payload_ready else "fail",
            "GA Search Index KS and preview MCP/KB/retrieve request shapes remain separate."
            if payload_ready
            else "The combined profile payloads mix or omit required stable and preview properties.",
        )
    )

    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=True)
    try:
        token = acquire_search_bearer_token(runner)
        objects = [
            (
                "searchIndexKnowledgeSource",
                "knowledgesources",
                str(config.get("search.index_knowledge_source_name")),
                str(config.get("search.index_api_version")),
            ),
            (
                "mcpKnowledgeSource",
                "knowledgesources",
                str(config.get("search.mcp_knowledge_source_name")),
                str(config.get("search.preview_api_version")),
            ),
            (
                "combinedKnowledgeBase",
                "knowledgebases",
                str(config.get("search.combined_knowledge_base_name")),
                str(config.get("search.preview_api_version")),
            ),
        ]
        for label, kind, name, api_version in objects:
            status_code, existing = search_index_request(
                config,
                token,
                method="GET",
                path=search_object_path(kind, name),
                api_version=api_version,
                timeout=30,
            )
            remote_etag = _search_object_etag(existing)
            owned = (
                managed.get(label) == name
                and bool(managed_etags.get(label))
                and managed_etags.get(label) == remote_etag
            )
            collision = status_code == 200 and not owned
            ready = status_code == 404 or (status_code == 200 and owned)
            checks.append(
                _check(
                    f"{label}-name",
                    "pass" if ready else "fail",
                    "Name is available."
                    if status_code == 404
                    else "Existing object and ETag are owned by this environment."
                    if ready
                    else "An existing unowned object uses this name; choose another explicit name.",
                )
            )
    except Exception:
        checks.append(
            _check(
                "search-object-collision-check",
                "fail",
                "Existing Search object names could not be checked with their pinned API versions.",
            )
        )

    output_dir = ROOT / ".deployment" / config.environment
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_path = output_dir / "mcp-search-index-plan.json"
    write_json(
        payload_path,
        {
            "schemaVersion": 1,
            "contracts": contracts,
            "payloads": redact_mcp_search_index_payloads(payloads),
            "ownership": config.ownership(),
            "cleanupOrder": cleanup_order,
        },
    )
    status = "fail" if any(check["status"] == "fail" for check in checks) else "warn" if any(check["status"] in {"warn", "unknown"} for check in checks) else "pass"
    lock = write_lock(
        config,
        status="planned" if status != "fail" else "plan-failed",
        extra={
            "checks": checks,
            "resources": config.manifest.get("resources", []),
            "estimatedDuration": config.manifest.get("estimated_duration"),
            "cost": config.manifest.get("cost"),
            "managedObjects": managed,
            "managedObjectEtags": managed_etags,
            "contracts": contracts,
            "cleanupOrder": cleanup_order,
        },
    )
    return envelope(
        "plan",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        resources=config.manifest.get("resources", []),
        cost=config.manifest.get("cost"),
        estimatedDuration=config.manifest.get("estimated_duration"),
        ownership=config.ownership(),
        contracts=contracts,
        cleanupOrder=cleanup_order,
        artifacts=[_display_path(lock), _display_path(payload_path)],
        nextActions=[f"Run ./liveks up --env {config.environment}" if status != "fail" else "Fix plan failures before creating Search objects"],
    )


def plan_report(
    config: ResolvedConfig,
    *,
    quiet: bool = True,
    skip_app_build: bool = False,
    skip_dry_run: bool = False,
    operation_locked: bool = False,
) -> dict[str, Any]:
    if not operation_locked:
        try:
            with EnvironmentOperationLock(_operation_lock_path(config)):
                return plan_report(
                    config,
                    quiet=quiet,
                    skip_app_build=skip_app_build,
                    skip_dry_run=skip_dry_run,
                    operation_locked=True,
                )
        except RuntimeError as error:
            return envelope(
                "plan",
                "fail",
                profile=config.profile,
                environment=config.environment,
                checks=[_check("operation-lock", "fail", str(error))],
            )
    lock_conflict = _environment_lock_conflict(config)
    if lock_conflict:
        return envelope(
            "plan",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("environment-lock", "fail", lock_conflict)],
            resources=config.manifest.get("resources", []),
            nextActions=["Restore the original ledger and run liveks down before reusing this environment name."],
        )
    doctor = doctor_report(config, cloud=config.profile in LIVE_PROFILES)
    checks = list(doctor["checks"])
    if doctor["status"] == "fail":
        return envelope("plan", "fail", profile=config.profile, environment=config.environment, checks=checks, resources=config.manifest.get("resources", []), nextActions=["Resolve doctor failures and rerun plan"])

    if config.profile == "offline":
        lock = write_lock(config, status="planned", extra={"checks": checks})
        return envelope("plan", "pass", profile=config.profile, environment=config.environment, checks=checks, resources=[], cost=config.manifest.get("cost"), estimatedDuration=config.manifest.get("estimated_duration"), artifacts=[_display_path(lock)], nextActions=["Run ./liveks try"])

    if config.profile == "search-index":
        return _search_index_plan_report(config, checks)
    if config.profile == "mcp-search-index":
        return _mcp_search_index_plan_report(config, checks)

    output_dir = ROOT / ".deployment" / config.environment
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    commands = [("bicep-build", ["az", "bicep", "build", "--file", "infra/main.bicep", "--outfile", str(output_dir / "main.json")])]
    if not skip_dry_run:
        commands.append(("payload-dry-run", [sys.executable, "scripts/postprovision.py", "--dry-run"]))
    if not skip_app_build:
        commands.extend(
            [
                ("app-install", ["npm", "--prefix", "static-app", "ci"]),
                ("app-build", ["npm", "--prefix", "static-app", "run", "build"]),
            ]
        )
    for name, command in commands:
        result = runner.run(command)
        checks.append(_check(name, "pass" if result.returncode == 0 else "fail", "completed" if result.returncode == 0 else result.stdout[-1000:]))
        if result.returncode != 0:
            break
    status = "fail" if any(check["status"] == "fail" for check in checks) else "warn" if any(check["status"] in {"warn", "unknown"} for check in checks) else "pass"
    lock = write_lock(
        config,
        status="planned" if status != "fail" else "plan-failed",
        extra={
            "checks": checks,
            "resources": config.manifest.get("resources", []),
            "estimatedDuration": config.manifest.get("estimated_duration"),
            "cost": config.manifest.get("cost"),
        },
    )
    return envelope(
        "plan",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        resources=config.manifest.get("resources", []),
        cost=config.manifest.get("cost"),
        estimatedDuration=config.manifest.get("estimated_duration"),
        ownership=config.ownership(),
        artifacts=[_display_path(lock), _display_path(output_dir)],
        nextActions=[f"Run ./liveks up --env {config.environment}" if status != "fail" else "Fix plan failures before provisioning"],
    )


def _ensure_azd_environment(config: ResolvedConfig, runner: CommandRunner, *, reset_generated_fabric: bool = False) -> None:
    selected = runner.run(["azd", "env", "select", config.environment, "--no-prompt"])
    if selected.returncode != 0:
        runner.run(["azd", "env", "new", config.environment, "--no-prompt"], check=True)
    if reset_generated_fabric:
        for key in GENERATED_FABRIC_AZD_KEYS:
            runner.run(["azd", "env", "set", key, ""], check=True)
    if config.profile == "full" and not config.get("fabric.capacity_admin"):
        account = runner.run(["az", "account", "show", "--query", "user.name", "-o", "tsv"], check=True)
        config.values["fabric.capacity_admin"] = account.stdout.strip()
        config.sources["fabric.capacity_admin"] = "derived:azure-account"
    current_subscription = runner.run(["az", "account", "show", "--query", "id", "-o", "tsv"])
    if current_subscription.returncode == 0 and not config.get("azure.subscription_id"):
        config.values["azure.subscription_id"] = current_subscription.stdout.strip()
        config.sources["azure.subscription_id"] = "derived:azure-account"
    for key, value in sorted(config.azd_values().items()):
        runner.run(["azd", "env", "set", key, value], check=True)


def _confirm_up(config: ResolvedConfig, *, yes: bool, accept_fabric_capacity: bool, creates_capacity: bool = True) -> None:
    if config.profile == "full" and creates_capacity and not accept_fabric_capacity:
        raise PermissionError("full profile requires --accept-fabric-capacity because Fabric F2 is billable until cleanup.")
    if yes:
        return
    print(f"This will create resources for {config.environment} ({config.profile}).")
    print(config.manifest.get("cost", ""))
    expected = f"create {config.environment}"
    answer = input(f"Type '{expected}' to continue: ").strip()
    if answer != expected:
        raise PermissionError("Provisioning confirmation was not provided.")


def _search_index_up_report(
    config: ResolvedConfig,
    *,
    yes: bool,
    quiet: bool,
    query: str | None,
    expected_terms: list[str] | None,
) -> dict[str, Any]:
    if any(not str(term).strip() for term in expected_terms or []):
        return envelope(
            "up",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("runtime-input", "fail", "Expected terms must not be empty.")],
        )
    plan = plan_report(config, quiet=True, operation_locked=True)
    if plan["status"] == "fail":
        return {**plan, "command": "up"}

    checks = list(plan.get("checks", []))
    managed, managed_etags, lock_matches, _ = _search_index_lock_state(config)
    if not lock_matches:
        return envelope(
            "up",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("environment-lock", "fail", "The planned lock no longer matches the resolved configuration.")],
        )
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    payloads = build_search_index_payloads(config, query="What information is available in this index?")
    try:
        _confirm_up(config, yes=yes, accept_fabric_capacity=False, creates_capacity=False)
        token = acquire_search_bearer_token(runner)
        objects = [
            (
                "knowledgeSource",
                "knowledgesources",
                str(config.get("search.index_knowledge_source_name")),
                payloads["knowledgeSource"],
            ),
            (
                "knowledgeBase",
                "knowledgebases",
                str(config.get("search.index_knowledge_base_name")),
                payloads["knowledgeBase"],
            ),
        ]
        for label, kind, name, body in objects:
            existing_code, existing = search_index_request(
                config,
                token,
                method="GET",
                path=search_object_path(kind, name),
                timeout=30,
            )
            if existing_code == 200:
                remote_etag = _search_object_etag(existing)
                if (
                    managed.get(label) != name
                    or not managed_etags.get(label)
                    or managed_etags.get(label) != remote_etag
                ):
                    raise RuntimeError(f"Refusing to overwrite an unowned or changed {label}.")
                if not _payload_is_subset(body, existing):
                    raise RuntimeError(f"Owned {label} definition changed; run down before recreating it.")
                checks.append(_check(f"create-{label}", "pass", f"Owned {label} is already ready."))
                continue
            condition_headers = {
                "If-None-Match": "*",
                "Prefer": "return=representation",
            }
            if existing_code not in {200, 404}:
                raise RuntimeError(f"Unable to check the target {label} name (HTTP {existing_code}).")
            was_new = existing_code == 404
            if was_new:
                managed_etags.pop(label, None)
                managed[label] = name
                write_lock(
                    config,
                    status="deployment-in-progress",
                    extra={
                        "checks": checks,
                        "managedObjects": managed,
                        "managedObjectEtags": managed_etags,
                    },
                )
            created: Any = {}
            try:
                status_code, created = search_index_request(
                    config,
                    token,
                    method="PUT",
                    path=search_object_path(kind, name),
                    body=body,
                    headers=condition_headers,
                )
            except Exception:
                status_code = 0
            reconciled = False
            if status_code == 0 or status_code >= 500:
                reconcile_code, reconciled_object = search_index_request(
                    config,
                    token,
                    method="GET",
                    path=search_object_path(kind, name),
                    timeout=30,
                )
                if reconcile_code == 200 and _payload_is_subset(body, reconciled_object):
                    status_code = 200
                    created = reconciled_object
                    reconciled = True
            if status_code not in {200, 201}:
                if was_new and status_code not in {0} and status_code < 500:
                    managed.pop(label, None)
                raise RuntimeError(f"Creating {label} failed (HTTP {status_code}).")
            managed[label] = name
            etag = _search_object_etag(created)
            if not etag:
                reconcile_code, reconciled_object = search_index_request(
                    config,
                    token,
                    method="GET",
                    path=search_object_path(kind, name),
                    timeout=30,
                )
                if reconcile_code == 200 and _payload_is_subset(body, reconciled_object):
                    etag = _search_object_etag(reconciled_object)
            if not etag:
                write_lock(
                    config,
                    status="deployment-in-progress",
                    extra={
                        "checks": checks,
                        "managedObjects": managed,
                        "managedObjectEtags": managed_etags,
                    },
                )
                raise RuntimeError(f"Generated {label} is present but its ETag could not be recorded safely.")
            managed_etags[label] = etag
            checks.append(
                _check(
                    f"create-{label}",
                    "pass",
                    f"Generated {label} is ready"
                    + (" after reconciling an ambiguous response." if reconciled else "."),
                )
            )
            write_lock(
                config,
                status="deployment-in-progress",
                extra={
                    "checks": checks,
                    "managedObjects": managed,
                    "managedObjectEtags": managed_etags,
                },
            )

        verified = verify_report(
            config,
            quiet=True,
            query=query,
            expected_terms=expected_terms,
        )
        checks.extend(verified.get("checks", []))
        status = "pass" if verified.get("status") == "pass" else "fail"
        lock = write_lock(
            config,
            status="deployed" if status == "pass" else "verification-failed",
            extra={
                "checks": checks,
                "managedObjects": managed,
                "managedObjectEtags": managed_etags,
            },
        )
        return envelope(
            "up",
            status,
            profile=config.profile,
            environment=config.environment,
            checks=checks,
            ownership=config.ownership(),
            artifacts=[_display_path(lock)],
            nextActions=[f"Run ./liveks down --env {config.environment} when finished"],
        )
    except PermissionError as error:
        return envelope(
            "up",
            "confirmation-required",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("confirmation", "fail", str(error))],
            nextActions=["Review the plan and provide confirmation."],
        )
    except Exception as error:
        lock = write_lock(
            config,
            status="deployment-failed",
            extra={
                "checks": checks,
                "managedObjects": managed,
                "managedObjectEtags": managed_etags,
                "error": str(error),
            },
        )
        return envelope(
            "up",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("deployment", "fail", str(error))],
            ownership=config.ownership(),
            artifacts=[_display_path(lock)],
            nextActions=[f"Run ./liveks down --env {config.environment} --yes to remove only recorded generated objects"],
        )


def _mcp_search_index_up_report(
    config: ResolvedConfig,
    *,
    yes: bool,
    quiet: bool,
    query: str | None,
    expected_terms: list[str] | None,
    mcp_query: str | None,
    combined_query: str | None,
) -> dict[str, Any]:
    if any(not str(term).strip() for term in expected_terms or []):
        return envelope(
            "up",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("runtime-input", "fail", "Expected terms must not be empty.")],
        )
    plan = plan_report(config, quiet=True, operation_locked=True)
    if plan["status"] == "fail":
        return {**plan, "command": "up"}

    checks = list(plan.get("checks", []))
    managed, managed_etags, lock_matches, _ = _mcp_search_index_lock_state(config)
    if not lock_matches:
        return envelope(
            "up",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("environment-lock", "fail", "The planned lock no longer matches the resolved configuration.")],
        )

    effective_index_query = query or "What information is available in the existing search index?"
    effective_mcp_query = mcp_query or "What must be configured for an Azure AI Search MCP Server knowledge source?"
    effective_combined_query = combined_query or (
        "Use the existing index for domain evidence and Microsoft Learn for guidance on validating Knowledge Base retrieval."
    )
    payloads = build_mcp_search_index_payloads(
        config,
        index_query=effective_index_query,
        mcp_query=effective_mcp_query,
        combined_query=effective_combined_query,
    )
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    try:
        _confirm_up(config, yes=yes, accept_fabric_capacity=False, creates_capacity=False)
        token = acquire_search_bearer_token(runner)
        objects = [
            (
                "searchIndexKnowledgeSource",
                "knowledgesources",
                str(config.get("search.index_knowledge_source_name")),
                str(config.get("search.index_api_version")),
                payloads["searchIndexKnowledgeSource"],
            ),
            (
                "mcpKnowledgeSource",
                "knowledgesources",
                str(config.get("search.mcp_knowledge_source_name")),
                str(config.get("search.preview_api_version")),
                payloads["mcpKnowledgeSource"],
            ),
            (
                "combinedKnowledgeBase",
                "knowledgebases",
                str(config.get("search.combined_knowledge_base_name")),
                str(config.get("search.preview_api_version")),
                payloads["knowledgeBase"],
            ),
        ]
        for label, kind, name, api_version, body in objects:
            existing_code, existing = search_index_request(
                config,
                token,
                method="GET",
                path=search_object_path(kind, name),
                api_version=api_version,
                timeout=30,
            )
            if existing_code == 200:
                remote_etag = _search_object_etag(existing)
                if (
                    managed.get(label) != name
                    or not managed_etags.get(label)
                    or managed_etags.get(label) != remote_etag
                ):
                    raise RuntimeError(f"Refusing to overwrite an unowned or changed {label}.")
                if not _payload_is_subset(body, existing):
                    raise RuntimeError(f"Owned {label} definition changed; run down before recreating it.")
                checks.append(_check(f"create-{label}", "pass", f"Owned {label} is already ready."))
                continue
            condition_headers = {
                "If-None-Match": "*",
                "Prefer": "return=representation",
            }
            if existing_code not in {200, 404}:
                raise RuntimeError(f"Unable to check the target {label} name (HTTP {existing_code}).")
            was_new = existing_code == 404
            if was_new:
                managed_etags.pop(label, None)
                managed[label] = name
                write_lock(
                    config,
                    status="deployment-in-progress",
                    extra={
                        "checks": checks,
                        "managedObjects": managed,
                        "managedObjectEtags": managed_etags,
                    },
                )
            created: Any = {}
            try:
                status_code, created = search_index_request(
                    config,
                    token,
                    method="PUT",
                    path=search_object_path(kind, name),
                    api_version=api_version,
                    body=body,
                    headers=condition_headers,
                )
            except Exception:
                status_code = 0
            reconciled = False
            if status_code == 0 or status_code >= 500:
                reconcile_code, reconciled_object = search_index_request(
                    config,
                    token,
                    method="GET",
                    path=search_object_path(kind, name),
                    api_version=api_version,
                    timeout=30,
                )
                if reconcile_code == 200 and _payload_is_subset(body, reconciled_object):
                    status_code = 200
                    created = reconciled_object
                    reconciled = True
            if status_code not in {200, 201}:
                if was_new and status_code not in {0} and status_code < 500:
                    managed.pop(label, None)
                raise RuntimeError(f"Creating {label} failed (HTTP {status_code}).")
            managed[label] = name
            etag = _search_object_etag(created)
            if not etag:
                reconcile_code, reconciled_object = search_index_request(
                    config,
                    token,
                    method="GET",
                    path=search_object_path(kind, name),
                    api_version=api_version,
                    timeout=30,
                )
                if reconcile_code == 200 and _payload_is_subset(body, reconciled_object):
                    etag = _search_object_etag(reconciled_object)
            if not etag:
                write_lock(
                    config,
                    status="deployment-in-progress",
                    extra={
                        "checks": checks,
                        "managedObjects": managed,
                        "managedObjectEtags": managed_etags,
                    },
                )
                raise RuntimeError(f"Generated {label} is present but its ETag could not be recorded safely.")
            managed_etags[label] = etag
            checks.append(
                _check(
                    f"create-{label}",
                    "pass",
                    f"Generated {label} is ready"
                    + (" after reconciling an ambiguous response." if reconciled else "."),
                )
            )
            write_lock(
                config,
                status="deployment-in-progress",
                extra={
                    "checks": checks,
                    "managedObjects": managed,
                    "managedObjectEtags": managed_etags,
                },
            )

        verified = verify_report(
            config,
            quiet=True,
            query=effective_index_query,
            expected_terms=expected_terms,
            mcp_query=effective_mcp_query,
            combined_query=effective_combined_query,
        )
        checks.extend(verified.get("checks", []))
        status = "pass" if verified.get("status") == "pass" else "fail"
        lock = write_lock(
            config,
            status="deployed" if status == "pass" else "verification-failed",
            extra={
                "checks": checks,
                "managedObjects": managed,
                "managedObjectEtags": managed_etags,
            },
        )
        return envelope(
            "up",
            status,
            profile=config.profile,
            environment=config.environment,
            checks=checks,
            ownership=config.ownership(),
            contracts=_mcp_search_index_contracts(config),
            cleanupOrder=_mcp_search_index_cleanup_order(config),
            artifacts=[_display_path(lock)],
            nextActions=[f"Run ./liveks down --env {config.environment} when finished"],
        )
    except PermissionError as error:
        return envelope(
            "up",
            "confirmation-required",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("confirmation", "fail", str(error))],
            nextActions=["Review the plan and provide confirmation."],
        )
    except Exception as error:
        lock = write_lock(
            config,
            status="deployment-failed",
            extra={
                "checks": checks,
                "managedObjects": managed,
                "managedObjectEtags": managed_etags,
                "error": str(error),
            },
        )
        return envelope(
            "up",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("deployment", "fail", str(error))],
            ownership=config.ownership(),
            artifacts=[_display_path(lock)],
            nextActions=[f"Run ./liveks down --env {config.environment} --yes to remove only recorded generated objects"],
        )


def up_report(
    config: ResolvedConfig,
    *,
    yes: bool,
    accept_fabric_capacity: bool,
    quiet: bool = False,
    skip_app_build: bool = False,
    skip_dry_run: bool = False,
    postprovision_only: bool = False,
    query: str | None = None,
    expected_terms: list[str] | None = None,
    mcp_query: str | None = None,
    combined_query: str | None = None,
    operation_locked: bool = False,
) -> dict[str, Any]:
    if not operation_locked:
        try:
            with EnvironmentOperationLock(_operation_lock_path(config)):
                return up_report(
                    config,
                    yes=yes,
                    accept_fabric_capacity=accept_fabric_capacity,
                    quiet=quiet,
                    skip_app_build=skip_app_build,
                    skip_dry_run=skip_dry_run,
                    postprovision_only=postprovision_only,
                    query=query,
                    expected_terms=expected_terms,
                    mcp_query=mcp_query,
                    combined_query=combined_query,
                    operation_locked=True,
                )
        except RuntimeError as error:
            return envelope(
                "up",
                "fail",
                profile=config.profile,
                environment=config.environment,
                checks=[_check("operation-lock", "fail", str(error))],
            )
    if config.profile == "search-index":
        return _search_index_up_report(
            config,
            yes=yes,
            quiet=quiet,
            query=query,
            expected_terms=expected_terms,
        )
    if config.profile == "mcp-search-index":
        return _mcp_search_index_up_report(
            config,
            yes=yes,
            quiet=quiet,
            query=query,
            expected_terms=expected_terms,
            mcp_query=mcp_query,
            combined_query=combined_query,
        )
    plan = plan_report(
        config,
        quiet=True,
        skip_app_build=skip_app_build,
        skip_dry_run=skip_dry_run,
        operation_locked=True,
    )
    if plan["status"] == "fail":
        return {**plan, "command": "up"}
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    checks = list(plan.get("checks", []))
    restore_capacity_mode = False
    resource_group_preexisting: bool | None = None
    authored_config_digest = config.config_digest
    mutation_started = False
    try:
        _ensure_azd_environment(config, runner, reset_generated_fabric=config.profile == "full" and not postprovision_only)
        if postprovision_only:
            _confirm_up(config, yes=yes, accept_fabric_capacity=accept_fabric_capacity, creates_capacity=False)
            mutation_started = True
            write_lock(
                config,
                status="deployment-in-progress",
                extra={
                    "checks": checks,
                    "authoredConfigDigest": authored_config_digest,
                    "resourceGroupPreexisting": resource_group_preexisting,
                },
            )
            postprovision = runner.run([sys.executable, "scripts/postprovision.py"], check=True)
            checks.append(_check("postprovision", "pass", postprovision.stdout.splitlines()[-1] if postprovision.stdout else "completed"))
            verified = verify_report(config, quiet=True)
            checks.extend(verified.get("checks", []))
            status = verified["status"]
            lock = write_lock(
                config,
                status="deployed" if status == "pass" else "verification-failed",
                extra={"checks": checks, "authoredConfigDigest": authored_config_digest},
            )
            return envelope("up", status, profile=config.profile, environment=config.environment, checks=checks, ownership=config.ownership(), artifacts=[_display_path(lock)], nextActions=[f"Run ./liveks down --env {config.environment} when finished"])
        resource_group_probe = runner.run(["az", "group", "exists", "--name", str(config.get("azure.resource_group"))])
        if resource_group_probe.returncode == 0:
            resource_group_preexisting = resource_group_probe.stdout.strip().lower() == "true"
            message = "Resource group already existed before preview" if resource_group_preexisting else "Resource group did not exist before preview"
            checks.append(_check("resource-group-preexisting", "pass", message, preexisting=resource_group_preexisting))
        else:
            checks.append(_check("resource-group-preexisting", "warn", "Could not determine whether the resource group existed before preview"))
        if config.profile == "full":
            # Fabric preprovision owns capacity creation in the LiveKS path. Bicep
            # retains create-mode support for direct azd compatibility only.
            runner.run(["azd", "env", "set", "FABRIC_CAPACITY_MODE", "byo"], check=True)
            restore_capacity_mode = True
        preview = runner.run(["azd", "provision", "--preview", "--environment", config.environment, "--no-prompt"])
        checks.append(_check("azd-preview", "pass" if preview.returncode == 0 else "fail", "ARM preview completed without resource changes" if preview.returncode == 0 else preview.stdout[-1200:]))
        if preview.returncode != 0:
            raise RuntimeError("azd provision preview failed")
        _confirm_up(config, yes=yes, accept_fabric_capacity=accept_fabric_capacity)
        mutation_started = True
        write_lock(
            config,
            status="deployment-in-progress",
            extra={
                "checks": checks,
                "authoredConfigDigest": authored_config_digest,
                "resourceGroupPreexisting": resource_group_preexisting,
            },
        )
        if config.profile == "full":
            fabric = runner.run([sys.executable, "scripts/fabric-provision.py", "--env-name", config.environment], check=True)
            checks.append(_check("fabric-preprovision", "pass", fabric.stdout.splitlines()[-1] if fabric.stdout else "completed"))
        deployment = runner.run(["azd", "up", "--environment", config.environment, "--no-prompt"], check=True)
        checks.append(_check("azd-up", "pass", "Azure provisioning and app deployment completed"))
        verified = verify_report(config, quiet=True)
        checks.extend(verified.get("checks", []))
        status = "pass" if verified["status"] == "pass" else verified["status"]
        lock = write_lock(
            config,
            status="deployed" if status == "pass" else "verification-failed",
            extra={
                "checks": checks,
                "authoredConfigDigest": authored_config_digest,
                "resourceGroupPreexisting": resource_group_preexisting,
            },
        )
        return envelope("up", status, profile=config.profile, environment=config.environment, checks=checks, ownership=config.ownership(), artifacts=[_display_path(lock)], nextActions=[f"Run ./liveks down --env {config.environment} when finished"])
    except PermissionError as error:
        write_lock(
            config,
            status="confirmation-required",
            extra={
                "error": str(error),
                "checks": checks,
                "authoredConfigDigest": authored_config_digest,
                "resourceGroupPreexisting": resource_group_preexisting,
            },
        )
        return envelope("up", "confirmation-required", profile=config.profile, environment=config.environment, checks=checks + [_check("confirmation", "fail", str(error))], nextActions=["Review the plan and provide the required confirmation flag"])
    except Exception as error:
        write_lock(
            config,
            status="deployment-failed" if mutation_started else "plan-failed",
            extra={
                "error": str(error),
                "checks": checks,
                "authoredConfigDigest": authored_config_digest,
                "resourceGroupPreexisting": resource_group_preexisting,
            },
        )
        return envelope("up", "fail", profile=config.profile, environment=config.environment, checks=checks + [_check("deployment", "fail", str(error))], nextActions=[f"Run ./liveks down --env {config.environment} --yes to remove partial resources"])
    finally:
        if restore_capacity_mode:
            runner.run(["azd", "env", "set", "FABRIC_CAPACITY_MODE", str(config.get("fabric.mode"))])


def _response_has_evidence(payload: Any, source_type: str | None = None) -> bool:
    if not isinstance(payload, dict):
        return False
    evidence = list(payload.get("activity", [])) + list(payload.get("references", []))
    if not evidence:
        return False
    if source_type is None:
        return True
    return any(item.get("type") == source_type for item in evidence if isinstance(item, dict))


def _response_has_live_evidence(payload: Any, source_type: str) -> bool:
    return isinstance(payload, dict) and payload.get("mode") == "live" and _response_has_evidence(payload, source_type)


def _evidence_types(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    evidence = list(payload.get("activity", [])) + list(payload.get("references", []))
    return sorted({str(item.get("type")) for item in evidence if isinstance(item, dict) and item.get("type")})


def _evidence_count(payload: Any, source_type: str | None = None) -> int:
    if not isinstance(payload, dict):
        return 0
    evidence = list(payload.get("activity", [])) + list(payload.get("references", []))
    if source_type is None:
        return sum(1 for item in evidence if isinstance(item, dict))
    return sum(
        1
        for item in evidence
        if isinstance(item, dict) and item.get("type") == source_type
    )


def _mcp_text_blocks(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    content = result.get("content")
    if not isinstance(content, list):
        return []
    return [str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("type") == "text"]


def _mcp_failure_message(status_code: int, payload: Any) -> str:
    if status_code in {401, 403}:
        return f"Azure AI Search rejected MCP authentication (HTTP {status_code})."
    if status_code == 404:
        return "The Knowledge Base MCP endpoint was not found (HTTP 404)."
    if status_code >= 500:
        return f"The Knowledge Base or one of its sources failed (HTTP {status_code})."
    if isinstance(payload, dict) and payload.get("error"):
        return "The MCP endpoint returned a JSON-RPC error."
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict) and payload["result"].get("isError"):
        return "knowledge_base_retrieve returned a tool error; check source authorization and source readiness."
    return f"The MCP call did not return usable grounding content (HTTP {status_code})."


def _persist_mcp_report(config: ResolvedConfig, report: dict[str, Any]) -> None:
    report_dir = ROOT / "deployments" / config.environment
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "mcp-call-report.json"
    report["artifacts"] = [str(report_path.relative_to(ROOT))]
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mcp_report(
    config: ResolvedConfig,
    *,
    query: str | None = None,
    expected_terms: list[str] | None = None,
    auth: str = "admin-key",
    omit_source_authorization: bool = False,
    expect_failure: bool = False,
    knowledge_base: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if any(not str(term).strip() for term in expected_terms or []):
        return envelope(
            "mcp",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("runtime-input", "fail", "Expected terms must not be empty.")],
        )
    checks: list[dict[str, Any]] = []
    if config.profile == "offline":
        report = envelope(
            "mcp",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("deployment", "fail", "A deployed live profile is required for an MCP call.")],
        )
        if persist:
            _persist_mcp_report(config, report)
        return report
    if config.profile == "search-index":
        report = envelope(
            "mcp",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[
                _check(
                    "profile-contract",
                    "fail",
                    "The stable search-index profile validates the REST retrieve path; use liveks verify. MCP is available in the preview deployment profiles.",
                )
            ],
        )
        if persist:
            _persist_mcp_report(config, report)
        return report

    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=True)
    direct_combined = config.profile == "mcp-search-index"
    if direct_combined:
        search_endpoint = str(config.get("search.endpoint")).rstrip("/")
        search_service = ""
        resource_group = ""
        api_version = str(config.get("search.preview_api_version"))
        kb_name = knowledge_base or str(config.get("search.combined_knowledge_base_name"))
    else:
        selected = runner.run(["azd", "env", "select", config.environment, "--no-prompt"])
        if selected.returncode != 0:
            report = envelope(
                "mcp",
                "fail",
                profile=config.profile,
                environment=config.environment,
                checks=[_check("azd-environment", "fail", "The deployment environment was not found.")],
            )
            if persist:
                _persist_mcp_report(config, report)
            return report

        env_result = runner.run(["azd", "env", "get-values"])
        azd_values = parse_azd_values(env_result.stdout)
        search_endpoint = azd_values.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
        search_service = azd_values.get("AZURE_SEARCH_SERVICE_NAME", "")
        resource_group = azd_values.get("AZURE_RESOURCE_GROUP", str(config.get("azure.resource_group", "")))
        api_version = azd_values.get("AZURE_SEARCH_API_VERSION", str(config.get("search.api_version")))
        kb_name = knowledge_base or azd_values.get(
            "FABRIC_ONLY_KNOWLEDGE_BASE_NAME" if config.profile in {"byo-fabric", "full"} else "MCP_ONLY_KNOWLEDGE_BASE_NAME",
            str(config.get("search.fabric_knowledge_base_name" if config.profile in {"byo-fabric", "full"} else "search.mcp_knowledge_base_name")),
        )
    if not all((search_endpoint, api_version, kb_name)):
        report = envelope(
            "mcp",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("deployment-values", "fail", "Search endpoint, API version, or Knowledge Base name is missing.")],
        )
        if persist:
            _persist_mcp_report(config, report)
        return report
    checks.append(_check("deployment-values", "pass", "MCP endpoint inputs resolved from the selected deployment."))

    headers: dict[str, str] = {}
    if auth == "bearer":
        auth_result = runner.run(
            ["az", "account", "get-access-token", "--scope", "https://search.azure.com/.default", "--query", "accessToken", "-o", "tsv"]
        )
        service_credential = auth_result.stdout.strip()
        if not service_credential:
            checks.append(_check("mcp-auth", "fail", "Unable to acquire an Azure AI Search bearer token."))
        else:
            headers["Authorization"] = f"Bearer {service_credential}"
            checks.append(_check("mcp-auth", "pass", "Using a transient Azure AI Search bearer token."))
    else:
        if direct_combined:
            checks.append(
                _check(
                    "mcp-auth",
                    "fail",
                    "The mcp-search-index profile reuses a BYO Search service; call liveks mcp with --auth bearer.",
                )
            )
            report = envelope("mcp", "fail", profile=config.profile, environment=config.environment, checks=checks)
            if persist:
                _persist_mcp_report(config, report)
            return report
        key_result = runner.run(
            [
                "az",
                "search",
                "admin-key",
                "show",
                "--resource-group",
                resource_group,
                "--service-name",
                search_service,
                "--query",
                "primaryKey",
                "-o",
                "tsv",
            ]
        )
        service_credential = key_result.stdout.strip()
        if not search_service or not service_credential:
            checks.append(_check("mcp-auth", "fail", "Unable to acquire the transient Search admin key used by the sample deployment."))
        else:
            headers["api-key"] = service_credential
            checks.append(_check("mcp-auth", "pass", "Using the sample deployment's transient Search admin key; no key is printed or persisted."))

    needs_source_authorization = config.profile in {"byo-fabric", "full"}
    if needs_source_authorization and not omit_source_authorization:
        source_result = runner.run(
            ["az", "account", "get-access-token", "--scope", "https://search.azure.com/.default", "--query", "accessToken", "-o", "tsv"]
        )
        source_token = source_result.stdout.strip()
        if not source_token:
            checks.append(_check("source-authorization", "fail", "Unable to acquire delegated source authorization."))
        else:
            headers["x-ms-query-source-authorization"] = source_token
            checks.append(_check("source-authorization", "pass", "Delegated source authorization is attached transiently."))
    elif needs_source_authorization:
        checks.append(_check("source-authorization", "pass" if expect_failure else "warn", "Delegated source authorization was intentionally omitted."))
    else:
        checks.append(_check("source-authorization", "pass", "The selected MCP-only profile does not require Fabric source authorization."))

    if any(check["status"] == "fail" for check in checks):
        report = envelope("mcp", "fail", profile=config.profile, environment=config.environment, checks=checks)
        if persist:
            _persist_mcp_report(config, report)
        return report

    mcp_url = f"{search_endpoint}/knowledgebases/{quote(kb_name, safe='')}/mcp?api-version={quote(api_version, safe='')}"
    try:
        list_code, list_payload = http_mcp_json(
            mcp_url,
            body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
            attempts=3,
            delay_seconds=3,
            timeout=30,
            retry_mode="read",
        )
    except Exception:
        checks.append(_check("tools-list", "fail", "The MCP endpoint could not complete tool discovery."))
        report = envelope("mcp", "fail", profile=config.profile, environment=config.environment, checks=checks)
        if persist:
            _persist_mcp_report(config, report)
        return report
    tools = list_payload.get("result", {}).get("tools", []) if isinstance(list_payload, dict) else []
    has_retrieve_tool = any(isinstance(tool, dict) and tool.get("name") == "knowledge_base_retrieve" for tool in tools)
    if list_code != 200 or not has_retrieve_tool:
        failure = _mcp_failure_message(list_code, list_payload)
        checks.append(_check("tools-list", "fail", failure))
        report = envelope("mcp", "fail", profile=config.profile, environment=config.environment, checks=checks)
        if persist:
            _persist_mcp_report(config, report)
        return report
    checks.append(_check("tools-list", "pass", "Knowledge Base publishes knowledge_base_retrieve."))

    effective_query = query or (
        "Which airlines have the highest customer-care exposure this month?"
        if needs_source_authorization
        else "What must be configured for an Azure AI Search MCP Server knowledge source?"
    )
    try:
        call_code, call_payload = http_mcp_json(
            mcp_url,
            body={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "knowledge_base_retrieve", "arguments": {"queries": [effective_query]}},
            },
            headers=headers,
            attempts=3,
            delay_seconds=3,
            timeout=180,
            retry_mode="read",
        )
    except Exception:
        checks.append(_check("tools-call", "fail", "The MCP endpoint could not complete the tool call."))
        report = envelope("mcp", "fail", profile=config.profile, environment=config.environment, checks=checks)
        if persist:
            _persist_mcp_report(config, report)
        return report
    text_blocks = _mcp_text_blocks(call_payload)
    tool_error = isinstance(call_payload, dict) and isinstance(call_payload.get("result"), dict) and bool(call_payload["result"].get("isError"))
    terms = expected_terms or []
    combined_text = "\n".join(text_blocks).casefold()
    matched_terms = sum(1 for term in terms if term.casefold() in combined_text)
    call_ok = call_code == 200 and bool(text_blocks) and not tool_error

    if expect_failure:
        if call_ok:
            checks.append(_check("tools-call", "fail", "The MCP call succeeded, but this run expected a failure."))
        else:
            checks.append(_check("tools-call", "pass", f"Expected failure reproduced: {_mcp_failure_message(call_code, call_payload)}"))
    elif call_ok:
        checks.append(
            _check(
                "tools-call",
                "pass",
                f"knowledge_base_retrieve returned {len(text_blocks)} text block(s).",
                contentBlocks=len(text_blocks),
            )
        )
        if terms:
            grounding_status = "pass" if matched_terms == len(terms) else "fail"
            checks.append(
                _check(
                    "grounding-content",
                    grounding_status,
                    f"MCP content matched {matched_terms}/{len(terms)} expected term(s).",
                    expectedTermCount=len(terms),
                    matchedExpectedTermCount=matched_terms,
                )
            )
        else:
            checks.append(
                _check(
                    "grounding-content",
                    "warn",
                    "MCP protocol content returned, but source grounding was not content-verified; repeat with --expect-term using a known non-sensitive fact.",
                    expectedTermCount=0,
                    matchedExpectedTermCount=0,
                )
            )
    else:
        checks.append(_check("tools-call", "fail", _mcp_failure_message(call_code, call_payload)))

    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    report = envelope("mcp", status, profile=config.profile, environment=config.environment, checks=checks)
    if persist:
        _persist_mcp_report(config, report)
    return report


def _search_index_verify_report(
    config: ResolvedConfig,
    *,
    quiet: bool,
    query: str | None,
    expected_terms: list[str] | None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    try:
        token = acquire_search_bearer_token(runner)
    except Exception:
        return envelope(
            "verify",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("search-auth", "fail", "Unable to acquire a transient Azure AI Search bearer token.")],
        )

    object_contracts = [
        ("search-index", "indexes", str(config.get("search.index_name"))),
        ("search-index-knowledge-source", "knowledgesources", str(config.get("search.index_knowledge_source_name"))),
        ("search-index-knowledge-base", "knowledgebases", str(config.get("search.index_knowledge_base_name"))),
    ]
    objects: dict[str, Any] = {}
    for label, kind, name in object_contracts:
        try:
            status_code, payload = search_index_request(
                config,
                token,
                method="GET",
                path=search_object_path(kind, name),
                timeout=30,
            )
        except Exception:
            status_code, payload = 0, {}
        objects[label] = payload
        checks.append(
            _check(
                label,
                "pass" if status_code == 200 else "fail",
                "Object is readable." if status_code == 200 else f"Object read failed (HTTP {status_code or 'unavailable'}).",
            )
        )

    knowledge_source = objects.get("search-index-knowledge-source")
    source_parameters = knowledge_source.get("searchIndexParameters", {}) if isinstance(knowledge_source, dict) else {}
    source_matches = (
        isinstance(knowledge_source, dict)
        and knowledge_source.get("kind") == "searchIndex"
        and source_parameters.get("searchIndexName") == config.get("search.index_name")
        and source_parameters.get("semanticConfigurationName") == config.get("search.semantic_configuration_name")
    )
    checks.append(
        _check(
            "knowledge-source-contract",
            "pass" if source_matches else "fail",
            "Knowledge Source references the configured existing index and semantic configuration."
            if source_matches
            else "Knowledge Source definition does not match the configured index contract.",
        )
    )

    knowledge_base = objects.get("search-index-knowledge-base")
    source_names = {
        str(item.get("name"))
        for item in knowledge_base.get("knowledgeSources", [])
        if isinstance(knowledge_base, dict) and isinstance(item, dict) and item.get("name")
    } if isinstance(knowledge_base, dict) else set()
    stable_kb = (
        config.get("search.index_knowledge_source_name") in source_names
        and not {"models", "outputMode", "retrievalReasoningEffort"}.intersection(knowledge_base or {})
    )
    checks.append(
        _check(
            "knowledge-base-contract",
            "pass" if stable_kb else "fail",
            "Knowledge Base uses the generated source without preview-only properties."
            if stable_kb
            else "Knowledge Base definition does not match the stable extractive contract.",
        )
    )

    effective_query = query or "What information is available in this index?"
    payloads = build_search_index_payloads(config, query=effective_query)
    try:
        retrieve_code, retrieve_payload = search_index_request(
            config,
            token,
            method="POST",
            path=f"{search_object_path('knowledgebases', str(config.get('search.index_knowledge_base_name')))}/retrieve",
            body=payloads["retrieve"],
            attempts=3,
            retry_mode="read",
        )
    except Exception:
        retrieve_code, retrieve_payload = 0, {}
    text_content = search_index_response_text(retrieve_payload)
    retrieve_ok = retrieve_code == 200 and bool(text_content) and _response_has_evidence(retrieve_payload, "searchIndex")
    checks.append(
        _check(
            "search-index-retrieve",
            "pass" if retrieve_ok else "fail",
            "Stable retrieve returned extracted content and searchIndex activity or reference evidence."
            if retrieve_ok
            else f"Stable retrieve did not return the required evidence (HTTP {retrieve_code or 'unavailable'}).",
            evidenceCount=_evidence_count(retrieve_payload, "searchIndex"),
        )
    )

    terms = expected_terms or []
    if terms:
        folded = text_content.casefold()
        matched = sum(1 for term in terms if term.casefold() in folded)
        checks.append(
            _check(
                "grounding-content",
                "pass" if matched == len(terms) else "fail",
                f"Extracted content matched {matched}/{len(terms)} expected term(s).",
                expectedTermCount=len(terms),
                matchedExpectedTermCount=matched,
            )
        )

    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    report = envelope(
        "verify",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        nextActions=[f"Run ./liveks down --env {config.environment} when finished"],
    )
    report_dir = ROOT / "deployments" / config.environment
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "verify-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["artifacts"] = [_display_path(report_path)]
    return report


def _mcp_search_index_retrieve_failure(status_code: int, source: str) -> str:
    if status_code in {401, 403}:
        return (
            f"{source} retrieve was unauthorized (HTTP {status_code}); verify Search data permissions and "
            "the Search managed identity's Azure OpenAI role."
        )
    if status_code == 402:
        return f"{source} retrieve requires an enabled Azure AI Search knowledge retrieval billing plan (HTTP 402)."
    if status_code == 206:
        return f"{source} retrieve returned partial content (HTTP 206); inspect protected activity errors locally."
    if status_code == 502:
        return f"{source} retrieve failed because every selected source, or one required source, failed (HTTP 502)."
    return f"{source} retrieve did not return required source evidence (HTTP {status_code or 'unavailable'})."


def _mcp_search_index_verify_report(
    config: ResolvedConfig,
    *,
    quiet: bool,
    query: str | None,
    expected_terms: list[str] | None,
    mcp_query: str | None,
    combined_query: str | None,
) -> dict[str, Any]:
    if any(not str(term).strip() for term in expected_terms or []):
        return envelope(
            "verify",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("runtime-input", "fail", "Expected terms must not be empty.")],
        )
    checks: list[dict[str, Any]] = []
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    try:
        token = acquire_search_bearer_token(runner)
    except Exception:
        return envelope(
            "verify",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("search-auth", "fail", "Unable to acquire a transient Azure AI Search bearer token.")],
        )

    stable = str(config.get("search.index_api_version"))
    preview = str(config.get("search.preview_api_version"))
    object_contracts = [
        ("search-index", "indexes", str(config.get("search.index_name")), stable),
        (
            "search-index-knowledge-source",
            "knowledgesources",
            str(config.get("search.index_knowledge_source_name")),
            stable,
        ),
        (
            "mcp-knowledge-source",
            "knowledgesources",
            str(config.get("search.mcp_knowledge_source_name")),
            preview,
        ),
        (
            "combined-knowledge-base",
            "knowledgebases",
            str(config.get("search.combined_knowledge_base_name")),
            preview,
        ),
    ]
    objects: dict[str, Any] = {}
    for label, kind, name, api_version in object_contracts:
        try:
            status_code, payload = search_index_request(
                config,
                token,
                method="GET",
                path=search_object_path(kind, name),
                api_version=api_version,
                timeout=30,
            )
        except Exception:
            status_code, payload = 0, {}
        objects[label] = payload
        checks.append(
            _check(
                label,
                "pass" if status_code == 200 else "fail",
                f"Object is readable through {api_version}."
                if status_code == 200
                else f"Object read failed through {api_version} (HTTP {status_code or 'unavailable'}).",
            )
        )

    index_source = objects.get("search-index-knowledge-source")
    index_parameters = index_source.get("searchIndexParameters", {}) if isinstance(index_source, dict) else {}
    index_source_matches = (
        isinstance(index_source, dict)
        and index_source.get("kind") == "searchIndex"
        and index_parameters.get("searchIndexName") == config.get("search.index_name")
        and index_parameters.get("semanticConfigurationName") == config.get("search.semantic_configuration_name")
    )
    checks.append(
        _check(
            "search-index-source-contract",
            "pass" if index_source_matches else "fail",
            "GA Search Index KS references the configured existing index and semantic configuration."
            if index_source_matches
            else "Search Index KS does not match the pinned GA contract.",
        )
    )

    mcp_source = objects.get("mcp-knowledge-source")
    mcp_parameters = mcp_source.get("mcpServerParameters", {}) if isinstance(mcp_source, dict) else {}
    tools = mcp_parameters.get("tools", []) if isinstance(mcp_parameters, dict) else []
    mcp_source_matches = (
        isinstance(mcp_source, dict)
        and mcp_source.get("kind") == "mcpServer"
        and mcp_parameters.get("serverURL") == config.get("mcp.server_url")
        and any(isinstance(tool, dict) and tool.get("name") == config.get("mcp.tool_name") for tool in tools)
    )
    checks.append(
        _check(
            "mcp-source-contract",
            "pass" if mcp_source_matches else "fail",
            "Preview MCP Server KS references the configured HTTPS server and allowed tool."
            if mcp_source_matches
            else "MCP Server KS does not match the pinned preview contract.",
        )
    )

    knowledge_base = objects.get("combined-knowledge-base")
    knowledge_source_names = (
        {
            str(item.get("name"))
            for item in knowledge_base.get("knowledgeSources", [])
            if isinstance(item, dict) and item.get("name")
        }
        if isinstance(knowledge_base, dict)
        else set()
    )
    models = knowledge_base.get("models", []) if isinstance(knowledge_base, dict) else []
    model_parameters = (
        models[0].get("azureOpenAIParameters", {})
        if models and isinstance(models[0], dict)
        else {}
    )
    knowledge_base_matches = (
        knowledge_source_names
        == {
            str(config.get("search.index_knowledge_source_name")),
            str(config.get("search.mcp_knowledge_source_name")),
        }
        and knowledge_base.get("outputMode") == "answerSynthesis"
        and knowledge_base.get("retrievalReasoningEffort") == {"kind": "low"}
        and model_parameters.get("resourceUri") == config.get("openai.endpoint")
        and model_parameters.get("deploymentId") == config.get("openai.deployment_name")
        and model_parameters.get("modelName") == config.get("openai.model_name")
    ) if isinstance(knowledge_base, dict) else False
    checks.append(
        _check(
            "combined-knowledge-base-contract",
            "pass" if knowledge_base_matches else "fail",
            "Preview Knowledge Base references both sources and the reused Azure OpenAI deployment."
            if knowledge_base_matches
            else "Combined Knowledge Base does not match the pinned preview source and model contract.",
        )
    )

    effective_index_query = query or "What information is available in the existing search index?"
    effective_mcp_query = mcp_query or "What must be configured for an Azure AI Search MCP Server knowledge source?"
    effective_combined_query = combined_query or (
        "Use the existing index for domain evidence and Microsoft Learn for guidance on validating Knowledge Base retrieval."
    )
    payloads = build_mcp_search_index_payloads(
        config,
        index_query=effective_index_query,
        mcp_query=effective_mcp_query,
        combined_query=effective_combined_query,
    )
    kb_path = f"{search_object_path('knowledgebases', str(config.get('search.combined_knowledge_base_name')))}/retrieve"

    retrieve_results: dict[str, tuple[int, Any]] = {}
    for label in ("searchIndex", "mcp"):
        try:
            retrieve_results[label] = search_index_request(
                config,
                token,
                method="POST",
                path=kb_path,
                api_version=preview,
                body=payloads["retrieve"][label],
                attempts=3,
                retry_mode="read",
            )
        except Exception:
            retrieve_results[label] = (0, {})

    index_code, index_payload = retrieve_results["searchIndex"]
    index_ok = index_code == 200 and _response_has_evidence(index_payload, "searchIndex")
    checks.append(
        _check(
            "search-index-retrieve",
            "pass" if index_ok else "fail",
            "Independent preview retrieve returned searchIndex activity, references, or sourceData evidence."
            if index_ok
            else _mcp_search_index_retrieve_failure(index_code, "Search Index"),
            evidenceCount=_evidence_count(index_payload, "searchIndex"),
        )
    )
    terms = expected_terms or []
    index_grounding_ok = True
    if terms:
        source_data = reference_source_data_text(index_payload, "searchIndex").casefold()
        matched = sum(1 for term in terms if term.casefold() in source_data)
        index_grounding_ok = matched == len(terms)
        checks.append(
            _check(
                "grounding-content",
                "pass" if index_grounding_ok else "fail",
                f"Search Index reference sourceData matched {matched}/{len(terms)} expected term(s).",
                expectedTermCount=len(terms),
                matchedExpectedTermCount=matched,
            )
        )

    mcp_code, mcp_payload = retrieve_results["mcp"]
    mcp_ok = mcp_code == 200 and _response_has_evidence(mcp_payload, "mcpServer")
    checks.append(
        _check(
            "mcp-retrieve",
            "pass" if mcp_ok else "fail",
            "Independent preview retrieve returned mcpServer activity, references, or sourceData evidence."
            if mcp_ok
            else _mcp_search_index_retrieve_failure(mcp_code, "MCP Server"),
            evidenceCount=_evidence_count(mcp_payload, "mcpServer"),
        )
    )

    independent_sources_passed = index_ok and index_grounding_ok and mcp_ok
    combined_code = 0
    combined_payload: Any = {}
    if independent_sources_passed:
        try:
            combined_code, combined_payload = search_index_request(
                config,
                token,
                method="POST",
                path=kb_path,
                api_version=preview,
                body=payloads["retrieve"]["combined"],
                attempts=3,
                retry_mode="read",
            )
        except Exception:
            combined_code, combined_payload = 0, {}
    source_types = (
        [
            item
            for item in _evidence_types(combined_payload)
            if item in {"searchIndex", "mcpServer"}
        ]
        if independent_sources_passed
        else []
    )
    combined_ok = independent_sources_passed and combined_code == 200 and bool(source_types)
    checks.append(
        _check(
            "combined-retrieve",
            "pass" if combined_ok else "fail",
            f"Combined routing evidence selected: {', '.join(source_types)}."
            if combined_ok
            else "Combined retrieve was not attempted because independent source proof failed."
            if not independent_sources_passed
            else _mcp_search_index_retrieve_failure(combined_code, "Combined"),
            sourceTypes=source_types,
            evidenceCount=_evidence_count(combined_payload),
            sourceCounts={
                source_type: _evidence_count(combined_payload, source_type)
                for source_type in source_types
            },
        )
    )

    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    report = envelope(
        "verify",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        contracts=_mcp_search_index_contracts(config),
        nextActions=[f"Run ./liveks down --env {config.environment} when finished"],
    )
    report_dir = ROOT / "deployments" / config.environment
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "verify-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["artifacts"] = [_display_path(report_path)]
    return report


def verify_report(
    config: ResolvedConfig,
    *,
    quiet: bool = False,
    query: str | None = None,
    expected_terms: list[str] | None = None,
    mcp_query: str | None = None,
    combined_query: str | None = None,
) -> dict[str, Any]:
    if any(not str(term).strip() for term in expected_terms or []):
        return envelope(
            "verify",
            "fail",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("runtime-input", "fail", "Expected terms must not be empty.")],
        )
    if config.profile == "offline":
        result = subprocess.run([sys.executable, "tools/try_offline.py", "--format", "json"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return envelope("verify", "pass" if result.returncode == 0 else "fail", profile=config.profile, environment=config.environment, checks=[_check("offline-replay", "pass" if result.returncode == 0 else "fail", "combined trace inspected" if result.returncode == 0 else result.stdout)])
    if config.profile == "search-index":
        return _search_index_verify_report(
            config,
            quiet=quiet,
            query=query,
            expected_terms=expected_terms,
        )
    if config.profile == "mcp-search-index":
        return _mcp_search_index_verify_report(
            config,
            quiet=quiet,
            query=query,
            expected_terms=expected_terms,
            mcp_query=mcp_query,
            combined_query=combined_query,
        )

    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    checks: list[dict[str, Any]] = []
    selected = runner.run(["azd", "env", "select", config.environment, "--no-prompt"])
    if selected.returncode != 0:
        return envelope("verify", "fail", profile=config.profile, environment=config.environment, checks=[_check("azd-environment", "fail", "Environment not found")])
    env_result = runner.run(["azd", "env", "get-values"])
    azd_values = parse_azd_values(env_result.stdout)
    resource_group = azd_values.get("AZURE_RESOURCE_GROUP", str(config.get("azure.resource_group")))
    exists = runner.run(["az", "group", "exists", "--name", resource_group])
    checks.append(_check("resource-group", "pass" if exists.stdout.strip().lower() == "true" else "fail", resource_group))
    app_url = azd_values.get("AZURE_WEBAPP_URL", "").rstrip("/")
    if not app_url:
        checks.append(_check("app-url", "fail", "AZURE_WEBAPP_URL is missing from azd outputs"))
    else:
        try:
            status_code, status_payload = http_json(f"{app_url}/api/status", attempts=18, delay_seconds=10, timeout=20)
            checks.append(_check("app-status", "pass" if status_code == 200 else "fail", f"HTTP {status_code}"))
            mcp_code, mcp_payload = http_json(f"{app_url}/api/retrieve/mcp", method="POST", body={"query": "What must be configured for an Azure AI Search MCP Server knowledge source?"}, attempts=3, delay_seconds=5, timeout=120, retry_mode="read")
            mcp_ok = mcp_code == 200 and _response_has_live_evidence(mcp_payload, "mcpServer")
            checks.append(_check("mcp-retrieve", "pass" if mcp_ok else "fail", "Live MCP activity/reference evidence returned" if mcp_ok else f"HTTP {mcp_code}; live MCP evidence missing"))
            if config.profile in {"byo-fabric", "full"}:
                token_result = runner.run(["az", "account", "get-access-token", "--resource", "https://search.azure.com", "--query", "accessToken", "-o", "tsv"])
                token = token_result.stdout.strip()
                if not token:
                    checks.append(_check("fabric-token", "fail", "Unable to acquire delegated Search token"))
                else:
                    fabric_body = {"query": "Which airlines have the highest customer-care exposure this month?", "fabricUserSearchToken": token}
                    fabric_code, fabric_payload = http_json(f"{app_url}/api/retrieve/fabric", method="POST", body=fabric_body, attempts=3, delay_seconds=5, timeout=120, retry_mode="read")
                    fabric_ok = fabric_code == 200 and _response_has_live_evidence(fabric_payload, "fabricOntology")
                    checks.append(_check("fabric-retrieve", "pass" if fabric_ok else "fail", "Live Fabric ontology evidence returned" if fabric_ok else f"HTTP {fabric_code}; live Fabric evidence missing"))
                    combined_body = {
                        "query": (
                            "Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. "
                            "Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the "
                            "Knowledge Base retrieve response."
                        ),
                        "fabricUserSearchToken": token,
                    }
                    combined_code, combined_payload = http_json(f"{app_url}/api/retrieve/combined", method="POST", body=combined_body, attempts=3, delay_seconds=5, timeout=120, retry_mode="read")
                    source_types = _evidence_types(combined_payload)
                    selected_types = [item for item in source_types if item in {"fabricOntology", "mcpServer"}]
                    combined_ok = combined_code == 200 and combined_payload.get("mode") == "live" and bool(selected_types)
                    if combined_ok:
                        selected = ", ".join(selected_types)
                        message = f"Combined KB returned live evidence; planner selected: {selected}"
                    else:
                        message = f"HTTP {combined_code}; combined live evidence missing"
                    checks.append(_check("combined-retrieve", "pass" if combined_ok else "fail", message, sourceTypes=source_types))
        except Exception as error:
            checks.append(_check("app-api", "fail", str(error)))

    native_expected_terms = (
        ["Alpine Air"]
        if config.profile == "full"
        else ["Azure AI Search"]
        if config.profile == "mcp-only"
        else None
    )
    native_mcp = mcp_report(
        config,
        query=(
            "Which airlines have the highest customer-care exposure this month?"
            if config.profile in {"byo-fabric", "full"}
            else "What must be configured for an Azure AI Search MCP Server knowledge source?"
        ),
        expected_terms=native_expected_terms,
        persist=False,
    )
    native_message = next(
        (
            str(check.get("message", ""))
            for check in reversed(native_mcp.get("checks", []))
            if check.get("name") in {"grounding-content", "tools-call", "tools-list"}
        ),
        "Knowledge Base MCP validation did not complete.",
    )
    grounding_check = next(
        (check for check in native_mcp.get("checks", []) if check.get("name") == "grounding-content"),
        None,
    )
    native_status = "fail" if native_mcp.get("status") != "pass" else "pass"
    if native_status == "pass" and grounding_check and grounding_check.get("status") == "warn":
        native_status = "warn"
    checks.append(_check("knowledge-base-mcp", native_status, native_message))
    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    report = envelope("verify", status, profile=config.profile, environment=config.environment, checks=checks, nextActions=[f"Run ./liveks down --env {config.environment} when finished"])
    report_dir = ROOT / "deployments" / config.environment
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "verify-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["artifacts"] = [str(report_path.relative_to(ROOT))]
    return report


def _load_lock(environment: str) -> dict[str, Any] | None:
    lock_path = ROOT / ".liveks" / f"{environment}.lock.json"
    if not lock_path.exists():
        return None
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"Invalid environment lock: {lock_path}: {error}") from error
    if lock.get("environment") != environment:
        raise ConfigError(f"Environment lock identity mismatch: {lock_path}")
    return lock


def _load_fabric_summary(environment: str) -> dict[str, Any] | None:
    summary_path = ROOT / "deployments" / environment / "fabric-summary.json"
    if not summary_path.exists():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"Invalid Fabric summary: {summary_path}: {error}") from error
    if not isinstance(summary, dict):
        raise ConfigError(f"Invalid Fabric summary object: {summary_path}")
    recorded_environment = str(summary.get("environmentName") or "")
    if recorded_environment and recorded_environment != environment:
        raise ConfigError(
            f"Fabric summary identity mismatch: expected {environment}, found {recorded_environment}"
        )
    return summary


def _locked_identity(environment: str) -> tuple[str | None, dict[str, str] | None]:
    lock = _load_lock(environment)
    if lock is None:
        return None, None
    ownership = lock.get("ownership")
    return str(lock.get("profile") or "") or None, ownership if isinstance(ownership, dict) else None


def _cleanup_ownership(config: ResolvedConfig) -> tuple[dict[str, str], str]:
    configured = config.ownership()
    try:
        _, locked = _locked_identity(config.environment)
    except ConfigError as error:
        locked = None
        missing_reason = f"invalid environment lock: {error}"
    else:
        missing_reason = "environment lock is missing"
    if locked is None:
        effective = dict(configured)
        for key in ("fabricCapacity", "fabricWorkspace", "fabricOntology"):
            if configured.get(key) == "create":
                effective[key] = "none"
        return effective, f"resolved configuration; {missing_reason}"

    # Deletion is allowed only when both records identify the Fabric asset as generated.
    effective = dict(configured)
    for key in ("fabricCapacity", "fabricWorkspace", "fabricOntology"):
        if configured.get(key) != "create" or locked.get(key) != "create":
            effective[key] = "reuse" if "reuse" in {configured.get(key), locked.get(key)} else "none"
    if any(
        configured.get(key) != effective.get(key)
        for key in ("fabricCapacity", "fabricWorkspace", "fabricOntology")
    ):
        for key in ("fabricCapacity", "fabricWorkspace", "fabricOntology"):
            if configured.get(key) == "create":
                effective[key] = "none"
    return effective, "resolved configuration + environment lock"


def _search_index_down_report(config: ResolvedConfig, *, yes: bool, quiet: bool) -> dict[str, Any]:
    if not yes:
        expected = f"delete {config.environment}"
        answer = input(f"Type '{expected}' to delete generated resources: ").strip()
        if answer != expected:
            return envelope(
                "down",
                "confirmation-required",
                profile=config.profile,
                environment=config.environment,
                checks=[_check("confirmation", "fail", "Cleanup cancelled")],
            )

    managed, managed_etags, lock_matches, lock_message = _search_index_lock_state(config)
    if not lock_matches or lock_message != "matching environment lock":
        return envelope(
            "down",
            "cleanup-incomplete",
            profile=config.profile,
            environment=config.environment,
            checks=[
                _check(
                    "ownership",
                    "warn",
                    "Generated Search object ownership cannot be proven; the existing service, index, and all named objects were preserved.",
                )
            ],
            ownership=config.ownership(),
            nextActions=["Restore the matching environment lock before cleanup."],
        )

    checks = [_check("ownership", "pass", "Matching configuration and lock prove the generated object names.")]
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    try:
        token = acquire_search_bearer_token(runner)
    except Exception:
        return envelope(
            "down",
            "cleanup-incomplete",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("search-auth", "fail", "Unable to acquire a transient Azure AI Search bearer token.")],
            ownership=config.ownership(),
        )

    remaining = dict(managed)
    remaining_etags = dict(managed_etags)
    expected_payloads = build_search_index_payloads(
        config,
        query="cleanup-reconciliation",
    )
    expected_objects = {
        "knowledgeBase": expected_payloads["knowledgeBase"],
        "knowledgeSource": expected_payloads["knowledgeSource"],
    }
    for label, kind in (("knowledgeBase", "knowledgebases"), ("knowledgeSource", "knowledgesources")):
        name = managed.get(label)
        if not name:
            checks.append(_check(f"delete-{label}", "pass", "No generated object is recorded."))
            continue
        etag = managed_etags.get(label, "")
        if not etag:
            try:
                reconcile_code, reconciled_object = search_index_request(
                    config,
                    token,
                    method="GET",
                    path=search_object_path(kind, name),
                    timeout=30,
                )
            except Exception:
                reconcile_code, reconciled_object = 0, {}
            if reconcile_code == 404:
                checks.append(_check(f"delete-{label}", "pass", "Pending generated object is already absent."))
                remaining.pop(label, None)
                remaining_etags.pop(label, None)
                continue
            etag = _search_object_etag(reconciled_object)
            if (
                reconcile_code != 200
                or not etag
                or not _payload_is_subset(expected_objects[label], reconciled_object)
            ):
                checks.append(
                    _check(
                        f"delete-{label}",
                        "fail",
                        "Pending object could not be reconciled to the expected generated definition and was preserved.",
                    )
                )
                continue
        try:
            status_code, _ = search_index_request(
                config,
                token,
                method="DELETE",
                path=search_object_path(kind, name),
                headers={"If-Match": etag},
                attempts=3,
                retry_mode="conditional-write",
                timeout=60,
            )
        except Exception:
            status_code = 0
        deleted = status_code in {200, 202, 204, 404}
        checks.append(
            _check(
                f"delete-{label}",
                "pass" if deleted else "fail",
                "Generated object is absent."
                if deleted
                else f"Generated object deletion failed (HTTP {status_code or 'unavailable'}).",
            )
        )
        if deleted:
            remaining.pop(label, None)
            remaining_etags.pop(label, None)

    try:
        index_code, _ = search_index_request(
            config,
            token,
            method="GET",
            path=search_object_path("indexes", str(config.get("search.index_name"))),
            timeout=30,
        )
    except Exception:
        index_code = 0
    checks.append(
        _check(
            "search-index-preserved",
            "pass" if index_code == 200 else "fail",
            "The existing Search index remains readable after cleanup."
            if index_code == 200
            else f"The existing Search index could not be confirmed after cleanup (HTTP {index_code or 'unavailable'}).",
        )
    )

    status = "pass" if not remaining and all(check["status"] != "fail" for check in checks) else "cleanup-incomplete"
    lock = write_lock(
        config,
        status="cleaned" if status == "pass" else "cleanup-incomplete",
        extra={
            "checks": checks,
            "managedObjects": remaining,
            "managedObjectEtags": remaining_etags,
        },
    )
    return envelope(
        "down",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        ownership=config.ownership(),
        artifacts=[_display_path(lock)],
        nextActions=[] if status == "pass" else ["Retry cleanup after resolving the failed generated-object deletion."],
    )


def _mcp_search_index_down_report(config: ResolvedConfig, *, yes: bool, quiet: bool) -> dict[str, Any]:
    if not yes:
        expected = f"delete {config.environment}"
        answer = input(f"Type '{expected}' to delete generated resources: ").strip()
        if answer != expected:
            return envelope(
                "down",
                "confirmation-required",
                profile=config.profile,
                environment=config.environment,
                checks=[_check("confirmation", "fail", "Cleanup cancelled")],
            )

    managed, managed_etags, lock_matches, lock_message = _mcp_search_index_lock_state(config)
    if not lock_matches or lock_message != "matching environment lock":
        return envelope(
            "down",
            "cleanup-incomplete",
            profile=config.profile,
            environment=config.environment,
            checks=[
                _check(
                    "ownership",
                    "warn",
                    "Generated object ownership cannot be proven; all Search, OpenAI, Knowledge Base, and Knowledge Source objects were preserved.",
                )
            ],
            ownership=config.ownership(),
            nextActions=["Restore the matching environment lock before cleanup."],
        )

    checks = [_check("ownership", "pass", "Matching configuration and lock prove all generated object names.")]
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    try:
        token = acquire_search_bearer_token(runner)
    except Exception:
        return envelope(
            "down",
            "cleanup-incomplete",
            profile=config.profile,
            environment=config.environment,
            checks=checks + [_check("search-auth", "fail", "Unable to acquire a transient Azure AI Search bearer token.")],
            ownership=config.ownership(),
        )

    remaining = dict(managed)
    remaining_etags = dict(managed_etags)
    expected_payloads = build_mcp_search_index_payloads(
        config,
        index_query="cleanup-reconciliation",
        mcp_query="cleanup-reconciliation",
        combined_query="cleanup-reconciliation",
    )
    expected_objects = {
        "combinedKnowledgeBase": expected_payloads["knowledgeBase"],
        "mcpKnowledgeSource": expected_payloads["mcpKnowledgeSource"],
        "searchIndexKnowledgeSource": expected_payloads["searchIndexKnowledgeSource"],
    }
    delete_contracts = [
        (
            "combinedKnowledgeBase",
            "knowledgebases",
            str(config.get("search.preview_api_version")),
        ),
        (
            "mcpKnowledgeSource",
            "knowledgesources",
            str(config.get("search.preview_api_version")),
        ),
        (
            "searchIndexKnowledgeSource",
            "knowledgesources",
            str(config.get("search.index_api_version")),
        ),
    ]
    for label, kind, api_version in delete_contracts:
        name = managed.get(label)
        if not name:
            checks.append(_check(f"delete-{label}", "pass", "No generated object is recorded."))
            continue
        etag = managed_etags.get(label, "")
        if not etag:
            try:
                reconcile_code, reconciled_object = search_index_request(
                    config,
                    token,
                    method="GET",
                    path=search_object_path(kind, name),
                    api_version=api_version,
                    timeout=30,
                )
            except Exception:
                reconcile_code, reconciled_object = 0, {}
            if reconcile_code == 404:
                checks.append(_check(f"delete-{label}", "pass", "Pending generated object is already absent."))
                remaining.pop(label, None)
                remaining_etags.pop(label, None)
                continue
            etag = _search_object_etag(reconciled_object)
            if (
                reconcile_code != 200
                or not etag
                or not _payload_is_subset(expected_objects[label], reconciled_object)
            ):
                checks.append(
                    _check(
                        f"delete-{label}",
                        "fail",
                        "Pending object could not be reconciled to the expected generated definition and was preserved.",
                    )
                )
                continue
        try:
            status_code, _ = search_index_request(
                config,
                token,
                method="DELETE",
                path=search_object_path(kind, name),
                api_version=api_version,
                headers={"If-Match": etag},
                attempts=3,
                retry_mode="conditional-write",
                timeout=60,
            )
        except Exception:
            status_code = 0
        deleted = status_code in {200, 202, 204, 404}
        checks.append(
            _check(
                f"delete-{label}",
                "pass" if deleted else "fail",
                f"Generated object is absent through {api_version}."
                if deleted
                else f"Generated object deletion failed through {api_version} (HTTP {status_code or 'unavailable'}).",
            )
        )
        if deleted:
            remaining.pop(label, None)
            remaining_etags.pop(label, None)

    try:
        index_code, _ = search_index_request(
            config,
            token,
            method="GET",
            path=search_object_path("indexes", str(config.get("search.index_name"))),
            api_version=str(config.get("search.index_api_version")),
            timeout=30,
        )
    except Exception:
        index_code = 0
    checks.append(
        _check(
            "search-index-preserved",
            "pass" if index_code == 200 else "fail",
            "The existing Search index remains readable after cleanup."
            if index_code == 200
            else f"The existing Search index could not be confirmed after cleanup (HTTP {index_code or 'unavailable'}).",
        )
    )
    checks.append(
        _check(
            "azure-openai-preserved",
            "pass",
            "Cleanup issues no delete request for the reused Azure OpenAI deployment.",
        )
    )

    status = "pass" if not remaining and all(check["status"] != "fail" for check in checks) else "cleanup-incomplete"
    lock = write_lock(
        config,
        status="cleaned" if status == "pass" else "cleanup-incomplete",
        extra={
            "checks": checks,
            "managedObjects": remaining,
            "managedObjectEtags": remaining_etags,
        },
    )
    return envelope(
        "down",
        status,
        profile=config.profile,
        environment=config.environment,
        checks=checks,
        ownership=config.ownership(),
        cleanupOrder=_mcp_search_index_cleanup_order(config),
        artifacts=[_display_path(lock)],
        nextActions=[] if status == "pass" else ["Retry cleanup after resolving failed generated-object deletion."],
    )


def down_report(
    config: ResolvedConfig,
    *,
    yes: bool,
    quiet: bool = False,
    operation_locked: bool = False,
) -> dict[str, Any]:
    if not operation_locked:
        try:
            with EnvironmentOperationLock(_operation_lock_path(config)):
                return down_report(
                    config,
                    yes=yes,
                    quiet=quiet,
                    operation_locked=True,
                )
        except RuntimeError as error:
            return envelope(
                "down",
                "cleanup-incomplete",
                profile=config.profile,
                environment=config.environment,
                checks=[_check("operation-lock", "fail", str(error))],
            )
    if config.profile == "search-index":
        return _search_index_down_report(config, yes=yes, quiet=quiet)
    if config.profile == "mcp-search-index":
        return _mcp_search_index_down_report(config, yes=yes, quiet=quiet)
    cleanup_lock, cleanup_lock_error = _generic_cleanup_lock(config)
    if cleanup_lock_error:
        return envelope(
            "down",
            "cleanup-incomplete",
            profile=config.profile,
            environment=config.environment,
            checks=[_check("environment-lock", "fail", cleanup_lock_error)],
            ownership=config.ownership(),
            nextActions=["Restore the matching active environment lock before cleanup."],
        )
    checks: list[dict[str, Any]] = []
    if cleanup_lock is not None:
        checks.append(_check("environment-lock", "pass", "Matching environment lock authorizes cleanup."))
    if not yes:
        expected = f"delete {config.environment}"
        answer = input(f"Type '{expected}' to delete generated resources: ").strip()
        if answer != expected:
            return envelope("down", "confirmation-required", profile=config.profile, environment=config.environment, checks=[_check("confirmation", "fail", "Cleanup cancelled")])
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    selected = runner.run(["azd", "env", "select", config.environment, "--no-prompt"])
    if selected.returncode != 0:
        return envelope("down", "fail", profile=config.profile, environment=config.environment, checks=[_check("azd-environment", "fail", f"Environment not found: {config.environment}")])
    ownership, ownership_source = _cleanup_ownership(config)
    configured_ownership = config.ownership()
    ownership_disagreement = any(
        configured_ownership.get(key) != ownership.get(key)
        for key in ("fabricCapacity", "fabricWorkspace", "fabricOntology")
    )
    checks.append(
        _check(
            "ownership",
            "warn" if ownership_disagreement else "pass",
            (
                f"Fabric ownership cannot be proven ({ownership_source}); uncertain assets are preserved for manual review"
                if ownership_disagreement
                else ownership_source
            ),
            ownership=ownership,
        )
    )
    fabric_summary = None
    if ownership["fabricWorkspace"] == "create":
        try:
            fabric_summary = _load_fabric_summary(config.environment)
        except ConfigError as error:
            checks.append(_check("fabric-summary", "warn", str(error)))
        if fabric_summary is None and not any(check["name"] == "fabric-summary" for check in checks):
            checks.append(
                _check(
                    "fabric-summary",
                    "warn",
                    "Fabric ownership summary is missing; generated Fabric release cannot be verified",
                )
            )
    if ownership["fabricWorkspace"] == "create":
        if (
            fabric_summary is not None
            and ownership.get("fabricCapacity") == "create"
            and not fabric_summary.get("capacityCreated")
            and fabric_summary.get("capacityResourceGroupCreated") is not True
        ):
            checks.append(
                _check(
                    "fabric-capacity-ownership",
                    "warn",
                    "Full-mode capacity was not created by this environment; it was preserved and needs an explicit cleanup owner review",
                )
            )
        if (
            fabric_summary is not None
            and fabric_summary.get("capacityCreated")
            and not isinstance(fabric_summary.get("capacityResourceGroupCreated"), bool)
        ):
            checks.append(
                _check(
                    "fabric-capacity-resource-group-ownership",
                    "warn",
                    "Capacity resource-group ownership is missing; the group is preserved for manual review",
                )
            )
        fabric = runner.run([sys.executable, "scripts/fabric-destroy.py", "--env-name", config.environment, "--yes"])
        if (
            fabric.returncode == 0
            and fabric_summary is not None
            and not fabric_summary.get("capacityCreated")
            and fabric_summary.get("capacityResourceGroupCreated") is not True
        ):
            fabric_message = "Generated Fabric workspace assets deleted; unowned capacity preserved"
        else:
            fabric_message = "Generated Fabric assets deleted" if fabric.returncode == 0 else "Fabric cleanup needs manual follow-up; Azure cleanup continued"
        checks.append(_check("fabric-cleanup", "pass" if fabric.returncode == 0 else "warn", fabric_message))
    else:
        checks.append(_check("fabric-cleanup", "pass", "No generated Fabric assets owned by this environment"))
    azure = runner.run(["azd", "down", "--environment", config.environment, "--purge", "--force", "--no-prompt"])
    checks.append(_check("azure-cleanup", "pass" if azure.returncode == 0 else "fail", "azd down completed" if azure.returncode == 0 else azure.stdout[-1200:]))
    if config.profile == "full":
        for key in GENERATED_FABRIC_AZD_KEYS:
            runner.run(["azd", "env", "set", key, ""])
    env_values = runner.run(["azd", "env", "get-values"])
    projected = parse_azd_values(env_values.stdout)
    resource_group = projected.get("AZURE_RESOURCE_GROUP", str(config.get("azure.resource_group")))
    absent = False
    for attempt in range(12):
        exists = runner.run(["az", "group", "exists", "--name", resource_group])
        absent = exists.stdout.strip().lower() == "false"
        if absent:
            break
        if attempt < 11:
            time.sleep(5)
    try:
        lock = _load_lock(config.environment)
    except ConfigError as error:
        lock = None
        checks.append(_check("environment-lock", "warn", str(error)))
    preexisting = lock.get("resourceGroupPreexisting") if lock else None
    if not absent and preexisting is False:
        fallback = runner.run(["az", "group", "delete", "--name", resource_group, "--yes", "--no-wait"])
        checks.append(
            _check(
                "resource-group-fallback-cleanup",
                "pass" if fallback.returncode == 0 else "fail",
                "Deleting the accelerator-created residual resource group" if fallback.returncode == 0 else fallback.stdout[-1200:],
            )
        )
        if fallback.returncode == 0:
            for attempt in range(12):
                exists = runner.run(["az", "group", "exists", "--name", resource_group])
                absent = exists.stdout.strip().lower() == "false"
                if absent:
                    break
                if attempt < 11:
                    time.sleep(5)
    checks.append(_check("resource-group-absent", "pass" if absent else "fail", f"Deployment resource group {resource_group} is absent" if absent else f"Deployment resource group {resource_group} still exists"))

    capacity_cleanup_owned = bool(
        fabric_summary
        and (
            fabric_summary.get("capacityCreated")
            or fabric_summary.get("capacityResourceGroupCreated") is True
        )
    )
    if ownership.get("fabricCapacity") == "create" and capacity_cleanup_owned:
        capacity_group = str(
            fabric_summary.get("capacityResourceGroup")
            or projected.get("FABRIC_CAPACITY_RESOURCE_GROUP")
            or config.get("fabric.capacity_resource_group")
        )
        capacity_name = str(
            fabric_summary.get("capacityName")
            or projected.get("FABRIC_CAPACITY_NAME")
            or config.get("fabric.capacity_name")
        )
        capacity_group_ownership = fabric_summary.get("capacityResourceGroupCreated")
        capacity_group_owned = capacity_group_ownership is True
        capacity_group_absent = False
        capacity_absent = False
        for attempt in range(12):
            group_probe = runner.run(["az", "group", "exists", "--name", capacity_group])
            capacity_group_absent = group_probe.returncode == 0 and group_probe.stdout.strip().lower() == "false"
            if capacity_group_absent:
                capacity_absent = True
            else:
                capacity_probe = runner.run(
                    [
                        "az",
                        "resource",
                        "list",
                        "--resource-group",
                        capacity_group,
                        "--resource-type",
                        "Microsoft.Fabric/capacities",
                        "--output",
                        "json",
                    ]
                )
                try:
                    capacities = json.loads(capacity_probe.stdout or "[]")
                except json.JSONDecodeError:
                    capacities = None
                capacity_absent = bool(
                    capacity_probe.returncode == 0
                    and isinstance(capacities, list)
                    and not any(
                        isinstance(capacity, dict)
                        and str(capacity.get("name") or "").lower() == capacity_name.lower()
                        for capacity in capacities
                    )
                )
            if capacity_absent:
                break
            if attempt < 11:
                time.sleep(5)
        if capacity_group_owned:
            checks.append(
                _check(
                    "fabric-capacity-resource-group-absent",
                    "pass" if capacity_group_absent else "fail",
                    f"Generated Fabric capacity resource group {capacity_group} is absent"
                    if capacity_group_absent
                    else f"Generated Fabric capacity resource group {capacity_group} still exists",
                )
            )
        elif capacity_group_ownership is False:
            checks.append(
                _check(
                    "fabric-capacity-resource-group-preserved",
                    "pass" if not capacity_group_absent else "fail",
                    f"Pre-existing Fabric capacity resource group {capacity_group} is preserved"
                    if not capacity_group_absent
                    else f"Pre-existing Fabric capacity resource group {capacity_group} is absent",
                )
            )
        checks.append(
            _check(
                "fabric-capacity-absent",
                "pass" if capacity_absent else "fail",
                f"Generated Fabric capacity {capacity_name} is absent"
                if capacity_absent
                else f"Generated Fabric capacity {capacity_name} still exists or could not be verified",
            )
        )
    failed = any(check["status"] == "fail" for check in checks)
    warned = any(check["status"] == "warn" for check in checks)
    status = "fail" if failed else "partial" if warned else "pass"
    write_lock(
        config,
        status="destroyed" if status == "pass" else "cleanup-incomplete",
        extra={
            "checks": checks,
            **_preserved_cleanup_metadata(cleanup_lock),
        },
    )
    return envelope("down", status, profile=config.profile, environment=config.environment, checks=checks, nextActions=[] if status == "pass" else ["Inspect the cleanup report and remove only generated residual resources"])


def _common_config_args(parser: argparse.ArgumentParser, *, require_env: bool = False) -> None:
    parser.add_argument("--profile", choices=available_profiles())
    parser.add_argument("--mode", choices=available_profiles(), help=argparse.SUPPRESS)
    parser.add_argument("--env", dest="environment", required=require_env)
    parser.add_argument("--env-name", dest="legacy_environment", help=argparse.SUPPRESS)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--env-file", type=Path, help="Deprecated dotenv compatibility input.")
    parser.add_argument("--location", help=argparse.SUPPRESS)
    parser.add_argument("--fabric-location", help=argparse.SUPPRESS)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--no-color", action="store_true", help=argparse.SUPPRESS)


def _resolve_from_args(args: argparse.Namespace) -> ResolvedConfig:
    profile = getattr(args, "profile", None) or getattr(args, "mode", None)
    environment = getattr(args, "environment", None) or getattr(args, "legacy_environment", None)
    config_path = find_config(environment, getattr(args, "config", None))
    if not profile and environment and config_path is None:
        profile, _ = _locked_identity(environment)
    overrides: dict[str, Any] = {}
    if getattr(args, "location", None):
        overrides["azure.location"] = args.location
    if getattr(args, "fabric_location", None):
        overrides["fabric.location"] = args.fabric_location
    return resolve_config(profile=profile, environment=environment, config_path=config_path, legacy_env_path=getattr(args, "env_file", None), overrides=overrides)


def _exit_code(report: dict[str, Any]) -> int:
    status = report.get("status")
    if status in {"pass", "warn"}:
        return 0
    if status == "confirmation-required":
        return 3
    if status in {"partial", "cleanup-incomplete"}:
        return 4
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liveks", description="Plan-first deployment for Foundry IQ live Knowledge Sources.")
    parser.add_argument("--version", action="version", version=f"LiveKS {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("profiles", help="List executable profiles.").add_argument("--format", choices=["text", "json"], default="text")
    try_parser = subparsers.add_parser("try", help="Inspect a checked-in retrieve trace.")
    try_parser.add_argument("--sample", choices=["mcp", "fabric", "combined"], default="combined")
    try_parser.add_argument("--details", action="store_true")
    try_parser.add_argument("--format", choices=["text", "json"], default="text")
    try_parser.add_argument("--evidence-out", type=Path)

    init_parser = subparsers.add_parser("init", help="Create an ignored YAML environment ledger.")
    init_parser.add_argument(
        "--profile",
        choices=[profile for profile in available_profiles() if profile != "offline"],
        required=True,
    )
    init_parser.add_argument("--env", dest="environment", required=True)
    init_parser.add_argument("--config", type=Path)
    init_parser.add_argument("--from-env", type=Path)
    init_parser.add_argument("--format", choices=["text", "json"], default="text")

    doctor_parser = subparsers.add_parser("doctor", help="Check profile readiness without mutations.")
    _common_config_args(doctor_parser)
    plan_parser = subparsers.add_parser("plan", help="Build and describe the deployment without creating resources.")
    _common_config_args(plan_parser)
    up_parser = subparsers.add_parser("up", help="Preview, confirm, deploy, and verify.")
    _common_config_args(up_parser, require_env=False)
    up_parser.add_argument("--yes", action="store_true")
    up_parser.add_argument("--accept-fabric-capacity", action="store_true")
    up_parser.add_argument("--skip-app-build", action="store_true", help=argparse.SUPPRESS)
    up_parser.add_argument("--skip-dry-run", action="store_true", help=argparse.SUPPRESS)
    up_parser.add_argument("--postprovision-only", action="store_true", help=argparse.SUPPRESS)
    up_parser.add_argument("--query", help="Runtime acceptance query for a direct Search Index source.")
    up_parser.add_argument("--mcp-query", help="MCP-only retrieve query for the mcp-search-index profile.")
    up_parser.add_argument("--combined-query", help="Combined retrieve query for the mcp-search-index profile.")
    up_parser.add_argument("--expect-term", action="append", default=[], help="Expected non-sensitive term in Search Index reference sourceData; repeatable.")
    verify_parser = subparsers.add_parser("verify", help="Verify deployed resources and retrieve evidence.")
    _common_config_args(verify_parser, require_env=False)
    verify_parser.add_argument("--query")
    verify_parser.add_argument("--mcp-query")
    verify_parser.add_argument("--combined-query")
    verify_parser.add_argument("--expect-term", action="append", default=[])
    mcp_parser = subparsers.add_parser("mcp", help="Call a deployed Knowledge Base through its MCP endpoint.")
    _common_config_args(mcp_parser, require_env=True)
    mcp_parser.add_argument("--query")
    mcp_parser.add_argument("--expect-term", action="append", default=[])
    mcp_parser.add_argument("--auth", choices=["admin-key", "bearer"], default="admin-key")
    mcp_parser.add_argument("--omit-source-authorization", action="store_true")
    mcp_parser.add_argument("--expect-failure", action="store_true")
    mcp_parser.add_argument("--knowledge-base")
    down_parser = subparsers.add_parser("down", help="Delete only resources owned by an environment.")
    _common_config_args(down_parser, require_env=False)
    down_parser.add_argument("--yes", action="store_true")
    e2e_parser = subparsers.add_parser("e2e", help="Run up, verify, and optional cleanup as one lifecycle test.")
    _common_config_args(e2e_parser, require_env=False)
    e2e_parser.add_argument("--cleanup", action="store_true")
    e2e_parser.add_argument("--keep-resources", action="store_true")
    e2e_parser.add_argument("--yes", action="store_true")
    e2e_parser.add_argument("--accept-fabric-capacity", action="store_true")
    e2e_parser.add_argument("--query", help="Runtime acceptance query for a direct Search Index source.")
    e2e_parser.add_argument("--mcp-query", help="MCP-only retrieve query for the mcp-search-index profile.")
    e2e_parser.add_argument("--combined-query", help="Combined retrieve query for the mcp-search-index profile.")
    e2e_parser.add_argument("--expect-term", action="append", default=[], help="Expected non-sensitive term in Search Index reference sourceData; repeatable.")
    return parser


def _init_from_legacy(path: Path, profile: str, environment: str, destination: Path) -> None:
    write_user_config(destination, profile=profile, environment=environment)
    data = yaml.safe_load(destination.read_text(encoding="utf-8"))
    schema = yaml.safe_load((ROOT / "config/schema.yaml").read_text(encoding="utf-8"))
    flat: dict[str, Any] = {}
    for env_name, value in parse_legacy_env(path).items():
        field = schema.get("legacy_env", {}).get(env_name)
        if not field:
            continue
        if field in {"deployment.mode", "fabric.mode"}:
            continue
        if profile in {"mcp-only", "mcp-search-index"} and field.startswith("fabric."):
            continue
        if profile == "full" and field in {"fabric.workspace_id", "fabric.ontology_id"}:
            continue
        spec = schema["fields"][field]
        if spec.get("secret"):
            flat[field] = {"env": env_name}
        elif value and not (value.startswith("<") and value.endswith(">")):
            flat[field] = value
    imported = unflatten(flat)
    for key, value in imported.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    destination.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    destination.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    reset_retry_telemetry()
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.command == "profiles":
            rows = profile_table()
            report = envelope("profiles", "pass", profiles=rows)
            if args.format == "json":
                emit(report, "json")
            else:
                for row in rows:
                    print(f"{row['profile']}: {row['purpose']} ({row['estimatedDuration']})")
            return 0
        if args.command == "try":
            command = [sys.executable, "tools/try_offline.py", "--sample", args.sample, "--format", args.format]
            if args.details:
                command.append("--details")
            if args.evidence_out:
                command.extend(["--evidence-out", str(args.evidence_out)])
            return subprocess.run(command, cwd=ROOT, check=False).returncode
        if args.command == "init":
            destination = args.config or ROOT / ".liveks" / f"{args.environment}.yaml"
            if args.from_env:
                _init_from_legacy(args.from_env, args.profile, args.environment, destination)
            else:
                write_user_config(destination, profile=args.profile, environment=args.environment)
            display_destination = _display_path(destination)
            report = envelope(
                "init",
                "pass",
                profile=args.profile,
                environment=args.environment,
                artifacts=[display_destination],
                nextActions=[f"Review {display_destination}, then run ./liveks doctor --env {args.environment}"],
            )
            emit(report, args.format)
            return 0

        config = _resolve_from_args(args)
        if args.command == "doctor":
            report = doctor_report(config)
        elif args.command == "plan":
            report = plan_report(config, quiet=args.format == "json")
        elif args.command == "up":
            report = up_report(
                config,
                yes=args.yes,
                accept_fabric_capacity=args.accept_fabric_capacity,
                quiet=args.format == "json",
                skip_app_build=args.skip_app_build,
                skip_dry_run=args.skip_dry_run,
                postprovision_only=args.postprovision_only,
                query=args.query,
                expected_terms=args.expect_term,
                mcp_query=args.mcp_query,
                combined_query=args.combined_query,
            )
        elif args.command == "verify":
            report = verify_report(
                config,
                quiet=args.format == "json",
                query=args.query,
                expected_terms=args.expect_term,
                mcp_query=args.mcp_query,
                combined_query=args.combined_query,
            )
        elif args.command == "mcp":
            report = mcp_report(
                config,
                query=args.query,
                expected_terms=args.expect_term,
                auth=args.auth,
                omit_source_authorization=args.omit_source_authorization,
                expect_failure=args.expect_failure,
                knowledge_base=args.knowledge_base,
            )
        elif args.command == "down":
            report = down_report(config, yes=args.yes, quiet=args.format == "json")
        elif args.command == "e2e":
            if args.cleanup == args.keep_resources:
                raise ConfigError("Choose exactly one of --cleanup or --keep-resources.")
            cleanup: dict[str, Any] | None = None
            try:
                with EnvironmentOperationLock(_operation_lock_path(config)):
                    up = up_report(
                        config,
                        yes=args.yes,
                        accept_fabric_capacity=args.accept_fabric_capacity,
                        quiet=args.format == "json",
                        query=args.query,
                        expected_terms=args.expect_term,
                        mcp_query=args.mcp_query,
                        combined_query=args.combined_query,
                        operation_locked=True,
                    )
                    if args.cleanup:
                        blocked_before_mutation = any(
                            check.get("status") == "fail"
                            and check.get("name")
                            in {
                                "environment-lock",
                                "operation-lock",
                                "runtime-input",
                                "confirmation",
                            }
                            for check in up.get("checks", [])
                            if isinstance(check, dict)
                        )
                        cleanup_authorized = up.get("status") == "pass" or (
                            not blocked_before_mutation and _failed_up_started_mutation(config)
                        )
                        if cleanup_authorized:
                            cleanup = down_report(
                                config,
                                yes=True,
                                quiet=args.format == "json",
                                operation_locked=True,
                            )
                        else:
                            cleanup = envelope(
                                "down",
                                "skipped",
                                profile=config.profile,
                                environment=config.environment,
                                checks=[
                                    _check(
                                        "cleanup-authorization",
                                        "warn",
                                        "Cleanup was skipped because this E2E run did not start a mutation.",
                                    )
                                ],
                            )
            except RuntimeError as error:
                up = envelope(
                    "up",
                    "fail",
                    profile=config.profile,
                    environment=config.environment,
                    checks=[_check("operation-lock", "fail", str(error))],
                )
            status = "pass" if up["status"] == "pass" and (cleanup is None or cleanup["status"] == "pass") else "fail"
            report = envelope("e2e", status, profile=config.profile, environment=config.environment, phases={"up": up, "down": cleanup}, artifacts=list(dict.fromkeys(up.get("artifacts", []) + (cleanup or {}).get("artifacts", []))))
            report["retrySummary"] = retry_telemetry_summary()
            write_e2e_reports(config, report, cleanup_requested=args.cleanup)
        else:
            raise ConfigError(f"Unsupported command: {args.command}")
        report.setdefault("retrySummary", retry_telemetry_summary())
        emit(report, args.format)
        return _exit_code(report)
    except ConfigError as error:
        report = envelope(args.command, "fail", checks=[_check("configuration", "fail", str(error))])
        report["retrySummary"] = retry_telemetry_summary()
        emit(report, getattr(args, "format", "text"))
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
