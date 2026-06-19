import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ks_factory import (  # noqa: E402
    create_fabric_ontology_knowledge_source,
    create_knowledge_base,
    create_mcp_server_knowledge_source,
)


class KnowledgeSourceFactoryTests(unittest.TestCase):
    def test_mcp_server_knowledge_source_payload_shape(self):
        payload = create_mcp_server_knowledge_source(
            name="microsoft-learn-mcp-ks",
            server_url="https://learn.microsoft.com/api/mcp",
            tool_name="microsoft_docs_search",
            description="Microsoft Learn MCP source.",
        )

        self.assertEqual(payload["name"], "microsoft-learn-mcp-ks")
        self.assertEqual(payload["kind"], "mcpServer")
        self.assertEqual(payload["mcpServerParameters"]["serverURL"], "https://learn.microsoft.com/api/mcp")

        tools = payload["mcpServerParameters"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "microsoft_docs_search")
        self.assertEqual(tools[0]["outputParsing"], {"kind": "auto"})
        self.assertEqual(tools[0]["inclusionMode"], "reranked")
        self.assertEqual(tools[0]["maxOutputTokens"], 1000)

    def test_fabric_ontology_knowledge_source_payload_shape(self):
        payload = create_fabric_ontology_knowledge_source(
            name="fabric-ontology-ks",
            workspace_id="00000000-0000-0000-0000-000000000000",
            ontology_id="00000000-0000-0000-0000-000000000001",
        )

        self.assertEqual(payload["name"], "fabric-ontology-ks")
        self.assertEqual(payload["kind"], "fabricOntology")
        self.assertEqual(
            payload["fabricOntologyParameters"],
            {
                "workspaceId": "00000000-0000-0000-0000-000000000000",
                "ontologyId": "00000000-0000-0000-0000-000000000001",
            },
        )

    def test_knowledge_base_payload_shape_without_model_secret(self):
        payload = create_knowledge_base(
            name="live-knowledge-sources-kb",
            knowledge_source_names=["microsoft-learn-mcp-ks", "fabric-ontology-ks"],
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_deployment_id="gpt-4o-mini",
            azure_openai_model_name="gpt-4o-mini",
        )

        self.assertEqual(payload["outputMode"], "answerSynthesis")
        self.assertEqual(payload["retrievalReasoningEffort"], {"kind": "low"})
        self.assertEqual(
            payload["knowledgeSources"],
            [{"name": "microsoft-learn-mcp-ks"}, {"name": "fabric-ontology-ks"}],
        )
        self.assertEqual(payload["models"][0]["kind"], "azureOpenAI")
        model_params = payload["models"][0]["azureOpenAIParameters"]
        self.assertEqual(model_params["resourceUri"], "https://example.openai.azure.com")
        self.assertEqual(model_params["deploymentId"], "gpt-4o-mini")
        self.assertEqual(model_params["modelName"], "gpt-4o-mini")
        self.assertNotIn("apiKey", model_params)

    def test_knowledge_base_omits_model_when_model_config_is_incomplete(self):
        payload = create_knowledge_base(
            name="live-knowledge-sources-kb",
            knowledge_source_names=["microsoft-learn-mcp-ks"],
            azure_openai_endpoint="https://example.openai.azure.com",
        )

        self.assertNotIn("models", payload)

    def test_knowledge_base_can_include_model_key_only_when_explicitly_requested(self):
        payload = create_knowledge_base(
            name="live-knowledge-sources-kb",
            knowledge_source_names=["microsoft-learn-mcp-ks"],
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_deployment_id="gpt-4o-mini",
            azure_openai_model_name="gpt-4o-mini",
            azure_openai_api_key="<azure-openai-api-key>",
        )

        model_params = payload["models"][0]["azureOpenAIParameters"]
        self.assertEqual(model_params["apiKey"], "<azure-openai-api-key>")


if __name__ == "__main__":
    unittest.main()
