import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.canary import (  # noqa: E402
    CAPSULE_KEYS,
    CanaryConfigurationError,
    assert_canary_evidence_safe,
    build_canary_evidence,
    generated_canary_environment,
    missing_canary_configuration,
    protected_lifecycle_arguments,
    write_canary_config,
)


def complete_environment():
    return {
        "AZURE_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
        "AZURE_TENANT_ID": "22222222-2222-2222-2222-222222222222",
        "AZURE_SUBSCRIPTION_ID": "33333333-3333-3333-3333-333333333333",
        "SEARCH_ENDPOINT": "https://example.search.windows.net",
        "SEARCH_INDEX_NAME": "existing-index",
        "SEARCH_SEMANTIC_CONFIGURATION_NAME": "semantic-default",
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENT_ID": "existing-model",
        "AZURE_OPENAI_MODEL_NAME": "gpt-5-mini",
        "LIVEKS_INDEX_QUERY": "private index question",
        "LIVEKS_INDEX_EXPECT_TERM": "private known term",
        "LIVEKS_MCP_QUERY": "private MCP question",
        "LIVEKS_COMBINED_QUERY": "private combined question",
    }


class ProtectedCanaryPreflightTests(unittest.TestCase):
    def test_missing_configuration_names_are_reported_without_values(self):
        environ = complete_environment()
        environ["SEARCH_ENDPOINT"] = ""
        environ["LIVEKS_INDEX_QUERY"] = ""
        missing = missing_canary_configuration(environ)

        self.assertEqual(missing, ["LIVEKS_INDEX_QUERY", "SEARCH_ENDPOINT"])
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                CanaryConfigurationError,
                "LIVEKS_INDEX_QUERY, SEARCH_ENDPOINT",
            ) as error:
                write_canary_config(
                    Path(temp_dir),
                    environment="canary-123-1",
                    environ=environ,
                )
        self.assertNotIn("private known term", str(error.exception))

    def test_preflight_writes_valid_ignored_profile_with_run_unique_names(self):
        environ = complete_environment()
        with tempfile.TemporaryDirectory() as temp_dir:
            path, config = write_canary_config(
                Path(temp_dir),
                environment="canary-12345-2",
                environ=environ,
            )

            text = path.read_text(encoding="utf-8")

        self.assertEqual(config.profile, "mcp-search-index")
        self.assertEqual(config.environment, "canary-12345-2")
        self.assertEqual(
            config.get("search.index_knowledge_source_name"),
            "canary-12345-2-search-index-ks",
        )
        self.assertNotIn("AZURE_CLIENT_ID", text)
        self.assertNotIn(environ["LIVEKS_INDEX_QUERY"], text)
        self.assertNotIn(environ["LIVEKS_INDEX_EXPECT_TERM"], text)

    def test_generated_environment_is_bounded_and_valid(self):
        value = generated_canary_environment("1234567890" * 10, "4")
        self.assertLessEqual(len(value), 63)
        self.assertRegex(value, r"^[a-z][a-z0-9-]{2,62}$")

    def test_lifecycle_arguments_require_cleanup_and_never_keep_resources(self):
        arguments = protected_lifecycle_arguments(
            config_path=Path(".liveks/canary.yaml"),
            environment="canary-123-1",
            environ=complete_environment(),
        )
        self.assertEqual(arguments[0], "e2e")
        self.assertIn("--cleanup", arguments)
        self.assertIn("--yes", arguments)
        self.assertNotIn("--keep-resources", arguments)
        self.assertNotIn("full", arguments)
        self.assertNotIn("fabric", " ".join(arguments).lower())


