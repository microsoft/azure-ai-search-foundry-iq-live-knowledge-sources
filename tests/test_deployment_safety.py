import importlib.util
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_fabric_provision_module():
    path = REPO_ROOT / "scripts" / "fabric-provision.py"
    spec = importlib.util.spec_from_file_location("fabric_provision_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class FakeHttpResponse:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @staticmethod
    def read() -> bytes:
        return b'{"ok": true}'


class FabricProvisionSafetyTests(unittest.TestCase):
    def test_request_json_retries_transient_429(self):
        module = load_fabric_provision_module()
        http_error = urllib.error.HTTPError("https://example.test", 429, "Too Many Requests", {}, None)

        with (
            mock.patch.object(module.urllib.request, "urlopen", side_effect=[http_error, FakeHttpResponse()]) as urlopen,
            mock.patch.object(module.time, "sleep") as sleep,
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                status, _, payload = module.request_json(method="GET", url="https://example.test", token="token")

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_main_writes_capacity_summary_when_later_step_fails(self):
        module = load_fabric_provision_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            deployments_dir = Path(temp_dir) / "deployments"
            arm_id = "/subscriptions/000/resourceGroups/rg-unit-fabric/providers/Microsoft.Fabric/capacities/fabunit"

            with (
                mock.patch.object(module, "DEPLOYMENTS_DIR", deployments_dir),
                mock.patch.object(sys, "argv", ["fabric-provision.py", "--env-name", "unit"]),
                mock.patch.object(module, "load_azd_env", return_value={}),
                mock.patch.object(module, "run", return_value="admin@example.com"),
                mock.patch.object(module, "get_token", return_value="token"),
                mock.patch.object(module, "azd_set"),
                mock.patch.object(
                    module,
                    "ensure_capacity",
                    return_value=(
                        "capacity-guid",
                        {
                            "displayName": "fabunit",
                            "id": "capacity-guid",
                            "state": "Active",
                            "created": True,
                            "armId": arm_id,
                        },
                    ),
                ),
                mock.patch.object(module, "ensure_workspace", side_effect=RuntimeError("workspace boom")),
            ):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(RuntimeError):
                        module.main()

            summary_path = deployments_dir / "unit" / "fabric-summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["capacityId"], "capacity-guid")
            self.assertEqual(summary["capacityArmId"], arm_id)
            self.assertEqual(summary["capacityResourceGroup"], "rg-unit-fabric")
            self.assertTrue(summary["capacityCreated"])
            self.assertIn("workspace boom", summary["error"])


class ShellDeploymentSafetyTests(unittest.TestCase):
    def test_destroy_continues_to_azd_down_when_fabric_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir)
            marker = bin_dir / "azd-down.marker"

            write_executable(
                bin_dir / "python3",
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"scripts/fabric-destroy.py\" ]]; then\n"
                "  echo 'fake Fabric cleanup failed' >&2\n"
                "  exit 42\n"
                "fi\n"
                "exec /usr/bin/env python3 \"$@\"\n",
            )
            write_executable(
                bin_dir / "azd",
                f"#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"env\" && \"$2\" == \"select\" ]]; then exit 0; fi\n"
                "if [[ \"$1\" == \"env\" && \"$2\" == \"get-values\" ]]; then echo 'AZURE_ENV_NAME=\"unit\"'; exit 0; fi\n"
                f"if [[ \"$1\" == \"down\" ]]; then echo \"$*\" > {marker}; exit 0; fi\n"
                "exit 0\n",
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                ["bash", "scripts/destroy.sh", "--env-name", "unit", "--yes", "--no-color"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("Fabric cleanup failed", result.stdout)
            self.assertTrue(marker.exists())
            self.assertIn("down --purge --force", marker.read_text(encoding="utf-8"))

    def test_deploy_failure_prints_cleanup_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir)

            write_executable(
                bin_dir / "azd",
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"version\" ]]; then echo 'azd fake'; exit 0; fi\n"
                "if [[ \"$1\" == \"env\" && \"$2\" == \"select\" ]]; then exit 0; fi\n"
                "if [[ \"$1\" == \"env\" && \"$2\" == \"get-values\" ]]; then echo 'AZURE_ENV_NAME=\"unit\"'; exit 0; fi\n"
                "if [[ \"$1\" == \"env\" && \"$2\" == \"set\" ]]; then echo 'fake azd env set failure' >&2; exit 9; fi\n"
                "exit 0\n",
            )
            write_executable(
                bin_dir / "az",
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"version\" ]]; then echo '{\"azure-cli\":\"fake\"}'; exit 0; fi\n"
                "if [[ \"$1\" == \"account\" && \"$2\" == \"show\" ]]; then\n"
                "  if [[ \"$*\" == *'-o tsv'* ]]; then echo 'sub-id'; else echo '{\"name\":\"fake\",\"id\":\"sub-id\",\"tenantId\":\"tenant-id\"}'; fi\n"
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
            )
            write_executable(bin_dir / "node", "#!/usr/bin/env bash\necho 'v24.0.0'\n")
            write_executable(bin_dir / "npm", "#!/usr/bin/env bash\necho '11.0.0'\n")
            write_executable(bin_dir / "python3", "#!/usr/bin/env bash\nexec /usr/bin/env python3 \"$@\"\n")

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                [
                    "bash",
                    "scripts/deploy.sh",
                    "--mode",
                    "mcp-only",
                    "--env-name",
                    "unit",
                    "--location",
                    "eastus",
                    "--skip-app-build",
                    "--skip-dry-run",
                    "--no-color",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("A partial deployment may remain. To clean up:", result.stdout)
            self.assertIn("bash scripts/destroy.sh --env-name unit --yes", result.stdout)
            self.assertIn("azd down --purge --force", result.stdout)
            self.assertIn("python3 scripts/fabric-destroy.py --env-name unit --yes", result.stdout)


if __name__ == "__main__":
    unittest.main()
