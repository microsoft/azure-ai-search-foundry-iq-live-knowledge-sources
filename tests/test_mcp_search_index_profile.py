import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import cli  # noqa: E402
from liveks.config import ConfigError, resolve_config  # noqa: E402
from liveks.mcp_search_index import build_payloads, redacted_payloads  # noqa: E402
from liveks.runtime import EnvironmentOperationLock  # noqa: E402


def authored_config(root: Path, *, extra_search: str = "", extra_openai: str = ""):
    path = root / "mcp-search-index.yaml"
    path.write_text(
        "\n".join(
            [
                "version: 2",
                "profile: mcp-search-index",
                "environment: unit-combined",
                "search:",
                "  endpoint: https://example.search.windows.net",
                "  index_name: existing-docs",
                "  semantic_configuration_name: default-semantic",
                "  search_fields: [content]",
                "  source_data_fields: [id, title, content]",
                *([extra_search] if extra_search else []),
                "openai:",
                "  endpoint: https://example.openai.azure.com",
                "  deployment_name: existing-gpt",
                "  model_name: gpt-5-mini",
                *([extra_openai] if extra_openai else []),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return resolve_config(profile=None, environment=None, config_path=path)


class McpSearchIndexConfigurationTests(unittest.TestCase):
    def test_profile_resolves_both_pinned_contracts_and_reuse_ownership(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))

        self.assertEqual(config.get("search.index_api_version"), "2026-04-01")
        self.assertEqual(config.get("search.preview_api_version"), "2026-05-01-preview")
        self.assertEqual(config.get("search.index_knowledge_source_name"), "unit-combined-search-index-ks")
        self.assertEqual(config.get("search.mcp_knowledge_source_name"), "unit-combined-mcp-server-ks")
        self.assertEqual(config.get("search.combined_knowledge_base_name"), "unit-combined-combined-kb")
        self.assertEqual(config.ownership()["searchIndex"], "reuse")
        self.assertEqual(config.ownership()["azureOpenAI"], "reuse")
        self.assertEqual(config.ownership()["knowledgeSources"], "create")

    def test_profile_rejects_stable_and_preview_api_swaps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(ConfigError, "search.index_api_version"):
                authored_config(root, extra_search="  index_api_version: 2026-05-01-preview")
            with self.assertRaisesRegex(ConfigError, "search.preview_api_version"):
                authored_config(root, extra_search="  preview_api_version: '2026-04-01'")

    def test_profile_rejects_managed_name_collisions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ConfigError, "must be distinct"):
                authored_config(
                    Path(temp_dir),
                    extra_search=(
                        "  index_knowledge_source_name: duplicate-name\n"
                        "  mcp_knowledge_source_name: duplicate-name"
                    ),
                )

    def test_profile_rejects_untrusted_openai_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ConfigError, "trusted Azure OpenAI"):
                authored_config(
                    Path(temp_dir),
                    extra_openai="  endpoint: https://credential-collector.example",
                )

    def test_payloads_keep_ga_search_source_separate_from_preview_requests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))
        payloads = build_payloads(
            config,
            index_query="private index query",
            mcp_query="private MCP query",
            combined_query="private combined query",
        )

        self.assertEqual(payloads["searchIndexKnowledgeSource"]["kind"], "searchIndex")
        self.assertIn("semanticConfigurationName", payloads["searchIndexKnowledgeSource"]["searchIndexParameters"])
        self.assertEqual(payloads["mcpKnowledgeSource"]["kind"], "mcpServer")
        self.assertEqual(payloads["knowledgeBase"]["retrievalReasoningEffort"], {"kind": "low"})
        self.assertEqual(
            [item["name"] for item in payloads["knowledgeBase"]["knowledgeSources"]],
            ["unit-combined-search-index-ks", "unit-combined-mcp-server-ks"],
        )
        self.assertTrue(all("messages" in request for request in payloads["retrieve"].values()))
        self.assertTrue(all("intents" not in request for request in payloads["retrieve"].values()))
        self.assertEqual(
            [item["kind"] for item in payloads["retrieve"]["combined"]["knowledgeSourceParams"]],
            ["searchIndex", "mcpServer"],
        )

    def test_plan_redaction_removes_model_endpoint_and_runtime_queries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))
        payloads = build_payloads(
            config,
            index_query="private index query",
            mcp_query="private MCP query",
            combined_query="private combined query",
        )
        serialized = json.dumps(redacted_payloads(payloads))

        self.assertNotIn("example.openai.azure.com", serialized)
        self.assertNotIn("private index query", serialized)
        self.assertNotIn("private MCP query", serialized)
        self.assertNotIn("private combined query", serialized)
        self.assertIn("redacted-azure-openai-endpoint", serialized)


class McpSearchIndexLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = authored_config(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plan_is_read_only_and_names_versions_costs_ownership_and_cleanup(self):
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, **kwargs):
            calls.append((method, path, api_version))
            return 404, {}

        doctor = {"status": "pass", "checks": [{"name": "doctor", "status": "pass", "message": "ok"}]}
        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "doctor_report", return_value=doctor),
            mock.patch.object(cli, "_load_lock", return_value=None),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-combined.lock.json"),
        ):
            report = cli.plan_report(self.config)

        self.assertEqual(report["status"], "pass")
        self.assertEqual([method for method, _, _ in calls], ["GET", "GET", "GET"])
        self.assertEqual(
            [api_version for _, _, api_version in calls],
            ["2026-04-01", "2026-05-01-preview", "2026-05-01-preview"],
        )
        self.assertEqual(report["ownership"]["searchService"], "reuse")
        self.assertIn("Azure OpenAI", report["cost"])
        self.assertEqual(report["cleanupOrder"][0]["kind"], "knowledgeBase")
        self.assertEqual(
            [(item["kind"], item["apiVersion"]) for item in report["contracts"][:4]],
            [
                ("searchIndex", "2026-04-01"),
                ("searchIndexKnowledgeSource", "2026-04-01"),
                ("mcpServerKnowledgeSource", "2026-05-01-preview"),
                ("knowledgeBase", "2026-05-01-preview"),
            ],
        )
        artifact = (self.root / ".deployment/unit-combined/mcp-search-index-plan.json").read_text()
        self.assertNotIn("example.search.windows.net", artifact)
        self.assertNotIn("example.openai.azure.com", artifact)

    def test_environment_operation_lock_rejects_concurrent_lifecycle(self):
        lock_path = self.root / ".liveks/unit-combined.operation.lock"
        with EnvironmentOperationLock(lock_path):
            with self.assertRaisesRegex(RuntimeError, "Another lifecycle operation"):
                with EnvironmentOperationLock(lock_path):
                    pass

    def test_plan_rejects_an_unowned_name_collision_without_put_or_delete(self):
        calls = []
        responses = iter([(404, {}), (200, {"name": "occupied"}), (404, {})])

        def fake_request(config, token, *, method, path, api_version=None, **kwargs):
            calls.append(method)
            return next(responses)

        doctor = {"status": "pass", "checks": []}
        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "doctor_report", return_value=doctor),
            mock.patch.object(cli, "_load_lock", return_value=None),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-combined.lock.json"),
        ):
            report = cli.plan_report(self.config)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(calls, ["GET", "GET", "GET"])
        collision = next(check for check in report["checks"] if check["name"] == "mcpKnowledgeSource-name")
        self.assertEqual(collision["status"], "fail")

    def test_combined_profile_detects_stable_profile_owned_objects(self):
        foreign_lock = {
            "profile": "search-index",
            "environment": self.config.environment,
            "configDigest": "different",
            "managedObjects": {
                "knowledgeSource": "foreign-search-ks",
                "knowledgeBase": "foreign-search-kb",
            },
            "managedObjectEtags": {
                "knowledgeSource": "foreign-source-etag",
                "knowledgeBase": "foreign-base-etag",
            },
        }
        with mock.patch.object(cli, "_load_lock", return_value=foreign_lock):
            managed, etags, matches, _ = cli._mcp_search_index_lock_state(self.config)

        self.assertFalse(matches)
        self.assertEqual(managed["knowledgeSource"], "foreign-search-ks")
        self.assertEqual(etags["knowledgeBase"], "foreign-base-etag")

    def test_matching_active_direct_lock_can_reach_etag_reuse_checks(self):
        matching_lock = {
            "profile": self.config.profile,
            "environment": self.config.environment,
            "configDigest": self.config.config_digest,
            "status": "deployed",
            "managedObjects": {
                "searchIndexKnowledgeSource": "unit-combined-search-index-ks",
            },
            "managedObjectEtags": {
                "searchIndexKnowledgeSource": "owned-etag",
            },
        }
        with mock.patch.object(cli, "_load_lock", return_value=matching_lock):
            conflict = cli._environment_lock_conflict(self.config)

        self.assertIsNone(conflict)

    def test_ambiguous_creation_journals_pending_object_for_cleanup(self):
        responses = iter(
            [
                (404, {}),
                (201, {"@odata.etag": "etag-search"}),
                (404, {}),
                (500, {"error": "private detail"}),
                (404, {}),
            ]
        )
        locks = []
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, headers=None, **kwargs):
            calls.append((method, api_version, headers))
            return next(responses)

        def fake_write_lock(config, *, status, extra=None):
            locks.append(
                (
                    status,
                    dict((extra or {}).get("managedObjects", {})),
                    dict((extra or {}).get("managedObjectEtags", {})),
                )
            )
            return self.root / ".liveks/unit-combined.lock.json"

        with (
            mock.patch.object(cli, "plan_report", return_value={"status": "warn", "checks": []}),
            mock.patch.object(
                cli,
                "_mcp_search_index_lock_state",
                return_value=(
                    {"searchIndexKnowledgeSource": "unit-combined-search-index-ks"},
                    {"searchIndexKnowledgeSource": "stale-etag"},
                    True,
                    "matching environment lock",
                ),
            ),
            mock.patch.object(cli, "_confirm_up"),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", side_effect=fake_write_lock),
        ):
            report = cli.up_report(self.config, yes=True, accept_fabric_capacity=False)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(
            locks[-1][1],
            {
                "searchIndexKnowledgeSource": "unit-combined-search-index-ks",
                "mcpKnowledgeSource": "unit-combined-mcp-server-ks",
            },
        )
        self.assertEqual(locks[-1][2], {"searchIndexKnowledgeSource": "etag-search"})
        self.assertEqual(
            calls,
            [
                ("GET", "2026-04-01", None),
                ("PUT", "2026-04-01", {"If-None-Match": "*", "Prefer": "return=representation"}),
                ("GET", "2026-05-01-preview", None),
                ("PUT", "2026-05-01-preview", {"If-None-Match": "*", "Prefer": "return=representation"}),
                ("GET", "2026-05-01-preview", None),
            ],
        )
        self.assertNotIn("private detail", json.dumps(report))

    def test_up_refuses_to_update_an_owned_name_when_etag_changed(self):
        managed = {"searchIndexKnowledgeSource": "unit-combined-search-index-ks"}
        etags = {"searchIndexKnowledgeSource": "etag-recorded"}
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, **kwargs):
            calls.append(method)
            return 200, {"@odata.etag": "etag-recreated"}

        with (
            mock.patch.object(cli, "plan_report", return_value={"status": "warn", "checks": []}),
            mock.patch.object(
                cli,
                "_mcp_search_index_lock_state",
                return_value=(managed, etags, True, "matching environment lock"),
            ),
            mock.patch.object(cli, "_confirm_up"),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-combined.lock.json"),
        ):
            report = cli.up_report(self.config, yes=True, accept_fabric_capacity=False)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(calls, ["GET"])
        self.assertIn("unowned or changed", json.dumps(report))

    def test_verify_proves_each_source_before_combined_and_persists_no_content(self):
        index_definition = {
            "fields": [
                {"name": "id", "retrievable": True},
                {"name": "title", "retrievable": True},
                {"name": "content", "searchable": True, "retrievable": True},
            ],
            "semantic": {"configurations": [{"name": "default-semantic"}]},
        }
        knowledge_base = build_payloads(
            self.config,
            index_query="unused",
            mcp_query="unused",
            combined_query="unused",
        )["knowledgeBase"]
        responses = iter(
            [
                (200, index_definition),
                (
                    200,
                    {
                        "kind": "searchIndex",
                        "searchIndexParameters": {
                            "searchIndexName": "existing-docs",
                            "semanticConfigurationName": "default-semantic",
                        },
                    },
                ),
                (
                    200,
                    {
                        "kind": "mcpServer",
                        "mcpServerParameters": {
                            "serverURL": "https://learn.microsoft.com/api/mcp",
                            "tools": [{"name": "microsoft_docs_search"}],
                        },
                    },
                ),
                (200, knowledge_base),
                (
                    200,
                    {
                        "response": [{"content": [{"type": "text", "text": "private synthesized answer"}]}],
                        "activity": [{"type": "searchIndex"}],
                        "references": [
                            {
                                "type": "searchIndex",
                                "sourceData": {"content": "private-known-term"},
                            }
                        ],
                    },
                ),
                (
                    200,
                    {
                        "activity": [{"type": "mcpServer", "toolName": "microsoft_docs_search"}],
                        "references": [{"type": "mcpServer", "sourceData": {"content": "private MCP output"}}],
                    },
                ),
                (
                    200,
                    {
                        "activity": [{"type": "searchIndex"}],
                        "references": [{"type": "mcpServer", "sourceData": {"content": "combined private output"}}],
                    },
                ),
            ]
        )
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, body=None, **kwargs):
            calls.append((method, api_version, body))
            return next(responses)

        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
        ):
            report = cli.verify_report(
                self.config,
                query="private index question",
                expected_terms=["private-known-term"],
                mcp_query="private MCP question",
                combined_query="private combined question",
            )

        self.assertEqual(report["status"], "pass")
        retrieve_calls = [call for call in calls if call[0] == "POST"]
        self.assertEqual([call[1] for call in retrieve_calls], ["2026-05-01-preview"] * 3)
        self.assertEqual(
            [[item["kind"] for item in call[2]["knowledgeSourceParams"]] for call in retrieve_calls],
            [["searchIndex"], ["mcpServer"], ["searchIndex", "mcpServer"]],
        )
        check_names = [check["name"] for check in report["checks"]]
        self.assertLess(check_names.index("search-index-retrieve"), check_names.index("mcp-retrieve"))
        self.assertLess(check_names.index("mcp-retrieve"), check_names.index("combined-retrieve"))
        combined = next(check for check in report["checks"] if check["name"] == "combined-retrieve")
        self.assertEqual(combined["sourceTypes"], ["mcpServer", "searchIndex"])
        persisted = (self.root / "deployments/unit-combined/verify-report.json").read_text()
        for forbidden in (
            "private index question",
            "private MCP question",
            "private combined question",
            "private-known-term",
            "private synthesized answer",
            "example.search.windows.net",
            "example.openai.azure.com",
        ):
            self.assertNotIn(forbidden, persisted)

    def test_verify_normalizes_authorization_failure_without_raw_payload(self):
        payloads = build_payloads(
            self.config,
            index_query="unused",
            mcp_query="unused",
            combined_query="unused",
        )
        responses = iter(
            [
                (200, {"name": "existing-docs"}),
                (200, payloads["searchIndexKnowledgeSource"]),
                (200, payloads["mcpKnowledgeSource"]),
                (200, payloads["knowledgeBase"]),
                (403, {"error": "private tenant and token detail"}),
                (200, {"activity": [{"type": "mcpServer"}], "references": []}),
                (200, {"activity": [{"type": "mcpServer"}], "references": []}),
            ]
        )
        request_mock = mock.Mock(side_effect=lambda *args, **kwargs: next(responses))
        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", request_mock),
        ):
            report = cli.verify_report(self.config)

        self.assertEqual(report["status"], "fail")
        serialized = json.dumps(report)
        self.assertIn("Search managed identity", serialized)
        self.assertNotIn("private tenant", serialized)
        self.assertEqual(request_mock.call_count, 6)
        combined = next(check for check in report["checks"] if check["name"] == "combined-retrieve")
        self.assertIn("not attempted", combined["message"])

    def test_empty_expected_term_fails_before_any_live_request(self):
        with (
            mock.patch.object(cli, "acquire_search_bearer_token") as token_mock,
            mock.patch.object(cli, "search_index_request") as request_mock,
        ):
            report = cli.verify_report(self.config, expected_terms=["   "])

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["checks"][0]["name"], "runtime-input")
        token_mock.assert_not_called()
        request_mock.assert_not_called()

    def test_cleanup_uses_dependency_order_and_preserves_reused_assets(self):
        managed = {
            "searchIndexKnowledgeSource": "unit-combined-search-index-ks",
            "mcpKnowledgeSource": "unit-combined-mcp-server-ks",
            "combinedKnowledgeBase": "unit-combined-combined-kb",
        }
        managed_etags = {
            "searchIndexKnowledgeSource": "etag-search",
            "mcpKnowledgeSource": "etag-mcp",
            "combinedKnowledgeBase": "etag-kb",
        }
        responses = iter([(204, {}), (204, {}), (204, {}), (200, {"name": "existing-docs"})])
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, headers=None, **kwargs):
            calls.append((method, path, api_version, headers))
            return next(responses)

        with (
            mock.patch.object(
                cli,
                "_mcp_search_index_lock_state",
                return_value=(managed, managed_etags, True, "matching environment lock"),
            ),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-combined.lock.json"),
        ):
            report = cli.down_report(self.config, yes=True)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            [(method, api_version) for method, _, api_version, _ in calls],
            [
                ("DELETE", "2026-05-01-preview"),
                ("DELETE", "2026-05-01-preview"),
                ("DELETE", "2026-04-01"),
                ("GET", "2026-04-01"),
            ],
        )
        self.assertIn("/knowledgebases/", calls[0][1])
        self.assertIn("mcp-server-ks", calls[1][1])
        self.assertIn("search-index-ks", calls[2][1])
        self.assertEqual([call[3] for call in calls[:3]], [
            {"If-Match": "etag-kb"},
            {"If-Match": "etag-mcp"},
            {"If-Match": "etag-search"},
        ])
        self.assertEqual(next(check for check in report["checks"] if check["name"] == "search-index-preserved")["status"], "pass")
        self.assertEqual(next(check for check in report["checks"] if check["name"] == "azure-openai-preserved")["status"], "pass")

    def test_cleanup_preserves_everything_without_matching_lock(self):
        with (
            mock.patch.object(cli, "_mcp_search_index_lock_state", return_value=({}, {}, False, "mismatch")),
            mock.patch.object(cli, "search_index_request") as request_mock,
        ):
            report = cli.down_report(self.config, yes=True)

        self.assertEqual(report["status"], "cleanup-incomplete")
        request_mock.assert_not_called()

    def test_native_mcp_uses_direct_preview_endpoint_with_bearer_only(self):
        class DirectRunner:
            instances = []

            def __init__(self, *, root, env, quiet=False):
                self.history = []
                self.__class__.instances.append(self)

            def run(self, command, **kwargs):
                args = [str(item) for item in command]
                self.history.append(args)
                return mock.Mock(returncode=0, stdout="transient-token\n")

        responses = [
            (200, {"result": {"tools": [{"name": "knowledge_base_retrieve"}]}}),
            (200, {"result": {"content": [{"type": "text", "text": "Azure AI Search guidance"}]}}),
        ]
        DirectRunner.instances = []
        with (
            mock.patch.object(cli, "CommandRunner", DirectRunner),
            mock.patch.object(cli, "http_mcp_json", side_effect=responses) as mcp_request,
        ):
            report = cli.mcp_report(
                self.config,
                auth="bearer",
                expected_terms=["Azure AI Search"],
                persist=False,
            )

        self.assertEqual(report["status"], "pass")
        commands = [command for runner in DirectRunner.instances for command in runner.history]
        self.assertFalse(any(command[:2] == ["azd", "env"] for command in commands))
        self.assertIn("api-version=2026-05-01-preview", mcp_request.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()
