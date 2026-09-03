"""Payload and remote-definition contracts for current Knowledge Sources."""

from __future__ import annotations

from typing import Any, Protocol

from ks_factory import (
    create_extracting_knowledge_base,
    create_fabric_ontology_knowledge_source,
    create_knowledge_base,
    create_mcp_server_knowledge_source,
    create_search_index_knowledge_source,
)

from ..config import ResolvedConfig


class KnowledgeSourceOperations(Protocol):
    source_type: str

    def name(self, config: ResolvedConfig) -> str: ...

    def api_version(self, config: ResolvedConfig) -> str: ...

    def build(
        self,
        config: ResolvedConfig,
        *,
        description: str,
    ) -> dict[str, Any]: ...

    def matches(self, payload: Any, config: ResolvedConfig) -> bool: ...

    def retrieval_parameter(
        self,
        config: ResolvedConfig,
        *,
        include_evidence: bool,
    ) -> dict[str, Any]: ...


class SearchIndexSourceOperations:
    source_type = "searchIndex"

    def name(self, config: ResolvedConfig) -> str:
        return str(config.get("search.index_knowledge_source_name"))

    def api_version(self, config: ResolvedConfig) -> str:
        return str(
            config.get("search.index_api_version")
            or config.get("search.api_version")
        )

    def build(
        self,
        config: ResolvedConfig,
        *,
        description: str,
    ) -> dict[str, Any]:
        return create_search_index_knowledge_source(
            name=self.name(config),
            search_index_name=str(config.get("search.index_name")),
            semantic_configuration_name=str(
                config.get("search.semantic_configuration_name")
            ),
            search_fields=list(config.get("search.search_fields", [])),
            source_data_fields=list(config.get("search.source_data_fields", [])),
            description=description,
        )

    def matches(self, payload: Any, config: ResolvedConfig) -> bool:
        parameters = (
            payload.get("searchIndexParameters", {})
            if isinstance(payload, dict)
            else {}
        )
        return (
            isinstance(payload, dict)
            and payload.get("kind") == self.source_type
            and parameters.get("searchIndexName") == config.get("search.index_name")
            and parameters.get("semanticConfigurationName")
            == config.get("search.semantic_configuration_name")
        )

    def retrieval_parameter(
        self,
        config: ResolvedConfig,
        *,
        include_evidence: bool,
    ) -> dict[str, Any]:
        parameter: dict[str, Any] = {
            "knowledgeSourceName": self.name(config),
            "kind": self.source_type,
        }
        if include_evidence:
            parameter.update(
                {
                    "includeReferences": True,
                    "includeReferenceSourceData": True,
                }
            )
        return parameter


class McpServerSourceOperations:
    source_type = "mcpServer"

    def name(self, config: ResolvedConfig) -> str:
        return str(config.get("search.mcp_knowledge_source_name"))

    def api_version(self, config: ResolvedConfig) -> str:
        return str(
            config.get("search.preview_api_version")
            or config.get("search.api_version")
        )

    def build(
        self,
        config: ResolvedConfig,
        *,
        description: str,
    ) -> dict[str, Any]:
        return create_mcp_server_knowledge_source(
            name=self.name(config),
            server_url=str(config.get("mcp.server_url")),
            tool_name=str(config.get("mcp.tool_name")),
            description=description,
        )

    def matches(self, payload: Any, config: ResolvedConfig) -> bool:
        parameters = (
            payload.get("mcpServerParameters", {})
            if isinstance(payload, dict)
            else {}
        )
        tools = parameters.get("tools", []) if isinstance(parameters, dict) else []
        return (
            isinstance(payload, dict)
            and payload.get("kind") == self.source_type
            and parameters.get("serverURL") == config.get("mcp.server_url")
            and any(
                isinstance(tool, dict)
                and tool.get("name") == config.get("mcp.tool_name")
                for tool in tools
            )
        )

    def retrieval_parameter(
        self,
        config: ResolvedConfig,
        *,
        include_evidence: bool,
    ) -> dict[str, Any]:
        parameter: dict[str, Any] = {
            "knowledgeSourceName": self.name(config),
            "kind": self.source_type,
        }
        if include_evidence:
            parameter.update(
                {
                    "includeReferences": True,
                    "includeReferenceSourceData": True,
                }
            )
        return parameter


