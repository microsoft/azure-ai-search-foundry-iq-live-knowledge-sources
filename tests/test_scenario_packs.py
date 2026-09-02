import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import scenarios  # noqa: E402


class ScenarioPackTests(unittest.TestCase):
    def setUp(self):
        self.registry = scenarios.load_registry(ROOT, deep=True)

    def copied_root(self, temp_dir: str) -> Path:
        root = Path(temp_dir)
        for directory in ("config", "evals", "profiles", "scenario-packs"):
            shutil.copytree(ROOT / directory, root / directory)
        for directory in ("samples/responses", "samples/ontology", "samples/data"):
            shutil.copytree(ROOT / directory, root / directory)
        return root

    def manifest(self, root: Path, pack: str) -> tuple[Path, dict]:
        path = root / "scenario-packs" / pack / "manifest.json"
        return path, json.loads(path.read_text(encoding="utf-8"))

    def write_manifest(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_registry_order_and_legacy_aliases_are_deterministic(self):
        self.assertEqual(
            list(self.registry["cases"]),
            [
                "airline-ops.combined-guidance-replay",
                "airline-ops.fabric-exposure-replay",
                "airline-ops.three-source-replay",
                "microsoft-learn-mcp.guidance-replay",
            ],
        )
        self.assertEqual(
            self.registry["aliases"],
            {
                "combined": "airline-ops.combined-guidance-replay",
                "fabric": "airline-ops.fabric-exposure-replay",
                "mcp": "microsoft-learn-mcp.guidance-replay",
                "semantic-join": "airline-ops.combined-guidance-replay",
                "three-source": "airline-ops.three-source-replay",
            },
        )

    def test_new_synthetic_domain_is_discovered_without_python_registry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            _, manifest = self.manifest(root, "microsoft-learn-mcp")
            manifest["pack"].update(
                {
                    "id": "second-domain",
                    "title": "Second synthetic domain",
                    "domain": "second-synthetic-domain",
                }
            )
            case = manifest["cases"][0]
            case["id"] = "second-domain.guidance-replay"
            case["aliases"] = ["second-domain"]
            target = root / "scenario-packs/second-domain/manifest.json"
            target.parent.mkdir()
            self.write_manifest(target, manifest)

            registry = scenarios.load_registry(root)

        self.assertIn("second-domain.guidance-replay", registry["cases"])
        self.assertEqual(
            registry["aliases"]["second-domain"],
            "second-domain.guidance-replay",
        )

    def test_validate_and_run_all_are_deterministic(self):
        first = scenarios.validate_all(ROOT, run_all=True)
        second = scenarios.validate_all(ROOT, run_all=True)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "pass")
        self.assertEqual(first["networkCalls"], 0)
        self.assertEqual(len(first["runs"]), 4)

    def test_structured_fixture_digest_is_line_ending_independent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            lf = folder / "lf.json"
            crlf = folder / "crlf.json"
            lf.write_bytes(b'{\n  "value": true\n}\n')
            crlf.write_bytes(b'{\r\n  "value": true\r\n}\r\n')
            self.assertEqual(
                scenarios.scenario_file_sha256(lf),
                scenarios.scenario_file_sha256(crlf),
            )

    def test_unknown_manifest_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "microsoft-learn-mcp")
            manifest["pack"]["unexpected"] = True
            self.write_manifest(path, manifest)
            with self.assertRaisesRegex(scenarios.ScenarioError, "unknown fields: unexpected"):
                scenarios.load_registry(root)

    def test_fixture_traversal_and_symlink_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "microsoft-learn-mcp")
            manifest["cases"][0]["fixture"]["path"] = "../outside.json"
            self.write_manifest(path, manifest)
            with self.assertRaisesRegex(scenarios.ScenarioError, "repository-relative path"):
                scenarios.load_registry(root)

        if os.name == "nt":
            self.skipTest("Symlink creation is not generally available on Windows runners.")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            outside = Path(temp_dir) / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            fixture_dir = root / "samples/responses"
            fixture_dir.mkdir(parents=True)
            (fixture_dir / "escape.json").symlink_to(outside)
            with self.assertRaisesRegex(scenarios.ScenarioError, "escapes the repository"):
                scenarios._safe_path(
                    root,
                    "samples/responses/escape.json",
                    location="fixture",
                    prefixes=("samples/responses/",),
                )

    def test_symlink_cannot_escape_the_allowed_in_repo_prefix(self):
        if os.name == "nt":
            self.skipTest("Symlink creation is not generally available on Windows runners.")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside_prefix = root / "infra/payload.json"
            outside_prefix.parent.mkdir(parents=True)
            outside_prefix.write_text("{}\n", encoding="utf-8")
            fixture_dir = root / "samples/responses"
            fixture_dir.mkdir(parents=True)
            (fixture_dir / "escape.json").symlink_to(outside_prefix)
            with self.assertRaisesRegex(
                scenarios.ScenarioError,
                "outside the allowed path prefixes",
            ):
                scenarios._safe_path(
                    root,
                    "samples/responses/escape.json",
                    location="fixture",
                    prefixes=("samples/responses/",),
                )

    def test_secret_or_tenant_shaped_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "microsoft-learn-mcp")
            manifest["cases"][0]["syntheticQuery"] = (
                "tenant 11111111-1111-1111-1111-111111111111"
            )
            self.write_manifest(path, manifest)
            with self.assertRaisesRegex(scenarios.ScenarioError, "tenant-shaped"):
                scenarios.load_registry(root)

    def test_unknown_profile_source_and_missing_assertion_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "microsoft-learn-mcp")
            case = manifest["cases"][0]
            case["profile"] = "unknown-profile"
            case["expectedSources"][0]["type"] = "unknownSource"
            case["assertions"].pop()
            self.write_manifest(path, manifest)
            with self.assertRaises(scenarios.ScenarioError) as caught:
                scenarios.load_registry(root, deep=True)
        message = str(caught.exception)
        self.assertIn("unknown source type", message)
        self.assertIn("assertions must contain exactly", message)
        self.assertIn("unknown deployment profile", message)

    def test_unknown_ownership_cleanup_and_adapter_values_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "microsoft-learn-mcp")
            case = manifest["cases"][0]
            case["ownershipClass"] = "unknown"
            case["cleanupExpectation"] = "unknown"
            case["protectedLive"]["adapter"] = "unknown"
            self.write_manifest(path, manifest)
            with self.assertRaises(scenarios.ScenarioError) as caught:
                scenarios.load_registry(root)
        message = str(caught.exception)
        self.assertIn("unknown ownershipClass", message)
        self.assertIn("unknown cleanupExpectation", message)
        self.assertIn("unknown protectedLive adapter", message)

    def test_text_configuration_failure_is_redacted_and_does_not_crash(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = scenarios.main(["run", "does-not-exist"])
        self.assertEqual(exit_code, 2)
        self.assertIn("[FAIL] scenario-configuration", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_fixture_and_ontology_digest_drift_are_actionable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            fixture = root / "samples/responses/mcp-retrieve.sample.json"
            fixture.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(scenarios.ScenarioError, "fixture digest is stale"):
                scenarios.load_registry(root)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            ontology = root / "samples/ontology/airline-ops/ontology-contract.yaml"
            ontology.write_text(
                ontology.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(scenarios.ScenarioError, "ontology digest is stale"):
                scenarios.load_registry(root, deep=True)

    def test_wrong_source_and_expected_term_fail_named_assertions(self):
        base = json.loads(
            (ROOT / "samples/responses/mcp-retrieve.sample.json").read_text(
                encoding="utf-8"
            )
        )
        base["activity"][0]["type"] = "fabricOntology"
        base["response"][0]["content"][0]["text"] = "No expected fact."
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "bad.json"
            fixture.write_text(json.dumps(base), encoding="utf-8")
            report = scenarios.run_case(
                "mcp",
                root=ROOT,
                fixture_override=fixture,
            )
        statuses = {item["id"]: item["status"] for item in report["checks"]}
        self.assertEqual(statuses["known-facts"], "fail")
        self.assertEqual(statuses["activity-evidence"], "fail")

    def test_missing_source_data_fails_source_contract_assertion(self):
        base = json.loads(
            (ROOT / "samples/responses/mcp-retrieve.sample.json").read_text(
                encoding="utf-8"
            )
        )
        base["references"][0].pop("sourceData")
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "bad.json"
            fixture.write_text(json.dumps(base), encoding="utf-8")
            report = scenarios.run_case(
                "mcp",
                root=ROOT,
                fixture_override=fixture,
            )
        statuses = {item["id"]: item["status"] for item in report["checks"]}
        self.assertEqual(statuses["source-contract"], "fail")

    def test_ownership_cleanup_contradiction_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "airline-ops")
            manifest["cases"][0]["cleanupExpectation"] = "none"
            self.write_manifest(path, manifest)
            with self.assertRaisesRegex(
                scenarios.ScenarioError,
                "cleanupExpectation must be delete-generated-azure-preserve-reused-fabric",
            ):
                scenarios.load_registry(root, deep=True)

    def test_duplicate_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.copied_root(temp_dir)
            path, manifest = self.manifest(root, "airline-ops")
            manifest["cases"][1]["aliases"].append("fabric")
            self.write_manifest(path, manifest)
            with self.assertRaisesRegex(scenarios.ScenarioError, "duplicate scenario alias"):
                scenarios.load_registry(root)

    def test_safe_output_and_capsule_redact_domain_values(self):
        report = scenarios.run_case("combined", root=ROOT)
        safe = scenarios.safe_run_report(report)
        capsule = scenarios.build_evidence_capsule(report, root=ROOT)
        serialized = json.dumps({"safe": safe, "capsule": capsule})
        for forbidden in (
            "Alpine Air",
            "fabric-ontology-ks",
            "microsoft-learn-mcp-ks",
            "customer-care exposure",
            "fabricAnswer",
            "fabricRawData",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(capsule["privacy"]["sourceDataIncluded"])
        self.assertEqual(
            [item["id"] for item in capsule["assertions"]],
            ["known-facts", "activity-evidence", "reference-evidence", "source-contract"],
        )


if __name__ == "__main__":
    unittest.main()