class ProtectedCanaryEvidenceTests(unittest.TestCase):
    def test_capsule_is_allowlist_only_and_redacts_detailed_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            environment = "canary-123-1"
            report_dir = root / "deployments" / environment
            report_dir.mkdir(parents=True)
            e2e_report = {
                "status": "pass",
                "environment": environment,
                "retrySummary": {
                    "retryCount": 2,
                    "recoveredCount": 1,
                    "categoryCounts": {"http-429": 1, "network-timeout": 1},
                    "terminalCategories": {"http-503-exhausted": 1},
                },
                "phases": {
                    "up": {
                        "checks": [
                            {
                                "name": "search-index-retrieve",
                                "status": "pass",
                                "message": "private query and https://private.example",
                                "evidenceCount": 2,
                            },
                            {
                                "name": "mcp-retrieve",
                                "status": "pass",
                                "message": "raw answer secret-token",
                                "evidenceCount": 3,
                            },
                            {
                                "name": "combined-retrieve",
                                "status": "pass",
                                "sourceTypes": ["searchIndex", "mcpServer"],
                                "sourceCounts": {"searchIndex": 1, "mcpServer": 2},
                            },
                            {
                                "name": "unapproved-diagnostic",
                                "status": "pass",
                                "message": "33333333-3333-3333-3333-333333333333",
                            },
                        ]
                    },
                    "down": {
                        "status": "pass",
                        "checks": [
                            {"name": "delete-combinedKnowledgeBase", "status": "pass"},
                            {"name": "search-index-preserved", "status": "pass"},
                        ],
                    },
                },
            }
            (report_dir / "e2e-report.json").write_text(
                json.dumps(e2e_report),
                encoding="utf-8",
            )
            cleanup_path = root / ".deployment" / "canary-cleanup.json"
            cleanup_path.parent.mkdir(parents=True)
            cleanup_path.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "retrySummary": {
                            "retryCount": 1,
                            "recoveredCount": 1,
                            "categoryCounts": {"http-500": 1},
                            "terminalCategories": {},
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = root / ".deployment" / "canary-evidence.json"
            detail = root / ".deployment" / "canary-detail.json"
            summary = root / ".deployment" / "step-summary.md"
            with mock.patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}):
                capsule = build_canary_evidence(
                    root,
                    environment=environment,
                    preflight_outcome="success",
                    login_outcome="success",
                    lifecycle_outcome="success",
                    cleanup_outcome="success",
                    output_path=output,
                    detail_path=detail,
                    summary_path=summary,
                )

            serialized = output.read_text(encoding="utf-8")
            summary_text = summary.read_text(encoding="utf-8")

        self.assertEqual(set(capsule), set(CAPSULE_KEYS))
        self.assertEqual(capsule["status"], "pass")
        self.assertEqual(capsule["protectedLive"]["status"], "run")
        self.assertEqual(
            capsule["sourceEvidence"]["counts"],
            {"mcpServer": 5, "searchIndex": 3},
        )
        self.assertEqual(capsule["retries"]["retryCount"], 3)
        self.assertEqual(capsule["cleanup"]["status"], "pass")
        self.assertEqual(len(capsule["detailedReport"]["sha256"]), 64)
        self.assertNotIn("unapproved-diagnostic", serialized)
        for forbidden in (
            "private query",
            "private.example",
            "secret-token",
            "33333333-3333-3333-3333-333333333333",
            environment,
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("Only the allowlist-sanitized capsule is uploaded.", summary_text)

    def test_missing_preflight_is_explicitly_not_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            capsule = build_canary_evidence(
                root,
                environment="canary-123-1",
                preflight_outcome="failure",
                login_outcome="skipped",
                lifecycle_outcome="skipped",
                cleanup_outcome="skipped",
                output_path=root / "capsule.json",
                detail_path=root / "detail.json",
            )

        self.assertEqual(capsule["status"], "not-run")
        self.assertEqual(capsule["protectedLive"]["status"], "not-run")
        self.assertEqual(capsule["cleanup"]["status"], "not-run")

    def test_capsule_validator_rejects_urls_guids_and_unknown_fields(self):
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            assert_canary_evidence_safe({"unexpected": "value"})
        with self.assertRaisesRegex(ValueError, "URL"):
            assert_canary_evidence_safe(
                {key: [] if key == "assertions" else {} for key in CAPSULE_KEYS}
                | {"kind": "https://private.example"}
            )


class ProtectedCanaryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / ".github" / "workflows" / "protected-mcp-search-index.yml"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.workflow = yaml.load(cls.text, Loader=yaml.BaseLoader)
        cls.job = cls.workflow["jobs"]["live-canary"]
        cls.steps = {step["name"]: step for step in cls.job["steps"]}

    def test_trigger_permissions_environment_concurrency_and_timeout(self):
        self.assertEqual(set(self.workflow["on"]), {"workflow_dispatch"})
        self.assertNotIn("schedule:", self.text)
        self.assertEqual(
            self.workflow["permissions"],
            {"contents": "read"},
        )
        self.assertEqual(
            self.job["permissions"],
            {"contents": "read", "id-token": "write"},
        )
        self.assertEqual(
            self.workflow["concurrency"],
            {
                "group": "protected-mcp-search-index-live",
                "cancel-in-progress": "false",
            },
        )
        self.assertEqual(self.job["environment"], "mcp-search-index-live")
        self.assertEqual(self.job["timeout-minutes"], "35")

    def test_untrusted_contexts_cannot_enter_credentialed_job(self):
        condition = self.job["if"]
        self.assertIn("github.event_name == 'workflow_dispatch'", condition)
        self.assertIn(
            "github.repository == 'microsoft/azure-ai-search-foundry-iq-live-knowledge-sources'",
            condition,
        )
        self.assertIn("github.ref == 'refs/heads/main'", condition)
        self.assertIn("inputs.confirmation == 'run-with-cleanup'", condition)
        self.assertNotIn("pull_request", set(self.workflow["on"]))
        self.assertNotIn("pull_request_target", set(self.workflow["on"]))

    def test_preflight_precedes_login_and_names_required_configuration(self):
        names = [step["name"] for step in self.job["steps"]]
        self.assertLess(
            names.index("Preflight protected configuration"),
            names.index("Sign in to Azure with OIDC"),
        )
        preflight = self.steps["Preflight protected configuration"]
        for name in (
            "AZURE_CLIENT_ID",
            "AZURE_TENANT_ID",
            "AZURE_SUBSCRIPTION_ID",
            "SEARCH_ENDPOINT",
            "SEARCH_INDEX_NAME",
            "SEARCH_SEMANTIC_CONFIGURATION_NAME",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT_ID",
            "AZURE_OPENAI_MODEL_NAME",
            "LIVEKS_INDEX_QUERY",
            "LIVEKS_INDEX_EXPECT_TERM",
            "LIVEKS_COMBINED_QUERY",
        ):
            self.assertIn(name, preflight["env"])

    def test_run_unique_environment_and_guarded_cleanup_only_lifecycle(self):
        generated = self.job["env"]["LIVEKS_CANARY_ENVIRONMENT"]
        self.assertIn("github.run_id", generated)
        self.assertIn("github.run_attempt", generated)
        lifecycle = self.steps["Run guarded lifecycle with cleanup"]
        self.assertEqual(lifecycle["continue-on-error"], "true")
        self.assertIn("ProtectedMcpSearchIndexLifecycleCanaryTests", lifecycle["run"])
        self.assertNotIn("--keep-resources", self.text)
        self.assertNotIn("profile: full", self.text)
        self.assertNotIn("byo-fabric", self.text)

    def test_cleanup_and_evidence_always_run_with_bounded_commands(self):
        cleanup = self.steps["Always retry guarded cleanup"]
        evidence = self.steps["Always build sanitized canary evidence"]
        self.assertIn("always()", cleanup["if"])
        self.assertIn("always()", evidence["if"])
        self.assertIn("timeout --signal=INT", cleanup["run"])
        self.assertIn("--yes", cleanup["run"])
        self.assertIn("canary-cleanup.json", cleanup["run"])
        self.assertIn("--kill-after=30s 1200s", self.steps["Run guarded lifecycle with cleanup"]["run"])

    def test_only_sanitized_capsule_is_uploaded(self):
        upload = self.steps["Upload sanitized canary capsule"]
        self.assertEqual(upload["with"]["path"], ".deployment/canary-evidence.json")
        self.assertNotIn("canary-detail.json", upload["with"]["path"])
        self.assertNotIn("deployments/", upload["with"]["path"])
        self.assertNotIn("e2e-report", upload["with"]["path"])


if __name__ == "__main__":
    unittest.main()
