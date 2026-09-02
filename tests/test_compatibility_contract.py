import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/check_compatibility.py"
SPEC = importlib.util.spec_from_file_location("check_compatibility", SCRIPT_PATH)
assert SPEC and SPEC.loader
compatibility = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = compatibility
SPEC.loader.exec_module(compatibility)


class CompatibilityContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = compatibility.load_compatibility_contract(ROOT / "config/compatibility.yaml")

    def test_repository_contract_is_current(self):
        self.assertEqual(compatibility.validate_contract(ROOT, self.contract), [])

    def test_generated_documentation_check_reports_actionable_drift(self):
        changed = json.loads(json.dumps(self.contract))
        changed["command_sets"]["posix"]["steps"][0]["display"] = "./liveks try --details"

        failures = compatibility.validate_contract(ROOT, changed)

        self.assertTrue(any("generated compatibility block is stale" in failure for failure in failures))
        self.assertTrue(any("--generate" in failure for failure in failures))

    def test_api_drift_reports_the_exact_schema_binding(self):
        changed = json.loads(json.dumps(self.contract))
        changed["api_contracts"]["search_index"]["version"] = "2099-01-01"

        failures = compatibility.validate_contract(ROOT, changed)

        self.assertTrue(
            any(
                "config/schema.yaml fields.search.api_version.values" in failure
                for failure in failures
            )
        )
        self.assertTrue(any("profiles/search-index.yaml" in failure for failure in failures))

    def test_generator_replaces_only_designated_block(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "README.md"
            path.write_text(
                "before\n<!-- test:start -->\nstale\n<!-- test:end -->\nafter\n",
                encoding="utf-8",
            )
            compatibility.write_generated_block(path, "test", "generated")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "before\n<!-- test:start -->\ngenerated\n<!-- test:end -->\nafter\n",
            )

    def test_command_evidence_accepts_expected_json(self):
        step = {
            "id": "doctor",
            "expected_exit": 0,
            "json_evidence": {"command": "doctor", "profile": "offline", "status": "pass"},
        }
        result = subprocess.CompletedProcess(
            ["liveks", "doctor"],
            0,
            json.dumps({"command": "doctor", "profile": "offline", "status": "pass"}),
            "",
        )

        self.assertEqual(compatibility.validate_command_evidence(step, result), [])

    def test_command_evidence_rejects_wrong_exit_and_missing_signal(self):
        wrong_exit = subprocess.CompletedProcess(["liveks", "try"], 1, "", "failed")
        self.assertEqual(
            compatibility.validate_command_evidence(
                {"id": "try", "expected_exit": 0, "stdout_contains": ["Contract: PASS"]},
                wrong_exit,
            ),
            ["try exited 1; expected 0"],
        )

        missing_signal = subprocess.CompletedProcess(["liveks", "try"], 0, "Contract: FAIL", "")
        self.assertEqual(
            compatibility.validate_command_evidence(
                {"id": "try", "expected_exit": 0, "stdout_contains": ["Contract: PASS"]},
                missing_signal,
            ),
            ["try stdout is missing expected evidence: Contract: PASS"],
        )

    def test_command_runner_stops_after_actionable_failure(self):
        minimal = {
            "command_sets": {
                "posix": {
                    "steps": [
                        {
                            "id": "try",
                            "display": "./liveks try",
                            "argv": ["./liveks", "try"],
                            "expected_exit": 0,
                            "stdout_contains": ["Contract: PASS"],
                        },
                        {
                            "id": "bootstrap",
                            "display": "./liveks bootstrap",
                            "argv": ["./liveks", "bootstrap"],
                            "expected_exit": 0,
                        },
                    ]
                }
            }
        }
        runner = mock.Mock(
            return_value=subprocess.CompletedProcess(["./liveks", "try"], 0, "Contract: FAIL", "")
        )

        with (
            mock.patch.object(compatibility.os, "name", "posix"),
            redirect_stdout(io.StringIO()),
        ):
            failures = compatibility.run_command_set(ROOT, minimal, "posix", run=runner)

        self.assertEqual(failures, ["try stdout is missing expected evidence: Contract: PASS"])
        runner.assert_called_once()

    def test_windows_command_contract_uses_powershell_argv(self):
        minimal = {
            "command_sets": {
                "windows": {
                    "steps": [
                        {
                            "id": "try",
                            "display": r".\liveks.ps1 try",
                            "argv": ["pwsh", "-NoProfile", "-File", r".\liveks.ps1", "try"],
                            "expected_exit": 0,
                            "stdout_contains": ["Contract: PASS"],
                        }
                    ]
                }
            }
        }
        runner = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["pwsh", "-NoProfile", "-File", r".\liveks.ps1", "try"],
                0,
                "Contract: PASS",
                "",
            )
        )

        with (
            mock.patch.object(compatibility.os, "name", "nt"),
            redirect_stdout(io.StringIO()),
        ):
            failures = compatibility.run_command_set(ROOT, minimal, "windows", run=runner)

        self.assertEqual(failures, [])
        self.assertEqual(
            runner.call_args.args[0],
            ["pwsh", "-NoProfile", "-File", r".\liveks.ps1", "try"],
        )


if __name__ == "__main__":
    unittest.main()
