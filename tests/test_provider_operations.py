from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.compatibility import (
    PREVIEW_SEARCH_API_VERSION,
    STABLE_SEARCH_API_VERSION,
)
from liveks.evidence import evidence_count, evidence_types, response_has_evidence
from liveks.providers import (
    FabricOntologySourceOperations,
    KnowledgeBaseOperations,
    McpServerSourceOperations,
    SearchDataPlaneOperations,
    SearchIndexSourceOperations,
    SearchObjectSpec,
    payload_is_subset,
)


class ConfigStub:
    def __init__(self) -> None:
        self.values = {
            "search.api_version": STABLE_SEARCH_API_VERSION,
            "search.index_api_version": STABLE_SEARCH_API_VERSION,
            "search.preview_api_version": PREVIEW_SEARCH_API_VERSION,
            "search.index_name": "existing-index",
            "search.semantic_configuration_name": "semantic-default",
            "search.search_fields": ["title", "content"],
            "search.source_data_fields": ["id", "title"],
            "search.index_knowledge_source_name": "index-ks",
            "search.mcp_knowledge_source_name": "mcp-ks",
            "search.fabric_knowledge_source_name": "fabric-ks",
            "search.index_knowledge_base_name": "index-kb",
            "search.combined_knowledge_base_name": "combined-kb",
            "mcp.server_url": "https://learn.microsoft.com/api/mcp",
            "mcp.tool_name": "microsoft_docs_search",
            "fabric.workspace_id": "00000000-0000-0000-0000-000000000001",
            "fabric.ontology_id": "00000000-0000-0000-0000-000000000002",
            "openai.endpoint": "https://example.openai.azure.com",
            "openai.deployment_name": "gpt-deployment",
            "openai.model_name": "gpt-4.1",
        }

    def get(self, key: str, default=None):
        return self.values.get(key, default)


class SearchDataPlaneOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ConfigStub()
        self.spec = SearchObjectSpec(
            "knowledgesources",
            "index-ks",
            STABLE_SEARCH_API_VERSION,
            {"name": "index-ks", "kind": "searchIndex"},
        )

    def test_crud_and_retrieve_keep_api_versions_and_conditions(self):
        responses = iter(
            [
                (200, {"@odata.etag": "read-etag"}),
                (201, {"@odata.etag": "create-etag"}),
                (200, {"activity": [{"type": "searchIndex"}]}),
                (204, {}),
            ]
        )
        request = mock.Mock(side_effect=lambda *args, **kwargs: next(responses))
        operations = SearchDataPlaneOperations(self.config, "token", request)

        read = operations.read(self.spec)
        created = operations.create(self.spec)
        retrieved = operations.retrieve(
            SearchObjectSpec(
                "knowledgebases",
                "combined-kb",
                PREVIEW_SEARCH_API_VERSION,
            ),
            {"messages": [{"role": "user", "content": "synthetic"}]},
            headers={"x-ms-query-source-authorization": "transient"},
        )
        deleted = operations.delete(self.spec, etag="create-etag")

        self.assertEqual(read.etag, "read-etag")
        self.assertEqual(created.etag, "create-etag")
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(deleted.status_code, 204)
        calls = request.call_args_list
        self.assertEqual([call.kwargs["method"] for call in calls], ["GET", "PUT", "POST", "DELETE"])
        self.assertEqual(calls[0].kwargs["api_version"], STABLE_SEARCH_API_VERSION)
        self.assertEqual(
            calls[1].kwargs["headers"],
            {"If-None-Match": "*", "Prefer": "return=representation"},
        )
        self.assertEqual(calls[2].kwargs["api_version"], PREVIEW_SEARCH_API_VERSION)
        self.assertEqual(
            calls[2].kwargs["path"],
            "/knowledgebases/combined-kb/retrieve",
        )
        self.assertEqual(
            calls[2].kwargs["headers"],
            {"x-ms-query-source-authorization": "transient"},
        )
        self.assertEqual(calls[3].kwargs["headers"], {"If-Match": "create-etag"})

    def test_create_reconciles_an_ambiguous_response(self):
        def request(config, token, *, method, **kwargs):
            if method == "PUT":
                raise TimeoutError("ambiguous")
            return 200, {
                **self.spec.payload,
                "@odata.etag": "reconciled-etag",
            }

        result = SearchDataPlaneOperations(
            self.config,
            "token",
            request,
        ).create(self.spec)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.etag, "reconciled-etag")
        self.assertTrue(result.reconciled)

    def test_failures_are_normalized_without_exception_content(self):
        def request(*args, **kwargs):
            raise RuntimeError("sensitive remote response")

        operations = SearchDataPlaneOperations(self.config, "token", request)

        results = [
            operations.read(self.spec),
            operations.create(self.spec),
            operations.retrieve(
                SearchObjectSpec(
                    "knowledgebases",
                    "combined-kb",
                    PREVIEW_SEARCH_API_VERSION,
                ),
                {"messages": []},
            ),
            operations.delete(self.spec, etag="authorized-etag"),
        ]

        self.assertTrue(all(result.status_code == 0 for result in results))
        self.assertTrue(all(result.payload == {} for result in results))
        self.assertNotIn("sensitive", repr(results))

    def test_delete_requires_lifecycle_authorized_etag(self):
        operations = SearchDataPlaneOperations(
            self.config,
            "token",
            mock.Mock(),
        )

        with self.assertRaisesRegex(ValueError, "authorized ETag"):
            operations.delete(self.spec, etag="")

        operations.request.assert_not_called()

    def test_payload_subset_allows_service_metadata_but_not_drift(self):
        self.assertTrue(
            payload_is_subset(
                self.spec.payload,
                {**self.spec.payload, "@odata.etag": "etag"},
            )
        )
        self.assertFalse(
            payload_is_subset(
                self.spec.payload,
                {"name": "index-ks", "kind": "mcpServer"},
            )
        )


class KnowledgeSourceOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ConfigStub()

    def test_current_source_contracts_keep_stable_and_preview_pins(self):
        search = SearchIndexSourceOperations()
        mcp = McpServerSourceOperations()
        fabric = FabricOntologySourceOperations()

        search_payload = search.build(self.config, description="Search")
        mcp_payload = mcp.build(self.config, description="MCP")
        fabric_payload = fabric.build(self.config, description="Fabric")

        self.assertEqual(search.api_version(self.config), STABLE_SEARCH_API_VERSION)
        self.assertEqual(mcp.api_version(self.config), PREVIEW_SEARCH_API_VERSION)
        self.assertEqual(fabric.api_version(self.config), PREVIEW_SEARCH_API_VERSION)
        self.assertTrue(search.matches(search_payload, self.config))
        self.assertTrue(mcp.matches(mcp_payload, self.config))
        self.assertTrue(fabric.matches(fabric_payload, self.config))
        self.assertEqual(
            [
                search_payload["kind"],
                mcp_payload["kind"],
                fabric_payload["kind"],
            ],
            ["searchIndex", "mcpServer", "fabricOntology"],
        )

    def test_knowledge_base_contracts_do_not_mix_api_shapes(self):
        knowledge_base = KnowledgeBaseOperations()
        stable = knowledge_base.build_stable(
            self.config,
            ["index-ks"],
            description="Stable",
        )
        preview = knowledge_base.build_preview(
            self.config,
            ["index-ks", "mcp-ks", "fabric-ks"],
            description="Preview",
            retrieval_instructions="Use source evidence.",
        )

        self.assertEqual(
            knowledge_base.api_version(self.config, stable=True),
            STABLE_SEARCH_API_VERSION,
        )
        self.assertEqual(
            knowledge_base.api_version(self.config, stable=False),
            PREVIEW_SEARCH_API_VERSION,
        )
        self.assertTrue(knowledge_base.matches_stable(stable, {"index-ks"}))
        self.assertTrue(
            knowledge_base.matches_preview(
                preview,
                self.config,
                {"index-ks", "mcp-ks", "fabric-ks"},
            )
        )
        self.assertFalse(
            {"models", "outputMode", "retrievalReasoningEffort"}.intersection(
                stable
            )
        )

    def test_evidence_classification_ignores_answer_text(self):
        answer_only = {"response": [{"content": [{"text": "searchIndex"}]}]}
        evidence = {
            "activity": [{"type": "mcpServer"}],
            "references": [{"type": "fabricOntology"}],
        }

        self.assertFalse(response_has_evidence(answer_only, "searchIndex"))
        self.assertTrue(response_has_evidence(evidence, "mcpServer"))
        self.assertEqual(evidence_count(evidence), 2)
        self.assertEqual(evidence_types(evidence), ["fabricOntology", "mcpServer"])


if __name__ == "__main__":
    unittest.main()
