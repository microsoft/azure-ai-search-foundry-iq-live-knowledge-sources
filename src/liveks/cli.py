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
from .runtime import CommandRunner, http_json, parse_azd_values, parse_version


ROOT = Path(__file__).resolve().parents[2]
LIVE_PROFILES = {"mcp-only", "byo-fabric", "full"}
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


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|").strip()


def write_e2e_reports(config: ResolvedConfig, report: dict[str, Any], *, cleanup_requested: bool) -> list[str]:
    """Persist ignored machine and maintainer reports for the complete lifecycle."""
    report_dir = ROOT / "deployments" / config.environment
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "e2e-report.json"
    markdown_path = report_dir / "test-report.md"
    artifacts = [_display_path(json_path), _display_path(markdown_path)]
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
    return artifacts


def _command_version(command: list[str], config: ResolvedConfig) -> tuple[int, str]:
    result = CommandRunner(root=ROOT, env=config.child_env(), quiet=True).run(command)
    return result.returncode, result.stdout.strip()


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

    if config.profile in LIVE_PROFILES and cloud:
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


def plan_report(
    config: ResolvedConfig,
    *,
    quiet: bool = True,
    skip_app_build: bool = False,
    skip_dry_run: bool = False,
) -> dict[str, Any]:
    doctor = doctor_report(config, cloud=config.profile in LIVE_PROFILES)
    checks = list(doctor["checks"])
    if doctor["status"] == "fail":
        return envelope("plan", "fail", profile=config.profile, environment=config.environment, checks=checks, resources=config.manifest.get("resources", []), nextActions=["Resolve doctor failures and rerun plan"])

    if config.profile == "offline":
        lock = write_lock(config, status="planned", extra={"checks": checks})
        return envelope("plan", "pass", profile=config.profile, environment=config.environment, checks=checks, resources=[], cost=config.manifest.get("cost"), estimatedDuration=config.manifest.get("estimated_duration"), artifacts=[_display_path(lock)], nextActions=["Run ./liveks try"])

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