class FabricOntologySourceOperations:
    source_type = "fabricOntology"

    def name(self, config: ResolvedConfig) -> str:
        return str(config.get("search.fabric_knowledge_source_name"))

    def api_version(self, config: ResolvedConfig) -> str:
        return str(
            config.get("search.preview_api_version")
            or config.get("search.api_version")
        )

    def build(
        self,
        config: ResolvedConfig,
        *,
        description: str,
    ) -> dict[str, Any]:
        return create_fabric_ontology_knowledge_source(
            name=self.name(config),
            workspace_id=str(config.get("fabric.workspace_id")),
            ontology_id=str(config.get("fabric.ontology_id")),
            description=description,
        )

    def matches(self, payload: Any, config: ResolvedConfig) -> bool:
        parameters = (
            payload.get("fabricOntologyParameters", {})
            if isinstance(payload, dict)
            else {}
        )
        return (
            isinstance(payload, dict)
            and payload.get("kind") == self.source_type
            and parameters.get("workspaceId") == config.get("fabric.workspace_id")
            and parameters.get("ontologyId") == config.get("fabric.ontology_id")
        )

    def retrieval_parameter(
        self,
        config: ResolvedConfig,
        *,
        include_evidence: bool,
    ) -> dict[str, Any]:
        parameter: dict[str, Any] = {
            "knowledgeSourceName": self.name(config),
            "kind": self.source_type,
        }
        if include_evidence:
            parameter.update(
                {
                    "includeReferences": True,
                    "includeReferenceSourceData": True,
                }
            )
        return parameter


class KnowledgeBaseOperations:
    def name(self, config: ResolvedConfig, *, stable: bool) -> str:
        field = (
            "search.index_knowledge_base_name"
            if stable
            else "search.combined_knowledge_base_name"
        )
        return str(config.get(field))

    def api_version(self, config: ResolvedConfig, *, stable: bool) -> str:
        if stable:
            return str(
                config.get("search.index_api_version")
                or config.get("search.api_version")
            )
        return str(
            config.get("search.preview_api_version")
            or config.get("search.api_version")
        )

    def build_stable(
        self,
        config: ResolvedConfig,
        source_names: list[str],
        *,
        description: str,
    ) -> dict[str, Any]:
        return create_extracting_knowledge_base(
            name=self.name(config, stable=True),
            knowledge_source_names=source_names,
            description=description,
        )

    def build_preview(
        self,
        config: ResolvedConfig,
        source_names: list[str],
        *,
        description: str,
        retrieval_instructions: str,
    ) -> dict[str, Any]:
        return create_knowledge_base(
            name=self.name(config, stable=False),
            knowledge_source_names=source_names,
            azure_openai_endpoint=str(config.get("openai.endpoint")),
            azure_openai_deployment_id=str(config.get("openai.deployment_name")),
            azure_openai_model_name=str(config.get("openai.model_name")),
            description=description,
            retrieval_instructions=retrieval_instructions,
        )

    def matches_preview(
        self,
        payload: Any,
        config: ResolvedConfig,
        source_names: set[str],
    ) -> bool:
        if not isinstance(payload, dict):
            return False
        actual_sources = {
            str(item.get("name"))
            for item in payload.get("knowledgeSources", [])
            if isinstance(item, dict) and item.get("name")
        }
        models = payload.get("models", [])
        parameters = (
            models[0].get("azureOpenAIParameters", {})
            if models and isinstance(models[0], dict)
            else {}
        )
        return (
            actual_sources == source_names
            and payload.get("outputMode") == "answerSynthesis"
            and payload.get("retrievalReasoningEffort") == {"kind": "low"}
            and parameters.get("resourceUri") == config.get("openai.endpoint")
            and parameters.get("deploymentId")
            == config.get("openai.deployment_name")
            and parameters.get("modelName") == config.get("openai.model_name")
        )

    def matches_stable(
        self,
        payload: Any,
        source_names: set[str],
    ) -> bool:
        if not isinstance(payload, dict):
            return False
        actual_sources = {
            str(item.get("name"))
            for item in payload.get("knowledgeSources", [])
            if isinstance(item, dict) and item.get("name")
        }
        return (
            actual_sources == source_names
            and not {
                "models",
                "outputMode",
                "retrievalReasoningEffort",
            }.intersection(payload)
        )
