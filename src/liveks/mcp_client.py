"""Lifecycle-neutral client contract for an Azure AI Search Knowledge Base MCP endpoint."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

from .compatibility import PREVIEW_SEARCH_API_VERSION
from .runtime import http_mcp_json


KNOWLEDGE_BASE_RETRIEVE_TOOL = "knowledge_base_retrieve"
CHECK_NAMES = (
    "endpoint-configuration",
    "authentication-readiness",
    "tools-list",
    "tools-call",
    "text-content",
    "grounding-content",
)
AUTH_MODES = frozenset({"bearer", "admin-key"})
CONFIGURATION_ERROR_CATEGORIES = frozenset(
    {
        "missing-configuration",
        "invalid-endpoint",
        "unsupported-api-version",
        "unsupported-auth-mode",
        "missing-credential",
        "invalid-credential",
    }
)

McpRequest = Callable[..., tuple[int, Any]]


@dataclass(frozen=True)
class McpConsumerConfig:
    endpoint: str = field(repr=False)
    auth_mode: str
    credential: str = field(repr=False)
    query: str = field(repr=False)
    expected_term: str = field(repr=False)
    source_authorization: str = field(default="", repr=False)
    api_version: str = PREVIEW_SEARCH_API_VERSION


def tools_list_request() -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


def tools_call_request(query: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": KNOWLEDGE_BASE_RETRIEVE_TOOL,
            "arguments": {"queries": [query]},
        },
    }


def mcp_text_blocks(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    content = result.get("content")
    if not isinstance(content, list):
        return []
    return [
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]


def mcp_has_tool(payload: Any, tool_name: str = KNOWLEDGE_BASE_RETRIEVE_TOOL) -> bool:
    if not isinstance(payload, dict):
        return False
    result = payload.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    return isinstance(tools, list) and any(
        isinstance(tool, dict) and tool.get("name") == tool_name for tool in tools
    )


def mcp_tool_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    result = payload.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    return (
        sum(1 for tool in tools if isinstance(tool, dict))
        if isinstance(tools, list)
        else 0
    )


def mcp_tool_error(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("result"), dict)
        and bool(payload["result"].get("isError"))
    )


def mcp_failure_category(status_code: int, payload: Any) -> str:
    if status_code in {401, 403}:
        return "authentication-rejected"
    if status_code == 404:
        return "endpoint-not-found"
    if status_code == 408:
        return "request-timeout-exhausted"
    if status_code == 429:
        return "throttling-exhausted"
    if status_code >= 500:
        return "service-error"
    if status_code >= 400:
        return "http-error"
    if isinstance(payload, dict) and payload.get("error"):
        return "json-rpc-error"
    if mcp_tool_error(payload):
        return "tool-call-error"
    return "malformed-response"


def transport_exception_category(error: BaseException) -> str:
    if isinstance(error, (json.JSONDecodeError, ValueError)):
        return "malformed-response"
    normalized = str(error).casefold()
    if "network-timeout" in normalized:
        return "network-timeout-exhausted"
    return "network-error"


def _blank_checks() -> dict[str, dict[str, Any]]:
    return {
        name: {"name": name, "status": "not-run"}
        for name in CHECK_NAMES
    }


def _set_check(
    checks: dict[str, dict[str, Any]],
    name: str,
    status: str,
    *,
    error_category: str | None = None,
    **counts: int,
) -> None:
    check: dict[str, Any] = {"name": name, "status": status}
    if error_category:
        check["errorCategory"] = error_category
    for key, value in counts.items():
        check[key] = int(value)
    checks[name] = check


def _report(
    checks: dict[str, dict[str, Any]],
    *,
    auth_mode: str,
    source_authorization: bool,
) -> dict[str, Any]:
    ordered = [checks[name] for name in CHECK_NAMES]
    status = "fail" if any(check["status"] == "fail" for check in ordered) else "pass"
    return {
        "schemaVersion": 1,
        "command": "knowledge-base-mcp-consumer",
        "status": status,
        "mode": {
            "apiVersion": PREVIEW_SEARCH_API_VERSION,
            "authentication": auth_mode if auth_mode in AUTH_MODES else "unresolved",
            "sourceAuthorization": "present" if source_authorization else "absent",
            "transport": "stateless-json-rpc-2.0-over-https",
            "responseFormats": ["json", "sse"],
        },
        "checks": ordered,
    }


def _configuration_failure(
    category: str,
    *,
    check_name: str,
    auth_mode: str,
    source_authorization: bool,
) -> dict[str, Any]:
    checks = _blank_checks()
    _set_check(checks, check_name, "fail", error_category=category)
    return _report(
        checks,
        auth_mode=auth_mode,
        source_authorization=source_authorization,
    )


def _valid_mcp_endpoint(endpoint: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit(endpoint)
        query = parse_qs(parsed.query, strict_parsing=True)
    except ValueError:
        return False, "invalid-endpoint"
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".search.windows.net")
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        return False, "invalid-endpoint"
    segments = [segment for segment in parsed.path.split("/") if segment]
    if (
        len(segments) != 3
        or segments[0] != "knowledgebases"
        or not segments[1]
        or segments[2] != "mcp"
    ):
        return False, "invalid-endpoint"
    versions = query.get("api-version", [])
    if set(query) != {"api-version"} or versions != [PREVIEW_SEARCH_API_VERSION]:
        return False, "unsupported-api-version"
    return True, ""


def config_from_environment(
    environ: Mapping[str, str],
) -> tuple[McpConsumerConfig | None, dict[str, Any] | None]:
    endpoint = str(environ.get("AZURE_SEARCH_MCP_ENDPOINT", "")).strip()
    auth_mode = (
        str(environ.get("AZURE_SEARCH_MCP_AUTH_MODE", "bearer"))
        .strip()
        .casefold()
    )
    query = str(environ.get("AZURE_SEARCH_MCP_QUERY", "")).strip()
    expected_term = str(environ.get("AZURE_SEARCH_MCP_EXPECT_TERM", "")).strip()
    source_authorization = str(
        environ.get("AZURE_SEARCH_MCP_SOURCE_AUTHORIZATION", "")
    ).strip()

    if not endpoint or not query or not expected_term:
        return None, _configuration_failure(
            "missing-configuration",
            check_name="endpoint-configuration",
            auth_mode=auth_mode,
            source_authorization=bool(source_authorization),
        )
    endpoint_valid, endpoint_category = _valid_mcp_endpoint(endpoint)
    if not endpoint_valid:
        return None, _configuration_failure(
            endpoint_category,
            check_name="endpoint-configuration",
            auth_mode=auth_mode,
            source_authorization=bool(source_authorization),
        )
    if auth_mode not in AUTH_MODES:
        return None, _configuration_failure(
            "unsupported-auth-mode",
            check_name="authentication-readiness",
            auth_mode=auth_mode,
            source_authorization=bool(source_authorization),
        )
    credential_name = (
        "AZURE_SEARCH_MCP_BEARER_TOKEN"
        if auth_mode == "bearer"
        else "AZURE_SEARCH_ADMIN_KEY"
    )
    credential = str(environ.get(credential_name, "")).strip()
    if not credential:
        return None, _configuration_failure(
            "missing-credential",
            check_name="authentication-readiness",
            auth_mode=auth_mode,
            source_authorization=bool(source_authorization),
        )
    if any(
        character in credential or character in source_authorization
        for character in "\r\n"
    ):
        return None, _configuration_failure(
            "invalid-credential",
            check_name="authentication-readiness",
            auth_mode=auth_mode,
            source_authorization=bool(source_authorization),
        )
    return (
        McpConsumerConfig(
            endpoint=endpoint,
            auth_mode=auth_mode,
            credential=credential,
            query=query,
            expected_term=expected_term,
            source_authorization=source_authorization,
        ),
        None,
    )


def _headers(config: McpConsumerConfig) -> dict[str, str]:
    headers = (
        {"Authorization": f"Bearer {config.credential}"}
        if config.auth_mode == "bearer"
        else {"api-key": config.credential}
    )
    if config.source_authorization:
        headers["x-ms-query-source-authorization"] = config.source_authorization
    return headers


def run_consumer(
    config: McpConsumerConfig,
    *,
    request: McpRequest = http_mcp_json,
) -> dict[str, Any]:
    checks = _blank_checks()
    _set_check(checks, "endpoint-configuration", "pass")
    _set_check(
        checks,
        "authentication-readiness",
        "pass",
        headerCount=2 if config.source_authorization else 1,
    )
    headers = _headers(config)

    try:
        list_code, list_payload = request(
            config.endpoint,
            body=tools_list_request(),
            headers=headers,
            attempts=3,
            delay_seconds=3,
            timeout=30,
            retry_mode="read",
        )
    except Exception as error:
        _set_check(
            checks,
            "tools-list",
            "fail",
            error_category=transport_exception_category(error),
        )
        return _report(
            checks,
            auth_mode=config.auth_mode,
            source_authorization=bool(config.source_authorization),
        )

    if list_code != 200 or (isinstance(list_payload, dict) and list_payload.get("error")):
        _set_check(
            checks,
            "tools-list",
            "fail",
            error_category=mcp_failure_category(list_code, list_payload),
            toolCount=mcp_tool_count(list_payload),
        )
        return _report(
            checks,
            auth_mode=config.auth_mode,
            source_authorization=bool(config.source_authorization),
        )
    if not mcp_has_tool(list_payload):
        _set_check(
            checks,
            "tools-list",
            "fail",
            error_category="missing-tool",
            toolCount=mcp_tool_count(list_payload),
        )
        return _report(
            checks,
            auth_mode=config.auth_mode,
            source_authorization=bool(config.source_authorization),
        )
    _set_check(
        checks,
        "tools-list",
        "pass",
        toolCount=mcp_tool_count(list_payload),
    )

    try:
        call_code, call_payload = request(
            config.endpoint,
            body=tools_call_request(config.query),
            headers=headers,
            attempts=3,
            delay_seconds=3,
            timeout=180,
            retry_mode="read",
        )
    except Exception as error:
        _set_check(
            checks,
            "tools-call",
            "fail",
            error_category=transport_exception_category(error),
        )
        return _report(
            checks,
            auth_mode=config.auth_mode,
            source_authorization=bool(config.source_authorization),
        )

    if (
        call_code != 200
        or (isinstance(call_payload, dict) and call_payload.get("error"))
        or mcp_tool_error(call_payload)
    ):
        _set_check(
            checks,
            "tools-call",
            "fail",
            error_category=mcp_failure_category(call_code, call_payload),
        )
        return _report(
            checks,
            auth_mode=config.auth_mode,
            source_authorization=bool(config.source_authorization),
        )
    _set_check(checks, "tools-call", "pass")

    text_blocks = [text for text in mcp_text_blocks(call_payload) if text.strip()]
    if not text_blocks:
        _set_check(
            checks,
            "text-content",
            "fail",
            error_category="missing-text-content",
            contentBlockCount=0,
        )
        return _report(
            checks,
            auth_mode=config.auth_mode,
            source_authorization=bool(config.source_authorization),
        )
    _set_check(
        checks,
        "text-content",
        "pass",
        contentBlockCount=len(text_blocks),
    )

    matched = int(
        config.expected_term.casefold()
        in "\n".join(text_blocks).casefold()
    )
    _set_check(
        checks,
        "grounding-content",
        "pass" if matched else "fail",
        error_category=None if matched else "expected-term-mismatch",
        expectedTermCount=1,
        matchedExpectedTermCount=matched,
    )
    return _report(
        checks,
        auth_mode=config.auth_mode,
        source_authorization=bool(config.source_authorization),
    )


def run_from_environment(
    environ: Mapping[str, str],
    *,
    request: McpRequest = http_mcp_json,
) -> dict[str, Any]:
    config, failure = config_from_environment(environ)
    if failure is not None:
        return failure
    if config is None:
        raise RuntimeError("MCP consumer configuration resolution failed.")
    return run_consumer(config, request=request)


def exit_code(report: Mapping[str, Any]) -> int:
    if report.get("status") == "pass":
        return 0
    checks = report.get("checks", [])
    categories = {
        str(check.get("errorCategory"))
        for check in checks
        if isinstance(check, dict) and check.get("errorCategory")
    }
    return 2 if categories.intersection(CONFIGURATION_ERROR_CATEGORIES) else 1


def format_text(report: Mapping[str, Any]) -> str:
    lines = [
        f"Knowledge Base MCP consumer: {str(report.get('status', 'fail')).upper()}"
    ]
    for check in report.get("checks", []):
        if not isinstance(check, dict):
            continue
        suffix = (
            f" ({check['errorCategory']})"
            if check.get("errorCategory")
            else ""
        )
        lines.append(
            f"[{str(check.get('status', 'not-run')).upper()}] "
            f"{check.get('name', 'unknown')}{suffix}"
        )
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    request: McpRequest | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Call an Azure AI Search Knowledge Base MCP endpoint using environment-only "
            "configuration and emit sanitized evidence."
        )
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    report = run_from_environment(
        os.environ if environ is None else environ,
        request=http_mcp_json if request is None else request,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_text(report))
    return exit_code(report)