def up_report(
    config: ResolvedConfig,
    *,
    yes: bool,
    accept_fabric_capacity: bool,
    quiet: bool = False,
    skip_app_build: bool = False,
    skip_dry_run: bool = False,
    postprovision_only: bool = False,
) -> dict[str, Any]:
    plan = plan_report(config, quiet=True, skip_app_build=skip_app_build, skip_dry_run=skip_dry_run)
    if plan["status"] == "fail":
        return {**plan, "command": "up"}
    runner = CommandRunner(root=ROOT, env=config.child_env(), quiet=quiet)
    checks = list(plan.get("checks", []))
    restore_capacity_mode = False
    resource_group_preexisting: bool | None = None
    try:
        _ensure_azd_environment(config, runner, reset_generated_fabric=config.profile == "full" and not postprovision_only)
        if postprovision_only:
            _confirm_up(config, yes=yes, accept_fabric_capacity=accept_fabric_capacity, creates_capacity=False)
            postprovision = runner.run([sys.executable, "scripts/postprovision.py"], check=True)
            checks.append(_check("postprovision", "pass", postprovision.stdout.splitlines()[-1] if postprovision.stdout else "completed"))
            verified = verify_report(config, quiet=True)
            checks.extend(verified.get("checks", []))
            status = verified["status"]
            lock = write_lock(config, status="deployed" if status == "pass" else "verification-failed", extra={"checks": checks})
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
            extra={"checks": checks, "resourceGroupPreexisting": resource_group_preexisting},
        )
        return envelope("up", status, profile=config.profile, environment=config.environment, checks=checks, ownership=config.ownership(), artifacts=[_display_path(lock)], nextActions=[f"Run ./liveks down --env {config.environment} when finished"])
    except PermissionError as error:
        write_lock(
            config,
            status="confirmation-required",
            extra={"error": str(error), "checks": checks, "resourceGroupPreexisting": resource_group_preexisting},
        )
        return envelope("up", "confirmation-required", profile=config.profile, environment=config.environment, checks=checks + [_check("confirmation", "fail", str(error))], nextActions=["Review the plan and provide the required confirmation flag"])
    except Exception as error:
        write_lock(
            config,
            status="deployment-failed",
            extra={"error": str(error), "checks": checks, "resourceGroupPreexisting": resource_group_preexisting},
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


def verify_report(config: ResolvedConfig, *, quiet: bool = False) -> dict[str, Any]:
    if config.profile == "offline":
        result = subprocess.run([sys.executable, "tools/try_offline.py", "--format", "json"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return envelope("verify", "pass" if result.returncode == 0 else "fail", profile=config.profile, environment=config.environment, checks=[_check("offline-replay", "pass" if result.returncode == 0 else "fail", "combined trace inspected" if result.returncode == 0 else result.stdout)])

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
            mcp_code, mcp_payload = http_json(f"{app_url}/api/retrieve/mcp", method="POST", body={"query": "What must be configured for an Azure AI Search MCP Server knowledge source?"}, attempts=3, delay_seconds=5, timeout=120)
            mcp_ok = mcp_code == 200 and _response_has_live_evidence(mcp_payload, "mcpServer")
            checks.append(_check("mcp-retrieve", "pass" if mcp_ok else "fail", "Live MCP activity/reference evidence returned" if mcp_ok else f"HTTP {mcp_code}; live MCP evidence missing"))
            if config.profile in {"byo-fabric", "full"}:
                token_result = runner.run(["az", "account", "get-access-token", "--resource", "https://search.azure.com", "--query", "accessToken", "-o", "tsv"])
                token = token_result.stdout.strip()
                if not token:
                    checks.append(_check("fabric-token", "fail", "Unable to acquire delegated Search token"))
                else:
                    fabric_body = {"query": "Which airlines have the highest customer-care exposure this month?", "fabricUserSearchToken": token}
                    fabric_code, fabric_payload = http_json(f"{app_url}/api/retrieve/fabric", method="POST", body=fabric_body, attempts=3, delay_seconds=5, timeout=120)
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
                    combined_code, combined_payload = http_json(f"{app_url}/api/retrieve/combined", method="POST", body=combined_body, attempts=3, delay_seconds=5, timeout=120)
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
    return summary


def _locked_identity(environment: str) -> tuple[str | None, dict[str, str] | None]:
    lock = _load_lock(environment)
    if lock is None:
        return None, None
    ownership = lock.get("ownership")
    return str(lock.get("profile") or "") or None, ownership if isinstance(ownership, dict) else None


def _cleanup_ownership(config: ResolvedConfig) -> tuple[dict[str, str], str]:
    configured = config.ownership()
    _, locked = _locked_identity(config.environment)
    if locked is None:
        return configured, "resolved configuration"

    # Deletion is allowed only when both records identify the Fabric asset as generated.
    effective = dict(configured)
    for key in ("fabricCapacity", "fabricWorkspace", "fabricOntology"):
        if configured.get(key) != "create" or locked.get(key) != "create":
            effective[key] = "reuse" if "reuse" in {configured.get(key), locked.get(key)} else "none"
    return effective, "resolved configuration + environment lock"


def down_report(config: ResolvedConfig, *, yes: bool, quiet: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
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
    fabric_summary = _load_fabric_summary(config.environment) if ownership["fabricWorkspace"] == "create" else None
    checks.append(_check("ownership", "pass", ownership_source, ownership=ownership))
    if ownership["fabricWorkspace"] == "create":
        fabric = runner.run([sys.executable, "scripts/fabric-destroy.py", "--env-name", config.environment, "--yes"])
        checks.append(_check("fabric-cleanup", "pass" if fabric.returncode == 0 else "warn", "Generated Fabric assets deleted" if fabric.returncode == 0 else "Fabric cleanup needs manual follow-up; Azure cleanup continued"))
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
    lock = _load_lock(config.environment)
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

    capacity_created = bool(fabric_summary and fabric_summary.get("capacityCreated"))
    if ownership.get("fabricCapacity") == "create" and capacity_created:
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
        capacity_group_absent = False
        capacity_absent = False
        for attempt in range(12):
            group_probe = runner.run(["az", "group", "exists", "--name", capacity_group])
            capacity_group_absent = group_probe.returncode == 0 and group_probe.stdout.strip().lower() == "false"
            capacity_probe = runner.run(
                [
                    "az",
                    "resource",
                    "list",
                    "--resource-type",
                    "Microsoft.Fabric/capacities",
                    "--query",
                    f"length([?name=='{capacity_name}'])",
                    "--output",
                    "tsv",
                ]
            )
            capacity_absent = capacity_probe.returncode == 0 and capacity_probe.stdout.strip() in {"", "0"}
            if capacity_group_absent and capacity_absent:
                break
            if attempt < 11:
                time.sleep(5)
        checks.append(
            _check(
                "fabric-capacity-resource-group-absent",
                "pass" if capacity_group_absent else "fail",
                f"Generated Fabric capacity resource group {capacity_group} is absent"
                if capacity_group_absent
                else f"Generated Fabric capacity resource group {capacity_group} still exists",
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
    write_lock(config, status="destroyed" if status == "pass" else "cleanup-incomplete", extra={"checks": checks})
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

    init_parser = subparsers.add_parser("init", help="Create an ignored YAML environment ledger.")
    init_parser.add_argument("--profile", choices=["mcp-only", "byo-fabric", "full"], required=True)
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
    verify_parser = subparsers.add_parser("verify", help="Verify deployed resources and retrieve evidence.")
    _common_config_args(verify_parser, require_env=False)
    down_parser = subparsers.add_parser("down", help="Delete only resources owned by an environment.")
    _common_config_args(down_parser, require_env=False)
    down_parser.add_argument("--yes", action="store_true")
    e2e_parser = subparsers.add_parser("e2e", help="Run up, verify, and optional cleanup as one lifecycle test.")
    _common_config_args(e2e_parser, require_env=False)
    e2e_parser.add_argument("--cleanup", action="store_true")
    e2e_parser.add_argument("--keep-resources", action="store_true")
    e2e_parser.add_argument("--yes", action="store_true")
    e2e_parser.add_argument("--accept-fabric-capacity", action="store_true")
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
        if profile == "mcp-only" and field.startswith("fabric."):
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
            return subprocess.run(command, cwd=ROOT, check=False).returncode
        if args.command == "init":
            destination = args.config or ROOT / ".liveks" / f"{args.environment}.yaml"
            if args.from_env:
                _init_from_legacy(args.from_env, args.profile, args.environment, destination)
            else:
                write_user_config(destination, profile=args.profile, environment=args.environment)
            report = envelope("init", "pass", profile=args.profile, environment=args.environment, artifacts=[str(destination.relative_to(ROOT))], nextActions=[f"Review {destination.relative_to(ROOT)}, then run ./liveks doctor --env {args.environment}"])
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
            )
        elif args.command == "verify":
            report = verify_report(config, quiet=args.format == "json")
        elif args.command == "down":
            report = down_report(config, yes=args.yes, quiet=args.format == "json")
        elif args.command == "e2e":
            if args.cleanup == args.keep_resources:
                raise ConfigError("Choose exactly one of --cleanup or --keep-resources.")
            up = up_report(config, yes=args.yes, accept_fabric_capacity=args.accept_fabric_capacity, quiet=args.format == "json")
            cleanup: dict[str, Any] | None = None
            if args.cleanup:
                cleanup = down_report(config, yes=True, quiet=args.format == "json")
            status = "pass" if up["status"] == "pass" and (cleanup is None or cleanup["status"] == "pass") else "fail"
            report = envelope("e2e", status, profile=config.profile, environment=config.environment, phases={"up": up, "down": cleanup}, artifacts=list(dict.fromkeys(up.get("artifacts", []) + (cleanup or {}).get("artifacts", []))))
            write_e2e_reports(config, report, cleanup_requested=args.cleanup)
        else:
            raise ConfigError(f"Unsupported command: {args.command}")
        emit(report, args.format)
        return _exit_code(report)
    except ConfigError as error:
        report = envelope(args.command, "fail", checks=[_check("configuration", "fail", str(error))])
        emit(report, getattr(args, "format", "text"))
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
