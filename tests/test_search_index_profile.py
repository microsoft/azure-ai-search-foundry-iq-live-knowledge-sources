import io
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
from liveks.runtime import CommandRunner  # noqa: E402
from liveks.search_index import acquire_bearer_token, build_payloads, inspect_index  # noqa: E402


def authored_config(root: Path, *, api_version: str = "2026-04-01"):
    path = root / "search-index.yaml"
    path.write_text(
        "\n".join(
            [
                "version: 2",
                "profile: search-index",
                "environment: unit-search",
                "search:",
                f"  api_version: '{api_version}'",
                "  endpoint: https://example.search.windows.net",
                "  index_name: existing-docs",
                "  semantic_configuration_name: default-semantic",
                "  search_fields: [content]",
                "  source_data_fields: [id, title]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return resolve_config(profile=None, environment=None, config_path=path)


class SearchIndexConfigurationTests(unittest.TestCase):
    def test_profile_requires_existing_index_inputs(self):
        with self.assertRaisesRegex(ConfigError, "search.endpoint, search.index_name, search.semantic_configuration_name"):
            resolve_config(profile="search-index", environment="unit-search")

    def test_profile_resolves_stable_contract_and_reuse_ownership(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))

        self.assertEqual(config.get("search.api_version"), "2026-04-01")
        self.assertEqual(config.get("search.index_knowledge_source_name"), "unit-search-search-index-ks")
        self.assertEqual(config.get("search.index_knowledge_base_name"), "unit-search-search-index-kb")
        self.assertEqual(config.ownership()["searchIndex"], "reuse")
        self.assertEqual(config.ownership()["knowledgeSources"], "create")

    def test_profile_rejects_preview_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ConfigError, "generally available 2026-04-01"):
                authored_config(Path(temp_dir), api_version="2026-05-01-preview")

    def test_profile_rejects_untrusted_https_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "search-index.yaml"
            path.write_text(
                "version: 2\n"
                "profile: search-index\n"
                "environment: unit-search\n"
                "search:\n"
                "  endpoint: https://token-collector.example\n"
                "  index_name: existing-docs\n"
                "  semantic_configuration_name: default-semantic\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "trusted Azure AI Search"):
                resolve_config(profile=None, environment=None, config_path=path)

    def test_init_accepts_explicit_config_path_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "external-search-index.yaml"
            with mock.patch("sys.stdout"):
                result = cli.main(
                    [
                        "init",
                        "--profile",
                        "search-index",
                        "--env",
                        "external-index",
                        "--config",
                        str(destination),
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertTrue(destination.exists())

    def test_payloads_use_intents_and_no_preview_kb_properties(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))
        payloads = build_payloads(config, query="What is indexed?")

        self.assertEqual(payloads["knowledgeSource"]["kind"], "searchIndex")
        self.assertEqual(payloads["retrieve"]["intents"][0]["search"], "What is indexed?")
        self.assertNotIn("messages", payloads["retrieve"])
        self.assertFalse(
            {"models", "outputMode", "retrievalReasoningEffort"}.intersection(payloads["knowledgeBase"])
        )

    def test_bearer_token_command_marks_stdout_as_sensitive(self):
        runner = mock.Mock()
        runner.run.return_value = mock.Mock(returncode=0, stdout="sensitive-token\n")

        self.assertEqual(acquire_bearer_token(runner), "sensitive-token")
        self.assertTrue(runner.run.call_args.kwargs["sensitive_output"])

    def test_sensitive_command_output_is_not_printed(self):
        completed = mock.Mock(returncode=0, stdout="sensitive-token\n")
        with (
            mock.patch("liveks.runtime.subprocess.run", return_value=completed),
            mock.patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            runner = CommandRunner(root=ROOT, env={}, quiet=False)
            runner.run(["az", "account", "get-access-token"], sensitive_output=True)

        self.assertEqual(output.getvalue(), "")

    def test_index_contract_checks_semantic_and_field_capabilities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = authored_config(Path(temp_dir))
        index = {
            "fields": [
                {"name": "id", "retrievable": True},
                {"name": "title", "retrievable": True},
                {"name": "content", "searchable": True, "retrievable": True},
            ],
            "semantic": {"configurations": [{"name": "default-semantic"}]},
        }

        self.assertTrue(all(status == "pass" for _, status, _ in inspect_index(index, config)))


class SearchIndexLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = authored_config(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plan_checks_names_without_mutation(self):
        passing_doctor = {"status": "pass", "checks": [{"name": "doctor", "status": "pass", "message": "ok"}]}
        request_calls = []

        def fake_request(config, token, *, method, path, **kwargs):
            request_calls.append((method, path))
            return 404, {}

        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "doctor_report", return_value=passing_doctor),
            mock.patch.object(cli, "_load_lock", return_value=None),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-search.lock.json"),
        ):
            report = cli.plan_report(self.config)

        self.assertEqual(report["status"], "pass")
        self.assertEqual([method for method, _ in request_calls], ["GET", "GET"])
        plan = json.loads((self.root / ".deployment/unit-search/search-index-plan.json").read_text())
        self.assertEqual(plan["apiVersion"], "2026-04-01")

    def test_up_records_only_created_knowledge_objects(self):
        responses = iter([(404, {}), (201, {}), (404, {}), (201, {})])
        locks = []

        def fake_write_lock(config, *, status, extra=None):
            locks.append((status, dict((extra or {}).get("managedObjects", {}))))
            return self.root / ".liveks/unit-search.lock.json"

        with (
            mock.patch.object(cli, "plan_report", return_value={"status": "pass", "checks": []}),
            mock.patch.object(cli, "_search_index_lock_state", return_value=({}, True, "matching environment lock")),
            mock.patch.object(cli, "_confirm_up"),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=lambda *args, **kwargs: next(responses)),
            mock.patch.object(cli, "verify_report", return_value={"status": "pass", "checks": []}) as verify_mock,
            mock.patch.object(cli, "write_lock", side_effect=fake_write_lock),
        ):
            report = cli.up_report(
                self.config,
                yes=True,
                accept_fabric_capacity=False,
                query="What is the policy?",
                expected_terms=["retention"],
            )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            locks[-1][1],
            {
                "knowledgeSource": "unit-search-search-index-ks",
                "knowledgeBase": "unit-search-search-index-kb",
            },
        )
        verify_mock.assert_called_once_with(
            self.config,
            quiet=True,
            query="What is the policy?",
            expected_terms=["retention"],
        )

    def test_down_deletes_recorded_objects_and_preserves_index(self):
        managed = {
            "knowledgeSource": "unit-search-search-index-ks",
            "knowledgeBase": "unit-search-search-index-kb",
        }
        request_calls = []
        responses = iter([(204, {}), (204, {}), (200, {"name": "existing-docs"})])

        def fake_request(config, token, *, method, path, **kwargs):
            request_calls.append((method, path))
            return next(responses)

        with (
            mock.patch.object(cli, "_search_index_lock_state", return_value=(managed, True, "matching environment lock")),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=fake_request),
            mock.patch.object(cli, "write_lock", return_value=self.root / ".liveks/unit-search.lock.json"),
        ):
            report = cli.down_report(self.config, yes=True)

        self.assertEqual(report["status"], "pass")
        self.assertEqual([method for method, _ in request_calls], ["DELETE", "DELETE", "GET"])
        self.assertTrue(request_calls[-1][1].endswith("/indexes/existing-docs"))
        self.assertEqual(next(check for check in report["checks"] if check["name"] == "search-index-preserved")["status"], "pass")

    def test_down_preserves_everything_without_matching_lock(self):
        with (
            mock.patch.object(cli, "_search_index_lock_state", return_value=({}, False, "mismatch")),
            mock.patch.object(cli, "search_index_request") as request_mock,
        ):
            report = cli.down_report(self.config, yes=True)

        self.assertEqual(report["status"], "cleanup-incomplete")
        request_mock.assert_not_called()

    def test_verify_calls_search_index_and_persists_only_sanitized_counts(self):
        responses = iter(
            [
                (200, {"name": "existing-docs"}),
                (
                    200,
                    {
                        "name": "unit-search-search-index-ks",
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
                        "name": "unit-search-search-index-kb",
                        "knowledgeSources": [{"name": "unit-search-search-index-ks"}],
                    },
                ),
                (
                    200,
                    {
                        "response": [
                            {
                                "role": "assistant",
                                "content": [{"type": "text", "text": "The private-known-term is grounded."}],
                            }
                        ],
                        "activity": [{"type": "searchIndex", "knowledgeSourceName": "unit-search-search-index-ks"}],
                        "references": [],
                    },
                ),
            ]
        )
        with (
            mock.patch.object(cli, "ROOT", self.root),
            mock.patch.object(cli, "acquire_search_bearer_token", return_value="token"),
            mock.patch.object(cli, "search_index_request", side_effect=lambda *args, **kwargs: next(responses)),
        ):
            report = cli.verify_report(
                self.config,
                query="private validation question",
                expected_terms=["private-known-term"],
            )

        self.assertEqual(report["status"], "pass")
        persisted = (self.root / "deployments/unit-search/verify-report.json").read_text(encoding="utf-8")
        self.assertNotIn("private validation question", persisted)
        self.assertNotIn("private-known-term", persisted)
        self.assertNotIn("example.search.windows.net", persisted)
        grounding = next(check for check in report["checks"] if check["name"] == "grounding-content")
        self.assertEqual(grounding["matchedExpectedTermCount"], 1)

    def test_mcp_command_explains_stable_profile_boundary_without_azd(self):
        with mock.patch.object(cli, "CommandRunner") as runner:
            report = cli.mcp_report(self.config, persist=False)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["checks"][0]["name"], "profile-contract")
        self.assertIn("use liveks verify", report["checks"][0]["message"])
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
