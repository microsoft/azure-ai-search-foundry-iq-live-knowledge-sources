import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import cli, runtime as liveks_runtime  # noqa: E402
from liveks.config import resolve_config  # noqa: E402
from liveks.runtime import CommandResult  # noqa: E402


def load_fabric_provision_module():
    path = ROOT / "scripts/fabric-provision.py"
    spec = importlib.util.spec_from_file_location("fabric_provision_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


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

    def test_liveks_http_json_closes_transient_error_before_retry(self):
        http_error = urllib.error.HTTPError(
            "https://example.test",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"retry": true}'),
        )
        with (
            mock.patch.object(liveks_runtime.urllib.request, "urlopen", side_effect=[http_error, FakeHttpResponse()]),
            mock.patch.object(liveks_runtime.time, "sleep") as sleep,
        ):
            status, payload = liveks_runtime.http_json("https://example.test", attempts=2, delay_seconds=1)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})
        self.assertTrue(http_error.fp.closed)
        sleep.assert_called_once_with(1)

    def test_onelake_request_retries_metadata_eventual_consistency(self):
        module = load_fabric_provision_module()
        detail = b'{"error":{"message":"Couldn\'t find one lake details for the workspace."}}'
        http_error = urllib.error.HTTPError("https://example.test", 400, "Bad Request", {}, io.BytesIO(detail))
        with (
            mock.patch.object(module.urllib.request, "urlopen", side_effect=[http_error, FakeHttpResponse()]) as urlopen,
            mock.patch.object(module.time, "sleep") as sleep,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            module.onelake_request("PUT", "https://example.test", "token", attempts=2, delay_seconds=1)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_stale_capacity_id_does_not_bypass_live_lookup(self):
        module = load_fabric_provision_module()
        settings = {
            "FABRIC_CAPACITY_MODE": "create",
            "FABRIC_CAPACITY_ID": "stale-id",
            "FABRIC_CAPACITY_NAME": "fabunit",
            "FABRIC_CAPACITY_ARM_ID": "",
        }
        with (
            mock.patch.object(module, "capacity_by_name_with_retry", return_value=None),
            mock.patch.object(module, "create_arm_capacity", return_value="arm-id") as create,
            mock.patch.object(
                module,
                "capacity_by_name",
                return_value={"id": "current-id", "displayName": "fabunit", "state": "Active"},
            ),
        ):
            capacity_id, capacity = module.ensure_capacity(settings, "token", dry_run=False)
        self.assertEqual(capacity_id, "current-id")
        self.assertTrue(capacity["created"])
        create.assert_called_once()

    def test_previous_summary_retains_created_ownership_only_for_same_id(self):
        module = load_fabric_provision_module()
        previous = {"workspaceCreated": True, "workspaceId": "owned-id"}
        self.assertTrue(module.retain_created_ownership(previous, "workspace", "owned-id", False))
        self.assertFalse(module.retain_created_ownership(previous, "workspace", "different-id", False))

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
                    return_value=("capacity-guid", {"displayName": "fabunit", "id": "capacity-guid", "state": "Active", "created": True, "armId": arm_id}),
                ),
                mock.patch.object(module, "ensure_workspace", side_effect=RuntimeError("workspace boom")),
            ):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(RuntimeError):
                        module.main()
            summary = json.loads((deployments_dir / "unit" / "fabric-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "failed")
            self.assertTrue(summary["capacityCreated"])
            self.assertIn("workspace boom", summary["error"])


class FakeCleanupRunner:
    history = []

    def __init__(self, *, root, env, quiet=False):
        self.__class__.history = []

    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        self.__class__.history.append(args)
        output = "false\n" if args[:3] == ["az", "group", "exists"] else "ok\n"
        return CommandResult(args, 0, output)


class EventuallyAbsentCleanupRunner(FakeCleanupRunner):
    probes = 0

    def __init__(self, *, root, env, quiet=False):
        super().__init__(root=root, env=env, quiet=quiet)
        self.__class__.probes = 0

    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        self.__class__.history.append(args)
        if args[:3] == ["az", "group", "exists"]:
            self.__class__.probes += 1
            return CommandResult(args, 0, "true\n" if self.__class__.probes < 3 else "false\n")
        return CommandResult(args, 0, "ok\n")


class OwnedResidualCleanupRunner(FakeCleanupRunner):
    deleted = False

    def __init__(self, *, root, env, quiet=False):
        super().__init__(root=root, env=env, quiet=quiet)
        self.__class__.deleted = False

    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        self.__class__.history.append(args)
        if args[:3] == ["az", "group", "exists"]:
            return CommandResult(args, 0, "false\n" if self.__class__.deleted else "true\n")
        if args[:3] == ["az", "group", "delete"]:
            self.__class__.deleted = True
        return CommandResult(args, 0, "ok\n")


class CleanupOwnershipTests(unittest.TestCase):
    def test_cleanup_deletes_residual_group_only_when_lock_records_it_as_new(self):
        config = resolve_config(profile="mcp-only", environment="unit-owned-residual")
        lock = {
            "environment": config.environment,
            "profile": config.profile,
            "ownership": config.ownership(),
            "resourceGroupPreexisting": False,
        }
        config.lock_path.parent.mkdir(parents=True, exist_ok=True)
        config.lock_path.write_text(json.dumps(lock), encoding="utf-8")
        self.addCleanup(config.lock_path.unlink, missing_ok=True)
        with (
            mock.patch.object(cli, "CommandRunner", OwnedResidualCleanupRunner),
            mock.patch.object(cli, "write_lock"),
            mock.patch.object(cli.time, "sleep"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        commands = [" ".join(command) for command in OwnedResidualCleanupRunner.history]
        self.assertEqual(report["status"], "pass")
        self.assertTrue(any("az group delete" in command for command in commands))

    def test_cleanup_waits_for_resource_group_deletion(self):
        config = resolve_config(profile="mcp-only", environment="unit-eventual-cleanup")
        with (
            mock.patch.object(cli, "CommandRunner", EventuallyAbsentCleanupRunner),
            mock.patch.object(cli, "write_lock"),
            mock.patch.object(cli.time, "sleep") as sleep,
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(EventuallyAbsentCleanupRunner.probes, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_byo_cleanup_does_not_call_fabric_destroy(self):
        config = resolve_config(
            profile="byo-fabric",
            environment="unit-byo",
            overrides={
                "fabric.workspace_id": "11111111-1111-1111-1111-111111111111",
                "fabric.ontology_id": "22222222-2222-2222-2222-222222222222",
            },
        )
        with mock.patch.object(cli, "CommandRunner", FakeCleanupRunner), mock.patch.object(cli, "write_lock"):
            report = cli.down_report(config, yes=True, quiet=True)
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        self.assertEqual(report["status"], "pass")
        self.assertFalse(any("fabric-destroy.py" in command for command in commands))
        self.assertTrue(any("azd down" in command for command in commands))

    def test_full_cleanup_calls_fabric_destroy_before_azd_down(self):
        config = resolve_config(profile="full", environment="unit-full")
        with mock.patch.object(cli, "CommandRunner", FakeCleanupRunner), mock.patch.object(cli, "write_lock"):
            report = cli.down_report(config, yes=True, quiet=True)
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        fabric_index = next(index for index, command in enumerate(commands) if "fabric-destroy.py" in command)
        azure_index = next(index for index, command in enumerate(commands) if "azd down" in command)
        self.assertLess(fabric_index, azure_index)
        self.assertEqual(report["status"], "pass")

    def test_lock_disagreement_preserves_fabric(self):
        config = resolve_config(profile="full", environment="unit-lock-safety")
        lock = {
            "environment": "unit-lock-safety",
            "profile": "full",
            "ownership": {
                "azure": "create",
                "fabricCapacity": "reuse",
                "fabricWorkspace": "reuse",
                "fabricOntology": "reuse",
            },
        }
        config.lock_path.parent.mkdir(parents=True, exist_ok=True)
        config.lock_path.write_text(json.dumps(lock), encoding="utf-8")
        self.addCleanup(config.lock_path.unlink, missing_ok=True)
        with mock.patch.object(cli, "CommandRunner", FakeCleanupRunner), mock.patch.object(cli, "write_lock"):
            report = cli.down_report(config, yes=True, quiet=True)
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        self.assertEqual(report["status"], "pass")
        self.assertFalse(any("fabric-destroy.py" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
