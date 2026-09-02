import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/release.py"
SPEC = importlib.util.spec_from_file_location("release_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
release_contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_contract)


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.release = release_contract.load_release(ROOT / "config/release.json")

    def clone_release(self):
        return json.loads(json.dumps(self.release))

    def test_repository_release_contract_is_current(self):
        self.assertEqual(
            release_contract.validate_release_contract(ROOT, self.release),
            [],
        )

    def test_version_drift_names_the_changelog_and_azd_bindings(self):
        changed = self.clone_release()
        changed["product"]["version"] = "2.0.1"
        changed["product"]["tag"] = "v2.0.1"

        failures = release_contract.validate_release_contract(ROOT, changed)

        self.assertTrue(any("bindings.changelog.heading" in failure for failure in failures))
        self.assertTrue(any("metadata.template" in failure for failure in failures))
        self.assertTrue(any("must name release value" in failure for failure in failures))

    def test_missing_changelog_and_notes_are_actionable(self):
        changed = self.clone_release()
        changed["bindings"]["changelog"]["path"] = "missing-changelog.md"
        changed["bindings"]["releaseNotes"]["path"] = "missing-notes.md"

        failures = release_contract.validate_release_contract(ROOT, changed)

        self.assertIn("release changelog is missing: missing-changelog.md", failures)
        self.assertIn("release notes are missing: missing-notes.md", failures)

    def test_unsafe_archive_paths_fail_closed(self):
        changed = self.clone_release()
        changed["archive"]["includeExact"].append(".liveks/customer.yaml")
        changed["archive"]["includePrefixes"].append("deployments/")
        changed["archive"]["includeExact"].append(".env.sample")

        failures = release_contract.validate_archive_policy(changed)

        self.assertIn(
            "archive includeExact contains forbidden path: .liveks/customer.yaml",
            failures,
        )
        self.assertIn(
            "archive includePrefixes contains unsafe prefix: deployments/",
            failures,
        )
        self.assertIn(
            "archive includeExact contains forbidden path: .env.sample",
            failures,
        )

    def test_checksum_mismatch_names_the_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            artifact = output / "artifact.tar.gz"
            artifact.write_bytes(b"original")
            checksums = output / "SHA256SUMS.txt"
            checksums.write_text(
                f"{release_contract.sha256_file(artifact)}  {artifact.name}\n",
                encoding="utf-8",
            )
            artifact.write_bytes(b"changed")

            with self.assertRaisesRegex(
                release_contract.ReleaseError,
                "checksum mismatch for artifact.tar.gz",
            ):
                release_contract.verify_checksums(
                    output,
                    checksums.name,
                    {artifact.name},
                )

    def test_nondeterministic_outputs_name_changed_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            first.mkdir()
            second.mkdir()
            (first / "artifact").write_bytes(b"one")
            (second / "artifact").write_bytes(b"two")

            with self.assertRaisesRegex(
                release_contract.ReleaseError,
                "bytes differ for artifact",
            ):
                release_contract.compare_output_dirs(first, second)

    def test_workflow_policy_rejects_mutable_action_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workflow.yml"
            path.write_text(
                "steps:\n  - uses: actions/checkout@v7\n",
                encoding="utf-8",
            )

            failures = release_contract.validate_action_pins(
                path,
                self.release["workflowPolicy"],
            )

        self.assertEqual(len(failures), 1)
        self.assertIn("40-character commit SHA", failures[0])

    def test_private_component_versions_are_not_product_bindings(self):
        binding_paths = json.dumps(self.release["bindings"], sort_keys=True)
        for component in self.release["independentComponents"]:
            self.assertNotIn(component["path"], binding_paths)


if __name__ == "__main__":
    unittest.main()
