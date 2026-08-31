"""Stable Search Index Knowledge Source data-plane contract."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ks_factory import create_extracting_knowledge_base, create_search_index_knowledge_source

from .config import ResolvedConfig
from .runtime import CommandRunner, http_json


def acquire_bearer_token(runner: CommandRunner) -> str:
    """Acquire an Azure AI Search token without printing or persisting it."""
    result = runner.run(
        [
            "az",
            "account",
            "get-access-token",
            "--scope",
            "https://search.azure.com/.default",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        sensitive_output=True,
    )
    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        raise RuntimeError("Unable to acquire an Azure AI Search bearer token.")
    return token


def request(
    config: ResolvedConfig,
    token: str,
    *,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    api_version: str | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 1,
    timeout: int = 120,
) -> tuple[int, Any]:
    endpoint = str(config.get("search.endpoint")).rstrip("/")
    resolved_api_version = str(api_version or config.get("search.api_version"))
    if not resolved_api_version:
        raise ValueError("An explicit Azure AI Search API version is required.")
    encoded_api_version = quote(resolved_api_version, safe="")
    request_headers = dict(headers or {})
    request_headers["Authorization"] = f"Bearer {token}"
    try:
        return http_json(
            f"{endpoint}{path}?api-version={encoded_api_version}",
            method=method,
            body=body,
            headers=request_headers,
            attempts=attempts,
            delay_seconds=2,
            timeout=timeout,
        )
    except Exception as error:
        raise RuntimeError("Azure AI Search request could not be completed.") from error


def object_path(kind: str, name: str) -> str:
    if kind not in {"indexes", "knowledgesources", "knowledgebases"}:
        raise ValueError(f"Unsupported Search object kind: {kind}")
    return f"/{kind}/{quote(name, safe='')}"


def build_payloads(config: ResolvedConfig, *, query: str) -> dict[str, dict[str, Any]]:
    knowledge_source_name = str(config.get("search.index_knowledge_source_name"))
    knowledge_base_name = str(config.get("search.index_knowledge_base_name"))
    knowledge_source = create_search_index_knowledge_source(
        name=knowledge_source_name,
        search_index_name=str(config.get("search.index_name")),
        semantic_configuration_name=str(config.get("search.semantic_configuration_name")),
        search_fields=list(config.get("search.search_fields", [])),
        source_data_fields=list(config.get("search.source_data_fields", [])),
        description="Stable Knowledge Source over an existing Azure AI Search index.",
    )
    knowledge_base = create_extracting_knowledge_base(
        name=knowledge_base_name,
        knowledge_source_names=[knowledge_source_name],
        description="Stable Knowledge Base for extractive retrieval from an existing search index.",
    )
    retrieve = {
        "intents": [{"type": "semantic", "search": query}],
        "knowledgeSourceParams": [
            {
                "knowledgeSourceName": knowledge_source_name,
                "kind": "searchIndex",
            }
        ],
    }
    return {"knowledgeSource": knowledge_source, "knowledgeBase": knowledge_base, "retrieve": retrieve}


def inspect_index(index: Any, config: ResolvedConfig) -> list[tuple[str, str, str]]:
    """Return credential-free assertions for the existing index definition."""
    if not isinstance(index, dict):
        return [("search-index-definition", "fail", "The index definition was not a JSON object.")]

    fields = {
        str(field.get("name")): field
        for field in index.get("fields", [])
        if isinstance(field, dict) and field.get("name")
    }
    semantic = index.get("semantic") if isinstance(index.get("semantic"), dict) else {}
    configurations = {
        str(item.get("name"))
        for item in semantic.get("configurations", [])
        if isinstance(item, dict) and item.get("name")
    }
    semantic_name = str(config.get("search.semantic_configuration_name"))
    checks: list[tuple[str, str, str]] = [
        (
            "semantic-configuration",
            "pass" if semantic_name in configurations else "fail",
            "Configured semantic configuration exists."
            if semantic_name in configurations
            else "Configured semantic configuration was not found on the index.",
        )
    ]

    requested_search_fields = list(config.get("search.search_fields", []))
    missing_search = [name for name in requested_search_fields if name not in fields]
    nonsearchable = [name for name in requested_search_fields if name in fields and not fields[name].get("searchable")]
    search_ok = not missing_search and not nonsearchable
    checks.append(
        (
            "search-fields",
            "pass" if search_ok else "fail",
            "Configured search fields exist and are searchable."
            if search_ok
            else "One or more configured search fields are missing or not searchable.",
        )
    )

    requested_source_fields = list(config.get("search.source_data_fields", []))
    missing_source = [name for name in requested_source_fields if name not in fields]
    nonretrievable = [name for name in requested_source_fields if name in fields and fields[name].get("retrievable") is False]
    source_ok = not missing_source and not nonretrievable
    checks.append(
        (
            "source-data-fields",
            "pass" if source_ok else "fail",
            "Configured source-data fields exist and are retrievable."
            if source_ok
            else "One or more configured source-data fields are missing or not retrievable.",
        )
    )
    return checks


def response_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    blocks: list[str] = []
    for message in payload.get("response", []):
        if not isinstance(message, dict):
            continue
        for item in message.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                blocks.append(str(item.get("text", "")))
    return "\n".join(blocks)


def reference_source_data_text(payload: Any, source_type: str) -> str:
    """Flatten sourceData strings for references produced by one source type."""
    if not isinstance(payload, dict):
        return ""

    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    for reference in payload.get("references", []):
        if isinstance(reference, dict) and reference.get("type") == source_type:
            collect(reference.get("sourceData"))
    return "\n".join(values)
