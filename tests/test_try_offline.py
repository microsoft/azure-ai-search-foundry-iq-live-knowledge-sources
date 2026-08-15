import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import try_offline  # noqa: E402


class OfflineFirstSuccessTests(unittest.TestCase):
    def test_every_packaged_scenario_satisfies_its_contract(self):
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

    def test_missing_expected_reference_fails_the_first_success_contract(self):
        original = json.loads(try_offline.SAMPLES["combined"].read_text(encoding="utf-8"))
        original["references"] = [
            item for item in original["references"] if item.get("type") != "mcpServer"
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "combined.json"
            fixture.write_text(json.dumps(original), encoding="utf-8")
            with mock.patch.dict(try_offline.SAMPLES, {"combined": fixture}):
                report = try_offline.build_report("combined")
                with redirect_stdout(StringIO()):
                    exit_code = try_offline.main(["--sample", "combined", "--format", "json"])

        reference_check = next(check for check in report["checks"] if check["name"] == "reference-evidence")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(reference_check["status"], "fail")
        self.assertEqual(exit_code, 1)

    def test_evidence_capsule_omits_answer_query_and_raw_response(self):
        report = try_offline.build_report("combined")
        report["answer"] += " super-secret-value"
        report["response"]["privateQuery"] = "customer private question"

        capsule = try_offline.build_evidence_capsule(report)
        serialized = json.dumps(capsule)

        self.assertEqual(capsule["kind"], "liveks-evidence-capsule")
        self.assertEqual(capsule["scope"], "offline-first-success")
        self.assertEqual(capsule["networkCalls"], 0)
        self.assertFalse(capsule["privacy"]["rawResponseIncluded"])
        self.assertNotIn("super-secret-value", serialized)
        self.assertNotIn("customer private question", serialized)
        self.assertNotIn("response", capsule)


if __name__ == "__main__":
    unittest.main()
