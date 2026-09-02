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


WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
ONTOLOGY_ID = "22222222-2222-2222-2222-222222222222"


def authored_config(
    root: Path,
    *,
    include_fabric: bool = True,
    extra_search: str = "",
):
    path = root / "three-source.yaml"
    lines = [
        "version: 2",
        "profile: three-source",
        "environment: unit-three",
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
    ]
    if include_fabric:
        lines.extend(
            [
                "fabric:",
                f"  workspace_id: {WORKSPACE_ID}",
                f"  ontology_id: {ONTOLOGY_ID}",
                "  user_search_token:",
                "    env: FABRIC_USER_SEARCH_TOKEN",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolve_config(profile=None, environment=None, config_path=path)


class ThreeSourceConfigurationTests(unittest.TestCase):
    def test_profile_resolves_pins_names_and_byo_ownership(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))

        self.assertEqual(config.get("search.index_api_version"), "2026-04-01")
        self.assertEqual(config.get("search.preview_api_version"), "2026-05-01-preview")
        self.assertEqual(config.get("search.index_knowledge_source_name"), "unit-three-search-index-ks")
        self.assertEqual(config.get("search.mcp_knowledge_source_name"), "unit-three-mcp-server-ks")
        self.assertEqual(config.get("search.fabric_knowledge_source_name"), "unit-three-fabric-ontology-ks")
        self.assertEqual(config.get("search.combined_knowledge_base_name"), "unit-three-combined-kb")
        self.assertEqual(config.ownership()["searchIndex"], "reuse")
        self.assertEqual(config.ownership()["azureOpenAI"], "reuse")
        self.assertEqual(config.ownership()["fabricWorkspace"], "reuse")
        self.assertEqual(config.ownership()["fabricOntology"], "reuse")
        self.assertEqual(config.ownership()["knowledgeSources"], "create")

    def test_missing_fabric_inputs_fail_before_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ConfigError,
                "fabric.workspace_id, fabric.ontology_id",
            ):
                authored_config(Path(temp_dir), include_fabric=False)

    def test_stable_preview_swap_fails_with_actionable_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ConfigError,
                "search.index_api_version.*2026-04-01",
            ):
                authored_config(
                    Path(temp_dir),
                    extra_search="  index_api_version: 2026-05-01-preview",
                )
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ConfigError,
                "search.preview_api_version.*2026-05-01-preview",
            ):
                authored_config(
                    Path(temp_dir),
                    extra_search="  preview_api_version: '2026-04-01'",
                )

    def test_four_generated_names_must_be_distinct(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ConfigError, "must be distinct"):
                authored_config(
                    Path(temp_dir),
                    extra_search=(
                        "  mcp_knowledge_source_name: duplicate\n"
                        "  fabric_knowledge_source_name: duplicate"
                    ),
                )

    def test_payloads_serialize_three_sources_without_cross_lane_substitution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))
        payloads = build_payloads(
            config,
            index_query="private index query",
            mcp_query="private MCP query",
            fabric_query="private Fabric query",
            combined_query="private combined query",
        )

        self.assertEqual(payloads["searchIndexKnowledgeSource"]["kind"], "searchIndex")
        self.assertEqual(payloads["mcpKnowledgeSource"]["kind"], "mcpServer")
        self.assertEqual(payloads["fabricKnowledgeSource"]["kind"], "fabricOntology")
        self.assertEqual(
            [item["name"] for item in payloads["knowledgeBase"]["knowledgeSources"]],
            [
                "unit-three-search-index-ks",
                "unit-three-mcp-server-ks",
                "unit-three-fabric-ontology-ks",
            ],
        )
        self.assertEqual(
            [item["kind"] for item in payloads["retrieve"]["combined"]["knowledgeSourceParams"]],
            ["searchIndex", "mcpServer", "fabricOntology"],
        )
        self.assertEqual(
            [item["kind"] for item in payloads["retrieve"]["fabric"]["knowledgeSourceParams"]],
            ["fabricOntology"],
        )
        self.assertTrue(all("messages" in request for request in payloads["retrieve"].values()))
        self.assertTrue(all("intents" not in request for request in payloads["retrieve"].values()))

        redacted = json.dumps(redacted_payloads(payloads))
        for private in (
            WORKSPACE_ID,
            ONTOLOGY_ID,
            "example.openai.azure.com",
            "private index query",
            "private MCP query",
            "private Fabric query",
            "private combined query",
        ):
            self.assertNotIn(private, redacted)


class ThreeSourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = authored_config(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plan_is_read_only_and_names_all_contracts_costs_and_cleanup(self):
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
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-three.lock.json"),
        ):
            report = cli.plan_report(self.config)

        self.assertEqual(report["status"], "pass")
        self.assertEqual([method for method, _, _ in calls], ["GET"] * 4)
        self.assertEqual(
            [version for _, _, version in calls],
            ["2026-04-01", "2026-05-01-preview", "2026-05-01-preview", "2026-05-01-preview"],
        )
        self.assertEqual(
            [(item["kind"], item["apiVersion"], item["ownership"]) for item in report["contracts"]],
            [
                ("searchIndex", "2026-04-01", "reuse"),
                ("searchIndexKnowledgeSource", "2026-04-01", "create"),
                ("mcpServerKnowledgeSource", "2026-05-01-preview", "create"),
                ("fabricOntologyKnowledgeSource", "2026-05-01-preview", "create"),
                ("knowledgeBase", "2026-05-01-preview", "create"),
                ("azureOpenAI", "external-existing-deployment", "reuse"),
                ("fabricWorkspace", "fabric-v1", "reuse"),
                ("fabricOntology", "fabric-v1", "reuse"),
            ],
        )
        self.assertEqual(
            [item["kind"] for item in report["cleanupOrder"][:4]],
            [
                "knowledgeBase",
                "fabricOntologyKnowledgeSource",
                "mcpServerKnowledgeSource",
                "searchIndexKnowledgeSource",
            ],
        )
        self.assertIn("existing Fabric capacity", report["cost"])
        artifact = (self.root / ".deployment/unit-three/three-source-plan.json").read_text()
        self.assertNotIn(WORKSPACE_ID, artifact)
        self.assertNotIn(ONTOLOGY_ID, artifact)
        self.assertNotIn("example.openai.azure.com", artifact)

    def test_doctor_reads_existing_fabric_assets_with_transient_bearer(self):
        class FabricRunner:
            def __init__(self, **kwargs):
                pass

            def run(self, command, **kwargs):
                self.sensitive_output = kwargs.get("sensitive_output")
                return mock.Mock(returncode=0, stdout="fabric-api-token\n")

        calls = []

        def fake_http(url, *, headers=None, **kwargs):
            calls.append((url, headers))
            return 200, {"type": "Ontology"} if "/items/" in url else {}

        with (
            mock.patch.object(cli.shutil, "which", return_value="/usr/bin/az"),
            mock.patch.object(cli, "CommandRunner", FabricRunner),
            mock.patch.object(cli, "http_json", side_effect=fake_http),
        ):
            checks = cli._fabric_byo_doctor_checks(self.config)

        self.assertEqual([check["status"] for check in checks], ["pass", "pass", "pass"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(headers == {"Authorization": "Bearer fabric-api-token"} for _, headers in calls))
        self.assertNotIn(WORKSPACE_ID, json.dumps(checks))
        self.assertNotIn(ONTOLOGY_ID, json.dumps(checks))

    def test_doctor_rejects_a_readable_non_ontology_fabric_item(self):
        class FabricRunner:
            def __init__(self, **kwargs):
                pass

            def run(self, command, **kwargs):
                return mock.Mock(returncode=0, stdout="fabric-api-token\n")

        responses = iter([(200, {}), (200, {"type": "Lakehouse"})])
        with (
            mock.patch.object(cli.shutil, "which", return_value="/usr/bin/az"),
            mock.patch.object(cli, "CommandRunner", FabricRunner),
            mock.patch.object(cli, "http_json", side_effect=lambda *args, **kwargs: next(responses)),
        ):
            checks = cli._fabric_byo_doctor_checks(self.config)

        ontology = next(check for check in checks if check["name"] == "fabric-ontology")
        self.assertEqual(ontology["status"], "fail")
        self.assertIn("not an Ontology", ontology["message"])

    def test_up_creates_three_sources_then_knowledge_base_with_pinned_versions(self):
        calls = []
        responses = iter(
            [
                (404, {}),
                (201, {"@odata.etag": "etag-search"}),
                (404, {}),
                (201, {"@odata.etag": "etag-mcp"}),
                (404, {}),
                (201, {"@odata.etag": "etag-fabric"}),
                (404, {}),
                (201, {"@odata.etag": "etag-kb"}),
            ]
        )

        def fake_request(config, token, *, method, path, api_version=None, body=None, **kwargs):
            calls.append((method, path, api_version, body))
            return next(responses)

        with (
            mock.patch.object(cli, "plan_report", return_value={"status": "pass", "checks": []}),
            mock.patch.object(
                cli,
                "_mcp_search_index_lock_state",
                return_value=({}, {}, True, "environment lock is not present"),
            ),
            mock.patch.object(cli, "_confirm_up"),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "verify_report", return_value={"status": "pass", "checks": []}),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-three.lock.json"),
        ):
            report = cli.up_report(
                self.config,
                yes=True,
                accept_fabric_capacity=False,
            )

        self.assertEqual(report["status"], "pass")
        puts = [call for call in calls if call[0] == "PUT"]
        self.assertEqual(
            [(version, body["kind"] if "kind" in body else "knowledgeBase") for _, _, version, body in puts],
            [
                ("2026-04-01", "searchIndex"),
                ("2026-05-01-preview", "mcpServer"),
                ("2026-05-01-preview", "fabricOntology"),
                ("2026-05-01-preview", "knowledgeBase"),
            ],
        )

    def test_verify_proves_three_sources_before_combined_with_delegated_header(self):
        payloads = build_payloads(
            self.config,
            index_query="unused",
            mcp_query="unused",
            fabric_query="unused",
            combined_query="unused",
        )
        index_definition = {
            "fields": [
                {"name": "id", "retrievable": True},
                {"name": "title", "retrievable": True},
                {"name": "content", "searchable": True, "retrievable": True},
            ],
            "semantic": {"configurations": [{"name": "default-semantic"}]},
        }
        responses = iter(
            [
                (200, index_definition),
                (200, payloads["searchIndexKnowledgeSource"]),
                (200, payloads["mcpKnowledgeSource"]),
                (200, payloads["fabricKnowledgeSource"]),
                (200, payloads["knowledgeBase"]),
                (
                    200,
                    {
                        "activity": [{"type": "searchIndex"}],
                        "references": [{"type": "searchIndex", "sourceData": {"content": "known-index-term"}}],
                    },
                ),
                (
                    200,
                    {
                        "activity": [{"type": "mcpServer"}],
                        "references": [{"type": "mcpServer", "sourceData": {"content": "private MCP output"}}],
                    },
                ),
                (
                    200,
                    {
                        "activity": [{"type": "fabricOntology"}],
                        "references": [{"type": "fabricOntology", "sourceData": {"fabricAnswer": "private Fabric output"}}],
                    },
                ),
                (
                    200,
                    {
                        "response": [{"content": [{"type": "text", "text": "private answer"}]}],
                        "activity": [{"type": "fabricOntology"}],
                        "references": [
                            {"type": "searchIndex", "sourceData": {}},
                            {"type": "mcpServer", "sourceData": {}},
                        ],
                    },
                ),
            ]
        )
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, body=None, headers=None, **kwargs):
            calls.append((method, api_version, body, headers))
            return next(responses)

        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="search-token"),
            mock.patch.object(cli, "_fabric_source_authorization", return_value="fabric-token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
        ):
            report = cli.verify_report(
                self.config,
                query="private index question",
                expected_terms=["known-index-term"],
                mcp_query="private MCP question",
                fabric_query="private Fabric question",
                combined_query="private combined question",
            )

        self.assertEqual(report["status"], "pass")
        retrieve_calls = [call for call in calls if call[0] == "POST"]
        self.assertEqual(
            [[item["kind"] for item in call[2]["knowledgeSourceParams"]] for call in retrieve_calls],
            [
                ["searchIndex"],
                ["mcpServer"],
                ["fabricOntology"],
                ["searchIndex", "mcpServer", "fabricOntology"],
            ],
        )
        self.assertIsNone(retrieve_calls[0][3])
        self.assertIsNone(retrieve_calls[1][3])
        self.assertEqual(
            retrieve_calls[2][3],
            {"x-ms-query-source-authorization": "fabric-token"},
        )
        self.assertEqual(
            retrieve_calls[3][3],
            {"x-ms-query-source-authorization": "fabric-token"},
        )
        names = [check["name"] for check in report["checks"]]
        self.assertLess(names.index("search-index-retrieve"), names.index("mcp-retrieve"))
        self.assertLess(names.index("mcp-retrieve"), names.index("fabric-retrieve"))
        self.assertLess(names.index("fabric-retrieve"), names.index("combined-retrieve"))
        combined = next(check for check in report["checks"] if check["name"] == "combined-retrieve")
        self.assertEqual(
            combined["sourceTypes"],
            ["fabricOntology", "mcpServer", "searchIndex"],
        )
        persisted = (self.root / "deployments/unit-three/verify-report.json").read_text()
        for private in (
            WORKSPACE_ID,
            ONTOLOGY_ID,
            "fabric-token",
            "private index question",
            "private MCP question",
            "private Fabric question",
            "private combined question",
            "private answer",
        ):
            self.assertNotIn(private, persisted)

    def test_combined_is_not_attempted_when_fabric_authorization_fails(self):
        payloads = build_payloads(
            self.config,
            index_query="unused",
            mcp_query="unused",
            fabric_query="unused",
            combined_query="unused",
        )
        responses = iter(
            [
                (200, {"name": "existing-docs"}),
                (200, payloads["searchIndexKnowledgeSource"]),
                (200, payloads["mcpKnowledgeSource"]),
                (200, payloads["fabricKnowledgeSource"]),
                (200, payloads["knowledgeBase"]),
                (200, {"activity": [{"type": "searchIndex"}]}),
                (200, {"activity": [{"type": "mcpServer"}]}),
            ]
        )
        request_mock = mock.Mock(side_effect=lambda *args, **kwargs: next(responses))
        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="search-token"),
            mock.patch.object(cli, "_fabric_source_authorization", side_effect=RuntimeError("private token detail")),
            mock.patch.object(cli, "search_index_request", request_mock),
        ):
            report = cli.verify_report(self.config)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(request_mock.call_count, 7)
        combined = next(check for check in report["checks"] if check["name"] == "combined-retrieve")
        self.assertIn("not attempted", combined["message"])
        self.assertNotIn("private token detail", json.dumps(report))

    def test_native_mcp_attaches_delegated_fabric_authorization_without_persisting_it(self):
        class DirectRunner:
            def __init__(self, **kwargs):
                self.history = []

            def run(self, command, **kwargs):
                self.history.append([str(item) for item in command])
                return mock.Mock(returncode=0, stdout="search-token\n")

        responses = [
            (200, {"result": {"tools": [{"name": "knowledge_base_retrieve"}]}}),
            (
                200,
                {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "known public fact",
                            }
                        ]
                    }
                },
            ),
        ]
        with (
            mock.patch.object(cli, "CommandRunner", DirectRunner),
            mock.patch.object(cli, "_fabric_source_authorization", return_value="fabric-token"),
            mock.patch.object(cli, "http_mcp_json", side_effect=responses) as request_mock,
        ):
            report = cli.mcp_report(
                self.config,
                auth="bearer",
                expected_terms=["known public fact"],
                persist=False,
            )

        self.assertEqual(report["status"], "pass")
        for request in request_mock.call_args_list:
            self.assertEqual(
                request.kwargs["headers"]["x-ms-query-source-authorization"],
                "fabric-token",
            )
        self.assertNotIn("fabric-token", json.dumps(report))
        self.assertNotIn(WORKSPACE_ID, json.dumps(report))
        self.assertNotIn(ONTOLOGY_ID, json.dumps(report))

    def test_cleanup_orders_four_deletes_and_preserves_all_byo_assets(self):
        managed = {
            "searchIndexKnowledgeSource": "unit-three-search-index-ks",
            "mcpKnowledgeSource": "unit-three-mcp-server-ks",
            "fabricKnowledgeSource": "unit-three-fabric-ontology-ks",
            "combinedKnowledgeBase": "unit-three-combined-kb",
        }
        etags = {key: f"etag-{key}" for key in managed}
        responses = iter([(204, {})] * 4 + [(200, {"name": "existing-docs"})])
        calls = []

        def fake_request(config, token, *, method, path, api_version=None, headers=None, **kwargs):
            calls.append((method, path, api_version, headers))
            return next(responses)

        with (
            mock.patch.object(
                cli,
                "_mcp_search_index_lock_state",
                return_value=(managed, etags, True, "matching environment lock"),
            ),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-three.lock.json"),
        ):
            report = cli.down_report(self.config, yes=True)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            [(method, version) for method, _, version, _ in calls],
            [
                ("DELETE", "2026-05-01-preview"),
                ("DELETE", "2026-05-01-preview"),
                ("DELETE", "2026-05-01-preview"),
                ("DELETE", "2026-04-01"),
                ("GET", "2026-04-01"),
            ],
        )
        self.assertIn("combined-kb", calls[0][1])
        self.assertIn("fabric-ontology-ks", calls[1][1])
        self.assertIn("mcp-server-ks", calls[2][1])
        self.assertIn("search-index-ks", calls[3][1])
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["search-index-preserved"], "pass")
        self.assertEqual(checks["azure-openai-preserved"], "pass")
        self.assertEqual(checks["fabric-assets-preserved"], "pass")

    def test_cleanup_preserves_everything_when_lock_is_ambiguous(self):
        with (
            mock.patch.object(
                cli,
                "_mcp_search_index_lock_state",
                return_value=({}, {}, False, "mismatch"),
            ),
            mock.patch.object(cli, "search_index_request") as request_mock,
        ):
            report = cli.down_report(self.config, yes=True)

        self.assertEqual(report["status"], "cleanup-incomplete")
        request_mock.assert_not_called()
        self.assertIn("preserved", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
