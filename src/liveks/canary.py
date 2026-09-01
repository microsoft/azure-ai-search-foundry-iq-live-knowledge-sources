"""Protected lifecycle canary configuration and sanitized evidence helpers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import ConfigError, ResolvedConfig, resolve_config
from .evidence import generated_at, repository_revision, sha256_file, write_json


REQUIRED_CANARY_CONFIGURATION = (
    "AZURE_CLIENT_ID",
    "AZURE_TENANT_ID",
    "AZURE_SUBSCRIPTION_ID",
    "SEARCH_ENDPOINT",
    "SEARCH_INDEX_NAME",
    "SEARCH_SEMANTIC_CONFIGURATION_NAME",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT_ID",
    "AZURE_OPENAI_MODEL_NAME",
    "LIVEKS_INDEX_QUERY",
    "LIVEKS_INDEX_EXPECT_TERM",
    "LIVEKS_COMBINED_QUERY",
)
CANARY_ASSERTION_ALLOWLIST = frozenset(
    {
        "environment-lock",
        "version-separated-payload-contract",
        "search-index-retrieve",
        "grounding-content",
        "mcp-retrieve",
        "combined-retrieve",
        "ownership",
        "delete-combinedKnowledgeBase",
        "delete-mcpKnowledgeSource",
        "delete-searchIndexKnowledgeSource",
        "search-index-preserved",
        "azure-openai-preserved",
        "cleanup-authorization",
    }
)
SOURCE_TYPES = frozenset({"searchIndex", "mcpServer"})
ALLOWED_STATUSES = frozenset(
    {
        "pass",
        "fail",
        "warn",
        "skip",
        "skipped",
        "unknown",
        "cleanup-incomplete",
        "not-run",
    }
)
CAPSULE_KEYS = frozenset(
    {
        "schemaVersion",
        "kind",
        "status",
        "generatedAt",
        "repositoryRevision",
        "profile",
        "protectedLive",
        "assertions",
        "sourceEvidence",
        "retries",
        "ownership",
        "costSensitiveResourceClasses",
        "cleanup",
        "detailedReport",
        "privacy",
    }
)
GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
URL_RE = re.compile(r"https?://", re.IGNORECASE)
SAFE_RETRY_CATEGORY_RE = re.compile(
    r"^(?:http-(?:408|429|500|502|503|504)|network-timeout)"
    r"(?:-(?:exhausted|unsafe-not-retried|non-retryable))?$"
)


class CanaryConfigurationError(ValueError):
    """Raised when protected canary inputs are incomplete or unsafe."""


def missing_canary_configuration(
    environ: Mapping[str, str],
    required: Sequence[str] = REQUIRED_CANARY_CONFIGURATION,
) -> list[str]:
    return sorted(name for name in required if not str(environ.get(name, "")).strip())


def generated_canary_environment(run_id: str, run_attempt: str) -> str:
    raw = f"canary-{run_id}-{run_attempt}".lower()
    value = re.sub(r"[^a-z0-9-]", "-", raw)
    value = re.sub(r"-+", "-", value).strip("-")[:63]
    if len(value) < 3 or not value[0].isalpha():
        raise CanaryConfigurationError("Generated canary environment is invalid.")
    return value


def write_canary_config(
    root: Path,
    *,
    environment: str,
    environ: Mapping[str, str],
) -> tuple[Path, ResolvedConfig]:
    missing = missing_canary_configuration(environ)
    if missing:
        raise CanaryConfigurationError(
            "Missing required protected canary configuration: " + ", ".join(missing)
        )

    import yaml

    data = {
        "version": 2,
        "profile": "mcp-search-index",
        "environment": environment,
        "azure": {
            "tenant_id": environ["AZURE_TENANT_ID"],
            "subscription_id": environ["AZURE_SUBSCRIPTION_ID"],
        },
        "search": {
            "endpoint": environ["SEARCH_ENDPOINT"],
            "index_name": environ["SEARCH_INDEX_NAME"],
            "semantic_configuration_name": environ["SEARCH_SEMANTIC_CONFIGURATION_NAME"],
            "search_fields": [],
            "source_data_fields": [],
        },
        "openai": {
            "endpoint": environ["AZURE_OPENAI_ENDPOINT"],
            "deployment_name": environ["AZURE_OPENAI_DEPLOYMENT_ID"],
            "model_name": environ["AZURE_OPENAI_MODEL_NAME"],
        },
    }
    path = root / ".liveks" / f"{environment}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    path.chmod(0o600)
    try:
        config = resolve_config(
            profile=None,
            environment=None,
            config_path=path,
        )
    except ConfigError as error:
        raise CanaryConfigurationError(
            "Protected canary configuration is invalid: " + str(error)
        ) from error
    return path, config


def protected_lifecycle_arguments(
    *,
    config_path: Path,
    environment: str,
    environ: Mapping[str, str],
) -> list[str]:
    missing = missing_canary_configuration(environ)
    if missing:
        raise CanaryConfigurationError(
            "Missing required protected canary configuration: " + ", ".join(missing)
        )
    arguments = [
        "e2e",
        "--config",
        str(config_path),
        "--env",
        environment,
        "--cleanup",
        "--yes",
        "--format",
        "json",
        "--query",
        environ["LIVEKS_INDEX_QUERY"],
        "--expect-term",
        environ["LIVEKS_INDEX_EXPECT_TERM"],
        "--combined-query",
        environ["LIVEKS_COMBINED_QUERY"],
    ]
    mcp_query = str(environ.get("LIVEKS_MCP_QUERY", "")).strip()
    if mcp_query:
        arguments.extend(["--mcp-query", mcp_query])
    return arguments


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _safe_status(value: Any, default: str = "unknown") -> str:
    normalized = str(value or default).lower()
    return normalized if normalized in ALLOWED_STATUSES else default


def _collect_assertions(report: dict[str, Any] | None) -> list[dict[str, str]]:
    assertions: list[dict[str, str]] = []
    if not report:
        return assertions
    phases = report.get("phases")
    if not isinstance(phases, dict):
        return assertions
    for phase in ("up", "down"):
        phase_report = phases.get(phase)
        if not isinstance(phase_report, dict):
            continue
        for check in phase_report.get("checks", []):
            if not isinstance(check, dict):
                continue
            name = str(check.get("name") or "")
            if name not in CANARY_ASSERTION_ALLOWLIST:
                continue
            assertions.append(
                {
                    "phase": phase,
                    "name": name,
                    "status": _safe_status(check.get("status")),
                }
            )
    return assertions


def _source_counts(report: dict[str, Any] | None) -> dict[str, int]:
    counts = {source_type: 0 for source_type in SOURCE_TYPES}
    if not report:
        return counts
    phases = report.get("phases")
    up = phases.get("up") if isinstance(phases, dict) else None
    if not isinstance(up, dict):
        return counts
    for check in up.get("checks", []):
        if not isinstance(check, dict):
            continue
        if check.get("name") == "search-index-retrieve":
            count = check.get("evidenceCount")
            if isinstance(count, int) and count >= 0:
                counts["searchIndex"] += count
        elif check.get("name") == "mcp-retrieve":
            count = check.get("evidenceCount")
            if isinstance(count, int) and count >= 0:
                counts["mcpServer"] += count
        elif check.get("name") == "combined-retrieve":
            source_counts = check.get("sourceCounts")
            if isinstance(source_counts, dict):
                for source_type in SOURCE_TYPES:
                    count = source_counts.get(source_type)
                    if isinstance(count, int) and count >= 0:
                        counts[source_type] += count
    return dict(sorted(counts.items()))


def _merge_retry_summaries(*reports: dict[str, Any] | None) -> dict[str, Any]:
    retry_count = 0
    recovered_count = 0
    category_counts: dict[str, int] = {}
    terminal_categories: dict[str, int] = {}
    for report in reports:
        summary = report.get("retrySummary") if isinstance(report, dict) else None
        if not isinstance(summary, dict):
            continue
        count = summary.get("retryCount")
        recovered = summary.get("recoveredCount")
        if isinstance(count, int) and count >= 0:
            retry_count += count
        if isinstance(recovered, int) and recovered >= 0:
            recovered_count += recovered
        for target, key in (
            (category_counts, "categoryCounts"),
            (terminal_categories, "terminalCategories"),
        ):
            values = summary.get(key)
            if not isinstance(values, dict):
                continue
            for category, value in values.items():
                if (
                    SAFE_RETRY_CATEGORY_RE.fullmatch(str(category))
                    and isinstance(value, int)
                    and value >= 0
                ):
                    target[str(category)] = target.get(str(category), 0) + value
    return {
        "retryCount": retry_count,
        "recoveredCount": recovered_count,
        "categoryCounts": dict(sorted(category_counts.items())),
        "terminalCategories": dict(sorted(terminal_categories.items())),
    }


def _cleanup_status(
    e2e_report: dict[str, Any] | None,
    cleanup_report: dict[str, Any] | None,
) -> str:
    if cleanup_report:
        return _safe_status(cleanup_report.get("status"))
    phases = e2e_report.get("phases") if isinstance(e2e_report, dict) else None
    down = phases.get("down") if isinstance(phases, dict) else None
    return _safe_status(down.get("status"), "not-run") if isinstance(down, dict) else "not-run"


def assert_canary_evidence_safe(capsule: dict[str, Any]) -> None:
    unknown_keys = set(capsule) - CAPSULE_KEYS
    if unknown_keys:
        raise ValueError("Canary capsule has unsupported fields: " + ", ".join(sorted(unknown_keys)))
    serialized = json.dumps(capsule, sort_keys=True)
    if URL_RE.search(serialized):
        raise ValueError("Canary capsule contains a URL.")
    if GUID_RE.search(serialized):
        raise ValueError("Canary capsule contains a GUID-shaped identifier.")
    forbidden_keys = {
        "answer",
        "endpoint",
        "environment",
        "payload",
        "query",
        "resourceName",
        "subscriptionId",
        "tenantId",
        "token",
    }

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            overlap = forbidden_keys.intersection(value)
            if overlap:
                raise ValueError(
                    "Canary capsule contains forbidden fields: " + ", ".join(sorted(overlap))
                )
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)

    inspect(capsule)


def build_canary_evidence(
    root: Path,
    *,
    environment: str,
    preflight_outcome: str,
    login_outcome: str,
    lifecycle_outcome: str,
    cleanup_outcome: str,
    output_path: Path,
    detail_path: Path,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    e2e_report_path = root / "deployments" / environment / "e2e-report.json"
    cleanup_report_path = root / ".deployment" / "canary-cleanup.json"
    e2e_report = _load_json(e2e_report_path)
    cleanup_report = _load_json(cleanup_report_path)
    cleanup_status = _cleanup_status(e2e_report, cleanup_report)

    ran = (
        preflight_outcome == "success"
        and login_outcome == "success"
        and lifecycle_outcome not in {"", "skipped", "not-run"}
    )
    status = (
        "not-run"
        if not ran
        else "pass"
        if lifecycle_outcome == "success" and cleanup_status == "pass"
        else "fail"
    )
    assertions = _collect_assertions(e2e_report)
    counts = _source_counts(e2e_report)
    retries = _merge_retry_summaries(e2e_report, cleanup_report)

    detail = {
        "schemaVersion": 1,
        "kind": "protected-canary-detail",
        "stepOutcomes": {
            "preflight": preflight_outcome or "unknown",
            "login": login_outcome or "unknown",
            "lifecycle": lifecycle_outcome or "unknown",
            "cleanup": cleanup_outcome or "unknown",
        },
        "e2eReportPresent": e2e_report is not None,
        "e2eReportSha256": (
            sha256_file(e2e_report_path)
            if e2e_report is not None
            else "unavailable"
        ),
        "cleanupReportPresent": cleanup_report is not None,
        "assertionCount": len(assertions),
        "retrySummary": retries,
    }
    write_json(detail_path, detail)
    detailed_report_path = e2e_report_path if e2e_report is not None else detail_path

    capsule = {
        "schemaVersion": 1,
        "kind": "liveks-protected-canary-evidence",
        "status": status,
        "generatedAt": generated_at(),
        "repositoryRevision": repository_revision(root),
        "profile": "mcp-search-index",
        "protectedLive": {
            "status": "run" if ran else "not-run",
            "trigger": "workflow-dispatch",
        },
        "assertions": assertions,
        "sourceEvidence": {
            "types": sorted(source_type for source_type, count in counts.items() if count > 0),
            "counts": counts,
        },
        "retries": retries,
        "ownership": {
            "generated": {
                "knowledgeBases": 1,
                "knowledgeSources": 2,
            },
            "byo": [
                "azureOpenAIDeployment",
                "remoteMcpServer",
                "searchIndex",
                "searchService",
            ],
            "fabric": "none",
        },
        "costSensitiveResourceClasses": [
            "azureAISearchRetrieval",
            "azureOpenAIModelUsage",
            "remoteMcpService",
        ],
        "cleanup": {
            "requested": True,
            "status": cleanup_status,
        },
        "detailedReport": {
            "kind": "e2e-report" if e2e_report is not None else "protected-canary-detail",
            "sha256": sha256_file(detailed_report_path),
        },
        "privacy": {
            "answersIncluded": False,
            "credentialsIncluded": False,
            "customerDataIncluded": False,
            "identifiersIncluded": False,
            "queriesIncluded": False,
            "rawPayloadsIncluded": False,
            "resourceNamesIncluded": False,
            "serviceEndpointsIncluded": False,
        },
    }
    assert_canary_evidence_safe(capsule)
    write_json(output_path, capsule)

    if summary_path is not None:
        lines = [
            "## Protected MCP + Search Index canary",
            "",
            f"- Status: `{status.upper()}`",
            f"- Protected live execution: `{'RUN' if ran else 'NOT RUN'}`",
            f"- Revision: `{capsule['repositoryRevision']}`",
            f"- Profile: `{capsule['profile']}`",
            f"- Assertions retained: `{len(assertions)}`",
            f"- Source evidence: `searchIndex={counts['searchIndex']}, mcpServer={counts['mcpServer']}`",
            f"- Retries: `{retries['retryCount']}`",
            f"- Cleanup: `{cleanup_status.upper()}`",
            f"- Detailed report digest: `{capsule['detailedReport']['sha256']}`",
            "",
            "Only the allowlist-sanitized capsule is uploaded.",
            "",
        ]
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    return capsule


def preflight_from_environment(
    root: Path,
    *,
    environment: str,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, ResolvedConfig]:
    return write_canary_config(
        root,
        environment=environment,
        environ=environ or os.environ,
    )
