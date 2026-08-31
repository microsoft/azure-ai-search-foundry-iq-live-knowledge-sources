"""Two-source Search Index and MCP Server Knowledge Base contract."""

from __future__ import annotations

import json
from typing import Any

from ks_factory import (
    create_knowledge_base,
    create_mcp_server_knowledge_source,
    create_search_index_knowledge_source,
)

from .config import ResolvedConfig


def _source_params(name: str, kind: str) -> dict[str, Any]:
    return {
        "knowledgeSourceName": name,
        "kind": kind,
        "includeReferences": True,
        "includeReferenceSourceData": True,
    }


def _retrieve(query: str, sources: list[dict[str, Any]], *, max_runtime: int) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": query}],
            }
        ],
        "includeActivity": True,
        "knowledgeSourceParams": sources,
        "outputMode": "answerSynthesis",
        "retrievalReasoningEffort": {"kind": "low"},
        "maxRuntimeInSeconds": max_runtime,
    }


def build_payloads(
    config: ResolvedConfig,
    *,
    index_query: str,
    mcp_query: str,
    combined_query: str,
) -> dict[str, Any]:
    """Build version-separated payloads for the combined data-plane profile."""
    index_source_name = str(config.get("search.index_knowledge_source_name"))
    mcp_source_name = str(config.get("search.mcp_knowledge_source_name"))

    index_source = create_search_index_knowledge_source(
        name=index_source_name,
        search_index_name=str(config.get("search.index_name")),
        semantic_configuration_name=str(config.get("search.semantic_configuration_name")),
        search_fields=list(config.get("search.search_fields", [])),
        source_data_fields=list(config.get("search.source_data_fields", [])),
        description="Generally available Knowledge Source over an existing Azure AI Search index.",
    )
    mcp_source = create_mcp_server_knowledge_source(
        name=mcp_source_name,
        server_url=str(config.get("mcp.server_url")),
        tool_name=str(config.get("mcp.tool_name")),
        description="Preview MCP Server Knowledge Source for official Microsoft Learn guidance.",
    )
    knowledge_base = create_knowledge_base(
        name=str(config.get("search.combined_knowledge_base_name")),
        knowledge_source_names=[index_source_name, mcp_source_name],
        azure_openai_endpoint=str(config.get("openai.endpoint")),
        azure_openai_deployment_id=str(config.get("openai.deployment_name")),
        azure_openai_model_name=str(config.get("openai.model_name")),
        description="Preview Knowledge Base combining an existing Search index with an MCP Server.",
        retrieval_instructions=(
            "Use the Search Index Knowledge Source for domain content from the existing index. "
            "Use the MCP Server Knowledge Source for current Microsoft Learn implementation guidance."
        ),
    )
    index_params = _source_params(index_source_name, "searchIndex")
    mcp_params = _source_params(mcp_source_name, "mcpServer")
    return {
        "searchIndexKnowledgeSource": index_source,
        "mcpKnowledgeSource": mcp_source,
        "knowledgeBase": knowledge_base,
        "retrieve": {
            "searchIndex": _retrieve(index_query, [index_params], max_runtime=60),
            "mcp": _retrieve(mcp_query, [mcp_params], max_runtime=60),
            "combined": _retrieve(combined_query, [index_params, mcp_params], max_runtime=90),
        },
    }


def redacted_payloads(payloads: dict[str, Any]) -> dict[str, Any]:
    """Return plan-safe payloads without model endpoints or runtime questions."""
    redacted = json.loads(json.dumps(payloads))
    models = redacted.get("knowledgeBase", {}).get("models", [])
    for model in models:
        parameters = model.get("azureOpenAIParameters")
        if isinstance(parameters, dict) and "resourceUri" in parameters:
            parameters["resourceUri"] = "<redacted-azure-openai-endpoint>"
        if isinstance(parameters, dict):
            parameters.pop("apiKey", None)
    for request in redacted.get("retrieve", {}).values():
        if isinstance(request, dict):
            request["messages"] = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "<runtime-query-not-persisted>"}],
                }
            ]
    return redacted
