import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import try_offline  # noqa: E402


class OfflineFirstSuccessTests(unittest.TestCase):
    def test_every_legacy_alias_satisfies_its_manifest_contract(self):
        expected_types = {
            "mcp": ["mcpServer"],
            "fabric": ["fabricOntology"],
            "combined": ["fabricOntology", "mcpServer"],
        }
        for sample, source_types in expected_types.items():
            with self.subTest(sample=sample):
                report = try_offline.build_report(sample)
                self.assertEqual(report["status"], "pass")
                self.assertEqual(report["sourceTypes"], source_types)
                self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))

    def test_missing_expected_reference_reports_assertion_without_raw_data(self):
        original_path = ROOT / "samples/responses/combined-airline-ops-retrieve.sample.json"
        original = json.loads(original_path.read_text(encoding="utf-8"))
        original["references"] = [
            item for item in original["references"] if item.get("type") != "mcpServer"
        ]
        original["privateQuery"] = "customer private question"
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "combined.json"
            fixture.write_text(json.dumps(original), encoding="utf-8")
            report = try_offline.build_report("combined", fixture_override=fixture)
            rendered = try_offline.render_text(report, details=True)

        reference_check = next(
            check for check in report["checks"] if check["id"] == "reference-evidence"
        )
        self.assertEqual(report["status"], "fail")
        self.assertEqual(reference_check["status"], "fail")
        self.assertIn("[FAIL] reference-evidence", rendered)
        self.assertNotIn("customer private question", rendered)
        self.assertNotIn("Alpine Air", rendered)
        self.assertNotIn("fabricAnswer", rendered)

    def test_evidence_capsule_omits_sensitive_replay_values(self):
        report = try_offline.build_report("combined")
        report["answer"] += " super-secret-value"
        report["response"]["privateQuery"] = "customer private question"

        capsule = try_offline.build_evidence_capsule(report)
        serialized = json.dumps(capsule)

        self.assertEqual(capsule["kind"], "liveks-evidence-capsule")
        self.assertEqual(capsule["scope"], "offline-scenario-replay")
        self.assertEqual(capsule["scenario"]["id"], "airline-ops.combined-guidance-replay")
        self.assertEqual(capsule["scenario"]["version"], "1.0.0")
        self.assertEqual(capsule["networkCalls"], 0)
        self.assertFalse(capsule["privacy"]["rawResponseIncluded"])
        self.assertFalse(capsule["privacy"]["sourceIdentitiesIncluded"])
        self.assertNotIn("super-secret-value", serialized)
        self.assertNotIn("customer private question", serialized)
        self.assertNotIn("Alpine Air", serialized)
        self.assertNotIn("fabric-ontology-ks", serialized)
        self.assertNotIn("response", capsule)

    def test_main_failure_json_is_redacted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_path = Path(temp_dir) / "capsule.json"
            with redirect_stdout(StringIO()) as output:
                exit_code = try_offline.main(
                    [
                        "--sample",
                        "combined",
                        "--format",
                        "json",
                        "--evidence-out",
                        str(evidence_path),
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertIn('"scenarioId": "airline-ops.combined-guidance-replay"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
