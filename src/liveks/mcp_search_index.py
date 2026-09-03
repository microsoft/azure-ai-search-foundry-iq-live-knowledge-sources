"""Version-separated direct combined Knowledge Base contracts."""

from __future__ import annotations

import json
from typing import Any

from .providers.sources import (
    FabricOntologySourceOperations,
    KnowledgeBaseOperations,
    McpServerSourceOperations,
    SearchIndexSourceOperations,
)

from .config import ResolvedConfig


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
    fabric_query: str | None = None,
) -> dict[str, Any]:
    """Build version-separated payloads for the combined data-plane profile."""
    index_provider = SearchIndexSourceOperations()
    mcp_provider = McpServerSourceOperations()
    fabric_provider = FabricOntologySourceOperations()
    knowledge_base_provider = KnowledgeBaseOperations()
    index_source_name = index_provider.name(config)
    mcp_source_name = mcp_provider.name(config)
    fabric_source_name = fabric_provider.name(config)
    includes_fabric = config.profile == "three-source"

    index_source = index_provider.build(
        config,
        description="Generally available Knowledge Source over an existing Azure AI Search index.",
    )
    mcp_source = mcp_provider.build(
        config,
        description="Preview MCP Server Knowledge Source for official Microsoft Learn guidance.",
    )
    fabric_source = (
        fabric_provider.build(
            config,
            description="Preview native Fabric Ontology Knowledge Source over existing governed assets.",
        )
        if includes_fabric
        else None
    )
    knowledge_source_names = [index_source_name, mcp_source_name]
    if includes_fabric:
        knowledge_source_names.append(fabric_source_name)
    knowledge_base = knowledge_base_provider.build_preview(
        config,
        knowledge_source_names,
        description=(
            "Preview Knowledge Base combining an existing Search index, an MCP Server, "
            "and a native Fabric ontology."
            if includes_fabric
            else "Preview Knowledge Base combining an existing Search index with an MCP Server."
        ),
        retrieval_instructions=(
            "Use the Search Index Knowledge Source for domain content from the existing index. "
            "Use the MCP Server Knowledge Source for current Microsoft Learn implementation guidance."
            + (
                " Use the native Fabric Ontology Knowledge Source for governed business entities and relationships."
                if includes_fabric
                else ""
            )
        ),
    )
    index_params = index_provider.retrieval_parameter(
        config,
        include_evidence=True,
    )
    mcp_params = mcp_provider.retrieval_parameter(
        config,
        include_evidence=True,
    )
    fabric_params = fabric_provider.retrieval_parameter(
        config,
        include_evidence=True,
    )
    payloads = {
        "searchIndexKnowledgeSource": index_source,
        "mcpKnowledgeSource": mcp_source,
        "knowledgeBase": knowledge_base,
        "retrieve": {
            "searchIndex": _retrieve(index_query, [index_params], max_runtime=60),
            "mcp": _retrieve(mcp_query, [mcp_params], max_runtime=60),
            "combined": _retrieve(
                combined_query,
                [index_params, mcp_params] + ([fabric_params] if includes_fabric else []),
                max_runtime=90,
            ),
        },
    }
    if includes_fabric and fabric_source is not None:
        payloads["fabricKnowledgeSource"] = fabric_source
        payloads["retrieve"]["fabric"] = _retrieve(
            fabric_query or "Query the configured Fabric ontology.",
            [fabric_params],
            max_runtime=60,
        )
    return payloads


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
    fabric_parameters = redacted.get("fabricKnowledgeSource", {}).get(
        "fabricOntologyParameters"
    )
    if isinstance(fabric_parameters, dict):
        fabric_parameters["workspaceId"] = "<redacted-fabric-workspace-id>"
        fabric_parameters["ontologyId"] = "<redacted-fabric-ontology-id>"
    return redacted
