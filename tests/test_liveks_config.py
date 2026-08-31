import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import cli  # noqa: E402
from liveks.config import ConfigError, available_profiles, parse_legacy_env, resolve_config  # noqa: E402
from liveks.runtime import CommandResult  # noqa: E402


class LiveKsConfigTests(unittest.TestCase):
    def test_profiles_are_ordered_and_include_full(self):
        self.assertEqual(
            available_profiles(),
            ["offline", "search-index", "mcp-search-index", "mcp-only", "byo-fabric", "full"],
        )

    def test_mcp_profile_resolves_to_azd_values(self):
        config = resolve_config(profile="mcp-only", environment="unit-mcp")
        values = config.azd_values()
        self.assertEqual(values["DEPLOYMENT_MODE"], "mcp-only")
        self.assertEqual(values["MCP_SERVER_URL"], "https://learn.microsoft.com/api/mcp")
        self.assertEqual(values["MCP_TOOL_NAME"], "microsoft_docs_search")
        self.assertEqual(values["FABRIC_ONLY_KNOWLEDGE_BASE_NAME"], "live-knowledge-sources-fabric-kb")
        self.assertEqual(values["AZURE_OPENAI_MODEL_NAME"], "gpt-5-mini")
        self.assertEqual(values["AZURE_RESOURCE_GROUP"], "rg-unit-mcp")

    def test_unknown_yaml_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text(
                "version: 2\nprofile: mcp-only\nenvironment: unit-mcp\nunknown:\n  value: true\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "Unknown configuration fields"):
                resolve_config(profile=None, environment=None, config_path=path)

    def test_stable_api_version_fails_before_provisioning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text(
                "version: 2\n"
                "profile: mcp-only\n"
                "environment: unit-stable\n"
                "search:\n"
                "  api_version: '2026-04-01'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "2026-05-01-preview"):
                resolve_config(profile=None, environment=None, config_path=path)

    def test_secret_must_be_environment_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text(
                "version: 2\nprofile: mcp-only\nenvironment: unit-mcp\nfabric:\n  user_search_token: raw-secret\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "environment reference"):
                resolve_config(profile=None, environment=None, config_path=path)

    def test_legacy_env_parser_does_not_execute_shell(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "executed"
            path = Path(temp_dir) / "legacy.env"
            path.write_text(f"MCP_TOOL_NAME=$(touch {marker})\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                parse_legacy_env(path)
            self.assertFalse(marker.exists())

    def test_legacy_placeholder_is_parsed_without_bash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "legacy.env"
            path.write_text("FABRIC_USER_SEARCH_TOKEN=<optional-token>\n", encoding="utf-8")
            self.assertEqual(parse_legacy_env(path)["FABRIC_USER_SEARCH_TOKEN"], "<optional-token>")

    def test_full_profile_rejects_byo_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text(
                "version: 2\nprofile: full\nenvironment: unit-full\nfabric:\n  workspace_id: 11111111-1111-1111-1111-111111111111\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "must not include BYO"):
                resolve_config(profile=None, environment=None, config_path=path)

    def test_legacy_init_preserves_profile_ownership_boundaries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "legacy.env"
            legacy.write_text(
                "DEPLOYMENT_MODE=byo-fabric\n"
                "EXTERNAL_TENANT_ID=11111111-1111-1111-1111-111111111111\n"
                "FABRIC_CAPACITY_MODE=byo\n"
                "FABRIC_WORKSPACE_ID=22222222-2222-2222-2222-222222222222\n"
                "FABRIC_ONTOLOGY_ID=33333333-3333-3333-3333-333333333333\n",
                encoding="utf-8",
            )
            for profile in ("mcp-only", "full"):
                destination = root / f"{profile}.yaml"
                cli._init_from_legacy(legacy, profile, f"unit-{profile}", destination)
                config = resolve_config(profile=None, environment=None, config_path=destination)
                self.assertEqual(config.profile, profile)
                self.assertEqual(config.get("deployment.mode"), profile)
                self.assertFalse(config.get("fabric.workspace_id"))
                self.assertFalse(config.get("fabric.ontology_id"))
                self.assertEqual(config.get("fabric.mode"), "skip" if profile == "mcp-only" else "create")

    def test_secret_value_is_not_serialized(self):
        config = resolve_config(profile="mcp-only", environment="unit-secret")
        config.values["fabric.user_search_token"] = {"env": "FABRIC_USER_SEARCH_TOKEN"}
        with mock.patch.dict(os.environ, {"FABRIC_USER_SEARCH_TOKEN": "secret-value"}):
            self.assertEqual(config.child_env()["FABRIC_USER_SEARCH_TOKEN"], "secret-value")
            serialized = json.dumps(config.nested())
            self.assertNotIn("secret-value", serialized)

    def test_evidence_types_accept_dynamic_combined_routing(self):
        fabric_only = {"mode": "live", "activity": [{"type": "fabricOntology"}], "references": []}
        both = {
            "mode": "live",
            "activity": [{"type": "fabricOntology"}],
            "references": [{"type": "mcpServer"}, {"type": "fabricOntology"}],
        }
        self.assertEqual(cli._evidence_types(fabric_only), ["fabricOntology"])
        self.assertEqual(cli._evidence_types(both), ["fabricOntology", "mcpServer"])

    def test_live_evidence_rejects_offline_fixture_activity(self):
        offline = {"mode": "offline", "activity": [{"type": "mcpServer"}], "references": []}
        live = {"mode": "live", "activity": [{"type": "mcpServer"}], "references": []}
        self.assertFalse(cli._response_has_live_evidence(offline, "mcpServer"))
        self.assertTrue(cli._response_has_live_evidence(live, "mcpServer"))

    def test_e2e_reports_preserve_machine_and_maintainer_formats(self):
        config = resolve_config(profile="mcp-only", environment="unit-report")
        report = {
            "schemaVersion": 2,
            "command": "e2e",
            "status": "pass",
            "profile": "mcp-only",
            "environment": "unit-report",
            "phases": {
                "up": {"checks": [{"name": "mcp-retrieve", "status": "pass", "message": "live | evidence"}]},
                "down": {
                    "checks": [
                        {
                            "name": "resource-group-absent",
                            "status": "pass",
                            "message": "absent; super-secret-token; https://private-search.example",
                        }
                    ]
                },
            },
            "artifacts": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)):
            artifacts = cli.write_e2e_reports(config, report, cleanup_requested=True)
            json_report = json.loads((Path(temp_dir) / "deployments/unit-report/e2e-report.json").read_text())
            markdown_report = (Path(temp_dir) / "deployments/unit-report/test-report.md").read_text()
            capsule = json.loads((Path(temp_dir) / "deployments/unit-report/evidence-capsule.json").read_text())
            capsule_markdown = (Path(temp_dir) / "deployments/unit-report/evidence-capsule.md").read_text()
        self.assertEqual(len(artifacts), 4)
        self.assertEqual(json_report["status"], "pass")
        self.assertIn("- Deployment mode: `mcp-only`", markdown_report)
        self.assertIn("| `PASS` | mcp-retrieve | live \\| evidence |", markdown_report)
        self.assertIn("| `PASS` | resource-group-absent | absent; super-secret-token", markdown_report)
        self.assertEqual(capsule["kind"], "liveks-evidence-capsule")
        self.assertEqual(capsule["observedEvidence"]["sourceTypes"], ["mcpServer"])
        self.assertFalse(capsule["privacy"]["messagesIncluded"])
        self.assertNotIn("unit-report", json.dumps(capsule))
        self.assertNotIn("super-secret-token", json.dumps(capsule))
        self.assertNotIn("private-search.example", capsule_markdown)

    def test_bicep_parameters_cover_canonical_names(self):
        parameters = json.loads((ROOT / "infra/main.parameters.json").read_text(encoding="utf-8"))["parameters"]
        expected = {
            "searchApiVersion",
            "airlineOpsIndexName",
            "mcpKnowledgeSourceName",
            "fabricKnowledgeSourceName",
            "mcpOnlyKnowledgeBaseName",
            "fabricOnlyKnowledgeBaseName",
            "knowledgeBaseName",
        }
        self.assertTrue(expected.issubset(parameters))


class FakeRunner:
    instances = []

    def __init__(self, *, root, env, quiet=False):
        self.history = []
        self.__class__.instances.append(self)

    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        self.history.append(args)
        return CommandResult(args, 0, "ok\n")


class LiveKsPlanSafetyTests(unittest.TestCase):
    def test_generic_cleanup_accepts_legacy_active_lock_without_authored_digest(self):
        config = resolve_config(profile="full", environment="unit-legacy-cleanup")
        legacy_lock = {
            "schemaVersion": 2,
            "status": "deployed",
            "profile": config.profile,
            "environment": config.environment,
            "configDigest": "runtime-derived-digest",
            "ownership": config.ownership(),
        }
        with mock.patch.object(cli, "_load_lock", return_value=legacy_lock):
            lock, error = cli._generic_cleanup_lock(config)

        self.assertIs(lock, legacy_lock)
        self.assertIsNone(error)

    def test_incomplete_cleanup_preserves_new_lock_safety_metadata(self):
        metadata = cli._preserved_cleanup_metadata(
            {
                "authoredConfigDigest": "authored-digest",
                "resourceGroupPreexisting": False,
                "unrelated": "omit",
            }
        )

        self.assertEqual(
            metadata,
            {
                "authoredConfigDigest": "authored-digest",
                "resourceGroupPreexisting": False,
            },
        )

    def test_plan_rejects_active_foreign_profile_lock_without_managed_objects(self):
        config = resolve_config(profile="mcp-only", environment="unit-active-lock")
        foreign_lock = {
            "schemaVersion": 2,
            "status": "deployed",
            "profile": "full",
            "environment": config.environment,
            "configDigest": "different",
            "ownership": {"azure": "create", "fabricCapacity": "create"},
        }
        with (
            mock.patch.object(cli, "_load_lock", return_value=foreign_lock),
            mock.patch.object(cli, "doctor_report") as doctor_mock,
        ):
            report = cli.plan_report(config, operation_locked=True)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["checks"][0]["name"], "environment-lock")
        doctor_mock.assert_not_called()

    def test_plan_never_calls_mutating_cloud_commands(self):
        config = resolve_config(profile="mcp-only", environment="unit-plan")
        FakeRunner.instances = []
        passing_doctor = {
            "status": "pass",
            "checks": [{"name": "doctor", "status": "pass", "message": "ok"}],
        }
        with mock.patch.object(cli, "doctor_report", return_value=passing_doctor), mock.patch.object(cli, "CommandRunner", FakeRunner):
            report = cli.plan_report(config)
        commands = [command for runner in FakeRunner.instances for command in runner.history]
        flattened = [" ".join(command) for command in commands]
        self.assertEqual(report["status"], "pass")
        self.assertFalse(any("azd env set" in command for command in flattened))
        self.assertFalse(any("azd up" in command for command in flattened))
        self.assertFalse(any("fabric-provision" in command for command in flattened))

    def test_compatibility_skip_flags_remove_only_requested_local_checks(self):
        config = resolve_config(profile="mcp-only", environment="unit-plan-skips")
        FakeRunner.instances = []
        passing_doctor = {
            "status": "pass",
            "checks": [{"name": "doctor", "status": "pass", "message": "ok"}],
        }
        with mock.patch.object(cli, "doctor_report", return_value=passing_doctor), mock.patch.object(cli, "CommandRunner", FakeRunner):
            report = cli.plan_report(config, skip_app_build=True, skip_dry_run=True)
        commands = [" ".join(command) for runner in FakeRunner.instances for command in runner.history]
        self.assertEqual(report["status"], "pass")
        self.assertTrue(any("az bicep build" in command for command in commands))
        self.assertFalse(any("postprovision.py" in command for command in commands))
        self.assertFalse(any("npm" in command for command in commands))

    def test_full_requires_explicit_capacity_acceptance(self):
        config = resolve_config(profile="full", environment="unit-full")
        with self.assertRaisesRegex(PermissionError, "accept-fabric-capacity"):
            cli._confirm_up(config, yes=True, accept_fabric_capacity=False)

    def test_full_liveks_path_reuses_preprovisioned_capacity_in_bicep(self):
        config = resolve_config(profile="full", environment="unit-full-reuse")
        FakeRunner.instances = []
        passing_plan = {"status": "warn", "checks": [], "resources": []}
        passing_verify = {"status": "pass", "checks": []}
        with (
            mock.patch.object(cli, "plan_report", return_value=passing_plan),
            mock.patch.object(cli, "verify_report", return_value=passing_verify),
            mock.patch.object(cli, "CommandRunner", FakeRunner),
        ):
            report = cli.up_report(config, yes=True, accept_fabric_capacity=True)
        commands = [command for runner in FakeRunner.instances for command in runner.history]
        cleared = [commands.index(["azd", "env", "set", key, ""]) for key in cli.GENERATED_FABRIC_AZD_KEYS]
        projected = commands.index(["azd", "env", "set", "FABRIC_CAPACITY_MODE", "byo"])
        preview = commands.index(["azd", "provision", "--preview", "--environment", "unit-full-reuse", "--no-prompt"])
        provision = next(index for index, command in enumerate(commands) if "scripts/fabric-provision.py" in command)
        deployment = commands.index(["azd", "up", "--environment", "unit-full-reuse", "--no-prompt"])
        restored = max(index for index, command in enumerate(commands) if command == ["azd", "env", "set", "FABRIC_CAPACITY_MODE", "create"])
        self.assertEqual(report["status"], "pass")
        self.assertTrue(all(index < projected for index in cleared))
        self.assertLess(projected, preview)
        self.assertLess(preview, provision)
        self.assertLess(provision, deployment)
        self.assertLess(deployment, restored)

    def test_e2e_holds_one_operation_lock_across_up_and_cleanup(self):
        config = resolve_config(profile="mcp-only", environment="unit-e2e-lock")
        events = []

        class RecordingLock:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                events.append("lock-enter")
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                events.append("lock-exit")

        def fake_up(*args, **kwargs):
            self.assertTrue(kwargs["operation_locked"])
            events.append("up")
            return {"status": "pass", "checks": [], "artifacts": []}

        def fake_down(*args, **kwargs):
            self.assertTrue(kwargs["operation_locked"])
            events.append("down")
            return {"status": "pass", "checks": [], "artifacts": []}

        with (
            mock.patch.object(cli, "_resolve_from_args", return_value=config),
            mock.patch.object(cli, "EnvironmentOperationLock", RecordingLock),
            mock.patch.object(cli, "up_report", side_effect=fake_up),
            mock.patch.object(cli, "down_report", side_effect=fake_down),
            mock.patch.object(cli, "write_e2e_reports"),
            mock.patch("sys.stdout"),
        ):
            result = cli.main(
                [
                    "e2e",
                    "--env",
                    "unit-e2e-lock",
                    "--cleanup",
                    "--yes",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(events, ["lock-enter", "up", "down", "lock-exit"])

    def test_e2e_skips_cleanup_when_up_rejects_foreign_ownership(self):
        config = resolve_config(profile="mcp-only", environment="unit-e2e-foreign")
        rejected_up = {
            "status": "fail",
            "checks": [
                {
                    "name": "environment-lock",
                    "status": "fail",
                    "message": "foreign active ledger",
                }
            ],
            "artifacts": [],
        }
        with (
            mock.patch.object(cli, "_resolve_from_args", return_value=config),
            mock.patch.object(cli, "up_report", return_value=rejected_up),
            mock.patch.object(cli, "down_report") as down_mock,
            mock.patch.object(cli, "write_e2e_reports"),
            mock.patch("sys.stdout"),
        ):
            result = cli.main(
                [
                    "e2e",
                    "--env",
                    "unit-e2e-foreign",
                    "--cleanup",
                    "--yes",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(result, 1)
        down_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
