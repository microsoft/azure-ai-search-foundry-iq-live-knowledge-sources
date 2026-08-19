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


def load_fabric_destroy_module():
    path = ROOT / "scripts/fabric-destroy.py"
    spec = importlib.util.spec_from_file_location("fabric_destroy_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_postprovision_module():
    path = ROOT / "scripts/postprovision.py"
    spec = importlib.util.spec_from_file_location("postprovision_for_tests", path)
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
    def test_postprovision_rejects_incompatible_search_api_before_calls(self):
        module = load_postprovision_module()
        settings = {
            "DEPLOYMENT_MODE": "mcp-only",
            "AZURE_SEARCH_API_VERSION": "2026-04-01",
        }
        with self.assertRaisesRegex(SystemExit, "2026-05-01-preview"):
            module.validate_mode_settings(settings)

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
            mock.patch.object(
                module,
                "create_arm_capacity",
                return_value={"armId": "arm-id", "resourceGroupCreated": True},
            ) as create,
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

    def test_create_mode_refuses_existing_capacity_without_environment_ownership(self):
        module = load_fabric_provision_module()
        settings = {
            "FABRIC_CAPACITY_MODE": "create",
            "FABRIC_CAPACITY_NAME": "fabshared",
        }
        with mock.patch.object(
            module,
            "capacity_by_name_with_retry",
            return_value={"id": "shared-id", "displayName": "fabshared"},
        ):
            with self.assertRaisesRegex(RuntimeError, "not owned by this environment"):
                module.ensure_capacity(settings, "token", dry_run=False)

    def test_create_mode_reuses_capacity_owned_by_same_environment(self):
        module = load_fabric_provision_module()
        settings = {
            "FABRIC_CAPACITY_MODE": "create",
            "FABRIC_CAPACITY_NAME": "fabunit",
            "FABRIC_CAPACITY_ARM_ID": "",
        }
        previous = {
            "capacityCreated": True,
            "capacityId": "owned-id",
            "capacityName": "fabunit",
            "capacityArmId": "arm-id",
            "capacityResourceGroupCreated": True,
        }
        with mock.patch.object(
            module,
            "capacity_by_name_with_retry",
            return_value={"id": "owned-id", "displayName": "fabunit"},
        ):
            capacity_id, capacity = module.ensure_capacity(
                settings,
                "token",
                dry_run=False,
                previous_summary=previous,
            )
        self.assertEqual(capacity_id, "owned-id")
        self.assertFalse(capacity["created"])
        self.assertTrue(capacity["owned"])
        self.assertTrue(capacity["resourceGroupCreated"])

    def test_create_mode_reuses_arm_journal_before_fabric_id_was_recorded(self):
        module = load_fabric_provision_module()
        arm_id = "/subscriptions/sub/resourceGroups/rg-unit-fabric/providers/Microsoft.Fabric/capacities/fabunit"
        settings = {
            "FABRIC_CAPACITY_MODE": "create",
            "FABRIC_CAPACITY_NAME": "fabunit",
            "FABRIC_CAPACITY_RESOURCE_GROUP": "rg-unit-fabric",
            "FABRIC_CAPACITY_ARM_ID": "",
        }
        previous = {
            "capacityCreated": True,
            "capacityId": "",
            "capacityName": "fabunit",
            "capacityArmId": arm_id,
            "capacityResourceGroup": "rg-unit-fabric",
            "capacityResourceGroupCreated": True,
        }
        with mock.patch.object(
            module,
            "capacity_by_name_with_retry",
            return_value={"id": "eventual-id", "displayName": "fabunit"},
        ):
            capacity_id, capacity = module.ensure_capacity(
                settings,
                "token",
                dry_run=False,
                previous_summary=previous,
            )
        self.assertEqual(capacity_id, "eventual-id")
        self.assertTrue(capacity["owned"])
        self.assertTrue(capacity["resourceGroupCreated"])

    def test_create_mode_refuses_unjournaled_arm_capacity(self):
        module = load_fabric_provision_module()
        settings = {
            "FABRIC_CAPACITY_MODE": "create",
            "FABRIC_CAPACITY_NAME": "fabunit",
            "FABRIC_CAPACITY_RESOURCE_GROUP": "rg-unit-fabric",
            "FABRIC_CAPACITY_ARM_ID": "/subscriptions/sub/resourceGroups/rg-unit-fabric/providers/Microsoft.Fabric/capacities/fabunit",
        }
        with (
            mock.patch.object(module, "capacity_by_name_with_retry", return_value=None),
            mock.patch.object(module, "wait_for_arm_capacity") as wait,
        ):
            with self.assertRaisesRegex(RuntimeError, "not proven as owned"):
                module.ensure_capacity(settings, "token", dry_run=False)
        wait.assert_not_called()

    def test_create_mode_accepts_exact_bicep_managed_capacity_during_propagation(self):
        module = load_fabric_provision_module()
        arm_id = "/subscriptions/sub/resourceGroups/rg-unit/providers/Microsoft.Fabric/capacities/fabunit"
        settings = {
            "AZURE_ENV_NAME": "unit",
            "FABRIC_CAPACITY_MODE": "create",
            "FABRIC_CAPACITY_NAME": "fabunit",
            "FABRIC_CAPACITY_RESOURCE_GROUP": "rg-unit",
            "FABRIC_CAPACITY_ARM_ID": arm_id,
        }
        resource = {
            "id": arm_id,
            "tags": {
                "azdEnvName": "unit",
                "solution": module.SOLUTION_TAG,
                "managedBy": module.BICEP_MANAGED_BY_TAG,
            },
        }
        with (
            mock.patch.object(module, "capacity_by_name_with_retry", return_value=None),
            mock.patch.object(module, "run", return_value=json.dumps(resource)),
            mock.patch.object(module, "wait_for_arm_capacity") as wait,
            mock.patch.object(
                module,
                "capacity_by_name",
                return_value={"id": "capacity-id", "displayName": "fabunit"},
            ),
        ):
            capacity_id, capacity = module.ensure_capacity(settings, "token", dry_run=False)
        self.assertEqual(capacity_id, "capacity-id")
        self.assertFalse(capacity["created"])
        self.assertTrue(capacity["owned"])
        self.assertIsNone(capacity["resourceGroupCreated"])
        wait.assert_called_once_with(arm_id)

    def test_arm_creation_records_tagged_ownership_before_readiness_wait(self):
        module = load_fabric_provision_module()
        settings = {
            "AZURE_ENV_NAME": "unit-full",
            "FABRIC_CAPACITY_RESOURCE_GROUP": "rg-unit-full-fabric",
            "FABRIC_LOCATION": "westus3",
            "FABRIC_CAPACITY_NAME": "fabunitfull",
            "FABRIC_CAPACITY_ADMIN": "admin@example.com",
            "FABRIC_CAPACITY_SKU": "F2",
        }
        arm_id = "/subscriptions/sub/resourceGroups/rg-unit-full-fabric/providers/Microsoft.Fabric/capacities/fabunitfull"
        ownership_callback = mock.Mock()
        with (
            mock.patch.object(module, "run", return_value="sub") as run,
            mock.patch.object(module, "resource_group_exists", return_value=False),
            mock.patch.object(
                module,
                "az_rest",
                side_effect=[{"nameAvailable": True}, {"id": arm_id}],
            ) as az_rest,
            mock.patch.object(module, "wait_for_arm_capacity", side_effect=RuntimeError("ARM wait timed out")),
        ):
            with self.assertRaisesRegex(RuntimeError, "ARM wait timed out"):
                module.create_arm_capacity(
                    settings,
                    dry_run=False,
                    on_ownership_update=ownership_callback,
                )
        self.assertEqual(
            ownership_callback.call_args_list,
            [
                mock.call(
                    {
                        "capacityId": "",
                        "capacityArmId": "",
                        "capacityName": "fabunitfull",
                        "capacityResourceGroup": "rg-unit-full-fabric",
                        "capacityResourceGroupCreated": True,
                        "capacityCreated": False,
                    }
                ),
                mock.call(
                    {
                        "capacityId": "",
                        "capacityArmId": arm_id,
                        "capacityName": "fabunitfull",
                        "capacityResourceGroup": "rg-unit-full-fabric",
                        "capacityResourceGroupCreated": True,
                        "capacityCreated": True,
                    }
                ),
            ],
        )
        create_body = az_rest.call_args_list[1].args[2]
        self.assertEqual(create_body["tags"]["azdEnvName"], "unit-full")
        self.assertEqual(create_body["tags"]["managedBy"], module.FABRIC_MANAGED_BY_TAG)
        group_create = next(call.args[0] for call in run.call_args_list if call.args[0][:3] == ["az", "group", "create"])
        self.assertIn("azdEnvName=unit-full", group_create)

    def test_arm_creation_journals_group_before_capacity_put_failure(self):
        module = load_fabric_provision_module()
        settings = {
            "AZURE_ENV_NAME": "unit-full",
            "FABRIC_CAPACITY_RESOURCE_GROUP": "rg-unit-full-fabric",
            "FABRIC_LOCATION": "westus3",
            "FABRIC_CAPACITY_NAME": "fabunitfull",
            "FABRIC_CAPACITY_ADMIN": "admin@example.com",
            "FABRIC_CAPACITY_SKU": "F2",
        }
        ownership_callback = mock.Mock()
        with (
            mock.patch.object(module, "run", return_value="sub"),
            mock.patch.object(module, "resource_group_exists", return_value=False),
            mock.patch.object(
                module,
                "az_rest",
                side_effect=[{"nameAvailable": True}, RuntimeError("capacity PUT failed")],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "capacity PUT failed"):
                module.create_arm_capacity(
                    settings,
                    dry_run=False,
                    on_ownership_update=ownership_callback,
                )
        ownership_callback.assert_called_once_with(
            {
                "capacityId": "",
                "capacityArmId": "",
                "capacityName": "fabunitfull",
                "capacityResourceGroup": "rg-unit-full-fabric",
                "capacityResourceGroupCreated": True,
                "capacityCreated": False,
            }
        )

    def test_provision_log_settings_redact_admin_and_runtime_ids(self):
        module = load_fabric_provision_module()
        logged = module.settings_for_log(
            {
                "FABRIC_CAPACITY_ADMIN": "admin@example.com",
                "FABRIC_WORKSPACE_ID": "workspace-id",
                "FABRIC_CAPACITY_NAME": "fabunit",
            }
        )
        self.assertEqual(logged["FABRIC_CAPACITY_ADMIN"], "<configured>")
        self.assertEqual(logged["FABRIC_WORKSPACE_ID"], "<configured>")
        self.assertEqual(logged["FABRIC_CAPACITY_NAME"], "fabunit")

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


class FabricDestroySafetyTests(unittest.TestCase):
    def test_verify_only_fails_when_cleanup_summary_is_missing(self):
        module = load_fabric_destroy_module()
        with (
            mock.patch.object(sys, "argv", ["fabric-destroy.py", "--env-name", "missing", "--verify-only"]),
            mock.patch.object(module, "load_azd_env", return_value={}),
            mock.patch.object(module, "load_summary", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "release cannot be verified"):
                module.main()

    def test_generated_capacity_group_delete_waits_for_completion(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityResourceGroup": "rg-unit-fabric",
            "capacityResourceGroupCreated": True,
        }
        resources = json.dumps(
            [
                {
                    "id": "/subscriptions/000/resourceGroups/rg-unit-fabric/providers/Microsoft.Fabric/capacities/fabunit",
                    "name": "fabunit",
                    "type": "Microsoft.Fabric/capacities",
                }
            ]
        )
        with (
            mock.patch.object(module, "resource_group_exists", return_value=True),
            mock.patch.object(module, "run", side_effect=[resources, "", ""]) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            deferred = module.delete_capacity_resource_group(summary, {"AZURE_RESOURCE_GROUP": "rg-unit-app"})
        self.assertFalse(deferred)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["az", "group", "delete", "--name", "rg-unit-fabric", "--yes", "--no-wait"], commands)
        self.assertIn(["az", "group", "wait", "--name", "rg-unit-fabric", "--deleted", "--timeout", "1800"], commands)

    def test_group_created_before_failed_capacity_put_is_deleted(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": False,
            "capacityName": "fabunit",
            "capacityResourceGroup": "rg-unit-fabric",
            "capacityResourceGroupCreated": True,
        }
        with (
            mock.patch.object(module, "resource_group_exists", return_value=True),
            mock.patch.object(module, "run", side_effect=["[]", "", ""]) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            deferred = module.delete_capacity_resource_group(summary, {"AZURE_RESOURCE_GROUP": "rg-unit-app"})
        self.assertFalse(deferred)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["az", "group", "delete", "--name", "rg-unit-fabric", "--yes", "--no-wait"], commands)

    def test_cleanup_preserves_group_with_other_resources_and_deletes_only_capacity(self):
        module = load_fabric_destroy_module()
        capacity_id = "/subscriptions/000/resourceGroups/rg-shared/providers/Microsoft.Fabric/capacities/fabunit"
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityArmId": capacity_id,
            "capacityResourceGroup": "rg-shared",
            "capacityResourceGroupCreated": True,
        }
        resources = json.dumps(
            [
                {"id": capacity_id, "name": "fabunit", "type": "Microsoft.Fabric/capacities"},
                {
                    "id": "/subscriptions/000/resourceGroups/rg-shared/providers/Microsoft.Storage/storageAccounts/shared",
                    "name": "shared",
                    "type": "Microsoft.Storage/storageAccounts",
                },
            ]
        )
        with (
            mock.patch.object(module, "resource_group_exists", return_value=True),
            mock.patch.object(module, "run", side_effect=[resources, ""]) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            deferred = module.delete_capacity_resource_group(summary, {"AZURE_RESOURCE_GROUP": "rg-app"})
        self.assertFalse(deferred)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["az", "resource", "delete", "--ids", capacity_id], commands)
        self.assertFalse(any(command[:3] == ["az", "group", "delete"] for command in commands))

    def test_cleanup_refuses_capacity_arm_identity_mismatch_before_group_delete(self):
        module = load_fabric_destroy_module()
        recorded_id = "/subscriptions/expected/resourceGroups/rg-unit/providers/Microsoft.Fabric/capacities/fabunit"
        discovered_id = "/subscriptions/other/resourceGroups/rg-unit/providers/Microsoft.Fabric/capacities/fabunit"
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityArmId": recorded_id,
            "capacityResourceGroup": "rg-unit",
            "capacityResourceGroupCreated": True,
        }
        resources = json.dumps(
            [{"id": discovered_id, "name": "fabunit", "type": "Microsoft.Fabric/capacities"}]
        )
        with (
            mock.patch.object(module, "resource_group_exists", return_value=True),
            mock.patch.object(module, "run", return_value=resources) as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                module.delete_capacity_resource_group(summary, {"AZURE_RESOURCE_GROUP": "rg-app"})
        commands = [call.args[0] for call in run.call_args_list]
        self.assertFalse(any(command[:3] == ["az", "group", "delete"] for command in commands))

    def test_full_cleanup_fails_closed_when_summary_is_missing(self):
        module = load_fabric_destroy_module()
        with (
            mock.patch.object(sys, "argv", ["fabric-destroy.py", "--env-name", "unit-full", "--yes"]),
            mock.patch.object(module, "load_azd_env", return_value={"DEPLOYMENT_MODE": "full"}),
            mock.patch.object(module, "load_summary", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "release cannot be verified"):
                module.main()

    def test_cleanup_verification_requires_generated_assets_to_be_absent(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityResourceGroup": "rg-unit-fabric",
            "capacityResourceGroupCreated": True,
            "workspaceCreated": True,
            "workspaceId": "workspace-id",
            "lakehouseCreated": True,
            "lakehouseId": "lakehouse-id",
            "ontologyCreated": True,
            "ontologyId": "ontology-id",
        }
        with (
            mock.patch.object(module, "wait_for_fabric_absent") as wait,
            mock.patch.object(module, "resource_group_exists", return_value=False),
            mock.patch.object(module, "wait_for_capacity_absent") as capacity_wait,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            module.verify_cleanup(summary, "token")
        self.assertEqual(wait.call_count, 3)
        capacity_wait.assert_called_once_with("fabunit", "rg-unit-fabric", "token")

    def test_cleanup_verification_fails_when_generated_capacity_remains(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityResourceGroup": "rg-unit-fabric",
            "capacityResourceGroupCreated": True,
        }
        with (
            mock.patch.object(module, "resource_group_exists", return_value=False),
            mock.patch.object(
                module,
                "wait_for_capacity_absent",
                side_effect=RuntimeError("Generated Fabric capacity still exists after cleanup: fabunit"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "capacity still exists"):
                module.verify_cleanup(summary, "token")

    def test_cleanup_verification_requires_preexisting_capacity_group_to_remain(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityResourceGroup": "rg-shared",
            "capacityResourceGroupCreated": False,
        }
        with (
            mock.patch.object(module, "resource_group_exists", return_value=True) as group_exists,
            mock.patch.object(module, "wait_for_capacity_absent") as capacity_wait,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            module.verify_cleanup(summary, "token")
        self.assertEqual(group_exists.call_count, 2)
        capacity_wait.assert_called_once_with("fabunit", "rg-shared", "token")

    def test_cleanup_verification_flags_unknown_capacity_group_ownership(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": True,
            "capacityName": "fabunit",
            "capacityResourceGroup": "rg-unknown",
        }
        with mock.patch.object(module, "wait_for_capacity_absent"):
            with self.assertRaisesRegex(RuntimeError, "ownership is missing"):
                module.verify_cleanup(summary, "token")

    def test_capacity_absence_waits_for_arm_and_fabric_inventories(self):
        module = load_fabric_destroy_module()
        with (
            mock.patch.object(module, "arm_capacity_exists", side_effect=[True, False]) as arm_exists,
            mock.patch.object(module, "fabric_capacity_exists", side_effect=[True, False]) as fabric_exists,
            mock.patch.object(module.time, "sleep") as sleep,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            module.wait_for_capacity_absent("fabunit", "rg-unit-fabric", "token")
        self.assertEqual(arm_exists.call_count, 2)
        self.assertEqual(fabric_exists.call_count, 2)
        sleep.assert_called_once_with(module.FABRIC_DELETE_DELAY_SECONDS)

    def test_cleanup_verification_preserves_reused_capacity(self):
        module = load_fabric_destroy_module()
        summary = {
            "capacityCreated": False,
            "capacityName": "fab-byo",
            "workspaceCreated": True,
            "workspaceId": "workspace-id",
        }
        with (
            mock.patch.object(module, "wait_for_fabric_absent") as wait,
            mock.patch.object(module, "resource_group_exists") as group_exists,
            mock.patch.object(module, "fabric_capacity_exists", return_value=True) as capacity_exists,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            module.verify_cleanup(summary, "token")
        wait.assert_called_once_with("/workspaces/workspace-id", "token", "workspace")
        group_exists.assert_not_called()
        capacity_exists.assert_called_once_with("fab-byo", "token")


class FakeCleanupRunner:
    history = []

    def __init__(self, *, root, env, quiet=False):
        self.__class__.history = []

    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        self.__class__.history.append(args)
        if args[:3] == ["az", "group", "exists"]:
            output = "false\n"
        elif args[:3] == ["az", "resource", "list"]:
            output = "[]\n"
        else:
            output = "ok\n"
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


class PreexistingCapacityGroupCleanupRunner(FakeCleanupRunner):
    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        self.__class__.history.append(args)
        if args[:3] == ["az", "group", "exists"]:
            group_name = args[args.index("--name") + 1]
            return CommandResult(args, 0, "true\n" if group_name == "rg-unit-full-shared" else "false\n")
        if args[:3] == ["az", "resource", "list"]:
            return CommandResult(args, 0, "[]\n")
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
        fabric_summary = {
            "capacityCreated": True,
            "capacityName": "fabunitfull",
            "capacityResourceGroup": "rg-unit-full-fabric",
            "capacityResourceGroupCreated": True,
        }
        with (
            mock.patch.object(cli, "CommandRunner", FakeCleanupRunner),
            mock.patch.object(cli, "_locked_identity", return_value=("full", config.ownership())),
            mock.patch.object(cli, "_load_fabric_summary", return_value=fabric_summary),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        fabric_index = next(index for index, command in enumerate(commands) if "fabric-destroy.py" in command)
        azure_index = next(index for index, command in enumerate(commands) if "azd down" in command)
        self.assertLess(fabric_index, azure_index)
        self.assertEqual(report["status"], "pass")
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["fabric-capacity-resource-group-absent"], "pass")
        self.assertEqual(checks["fabric-capacity-absent"], "pass")

    def test_full_cleanup_preserves_preexisting_capacity_group(self):
        config = resolve_config(profile="full", environment="unit-full-shared-group")
        fabric_summary = {
            "capacityCreated": True,
            "capacityName": "fabunitfull",
            "capacityResourceGroup": "rg-unit-full-shared",
            "capacityResourceGroupCreated": False,
        }
        with (
            mock.patch.object(cli, "CommandRunner", PreexistingCapacityGroupCleanupRunner),
            mock.patch.object(cli, "_locked_identity", return_value=("full", config.ownership())),
            mock.patch.object(cli, "_load_fabric_summary", return_value=fabric_summary),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(report["status"], "pass")
        self.assertEqual(checks["fabric-capacity-resource-group-preserved"], "pass")
        self.assertEqual(checks["fabric-capacity-absent"], "pass")

    def test_full_cleanup_releases_group_left_by_failed_capacity_put(self):
        config = resolve_config(profile="full", environment="unit-full-group-only")
        fabric_summary = {
            "capacityCreated": False,
            "capacityName": "fabunitfull",
            "capacityResourceGroup": "rg-unit-full-fabric",
            "capacityResourceGroupCreated": True,
        }
        with (
            mock.patch.object(cli, "CommandRunner", FakeCleanupRunner),
            mock.patch.object(cli, "_locked_identity", return_value=("full", config.ownership())),
            mock.patch.object(cli, "_load_fabric_summary", return_value=fabric_summary),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(report["status"], "pass")
        self.assertNotIn("fabric-capacity-ownership", checks)
        self.assertEqual(checks["fabric-capacity-resource-group-absent"], "pass")
        self.assertEqual(checks["fabric-capacity-absent"], "pass")

    def test_full_cleanup_preserves_reused_capacity_without_absence_claim(self):
        config = resolve_config(profile="full", environment="unit-full-reused-capacity")
        with (
            mock.patch.object(cli, "CommandRunner", FakeCleanupRunner),
            mock.patch.object(cli, "_locked_identity", return_value=("full", config.ownership())),
            mock.patch.object(cli, "_load_fabric_summary", return_value={"capacityCreated": False}),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        check_names = {check["name"] for check in report["checks"]}
        self.assertEqual(report["status"], "partial")
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["fabric-capacity-ownership"], "warn")
        self.assertNotIn("fabric-capacity-resource-group-absent", check_names)
        self.assertNotIn("fabric-capacity-absent", check_names)

    def test_full_cleanup_with_missing_summary_is_partial_but_continues_azure_cleanup(self):
        config = resolve_config(profile="full", environment="unit-full-missing-summary")
        with (
            mock.patch.object(cli, "CommandRunner", FakeCleanupRunner),
            mock.patch.object(cli, "_locked_identity", return_value=("full", config.ownership())),
            mock.patch.object(cli, "_load_fabric_summary", return_value=None),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        checks = {check["name"]: check["status"] for check in report["checks"]}
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        self.assertEqual(report["status"], "partial")
        self.assertEqual(checks["fabric-summary"], "warn")
        self.assertTrue(any("azd down" in command for command in commands))

    def test_full_cleanup_with_unknown_capacity_group_ownership_is_partial(self):
        config = resolve_config(profile="full", environment="unit-full-unknown-group")
        fabric_summary = {
            "capacityCreated": True,
            "capacityName": "fabunitfull",
            "capacityResourceGroup": "rg-unit-full-fabric",
        }
        with (
            mock.patch.object(cli, "CommandRunner", FakeCleanupRunner),
            mock.patch.object(cli, "_locked_identity", return_value=("full", config.ownership())),
            mock.patch.object(cli, "_load_fabric_summary", return_value=fabric_summary),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(report["status"], "partial")
        self.assertEqual(checks["fabric-capacity-resource-group-ownership"], "warn")

    def test_full_cleanup_without_lock_preserves_fabric_and_continues_azure_cleanup(self):
        config = resolve_config(profile="full", environment="unit-full-missing-lock")
        with (
            mock.patch.object(cli, "CommandRunner", FakeCleanupRunner),
            mock.patch.object(cli, "write_lock"),
        ):
            report = cli.down_report(config, yes=True, quiet=True)
        checks = {check["name"]: check["status"] for check in report["checks"]}
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        self.assertEqual(report["status"], "partial")
        self.assertEqual(checks["ownership"], "warn")
        self.assertFalse(any("fabric-destroy.py" in command for command in commands))
        self.assertTrue(any("azd down" in command for command in commands))

    def test_any_lock_disagreement_preserves_all_fabric(self):
        config = resolve_config(profile="full", environment="unit-lock-safety")
        lock = {
            "environment": "unit-lock-safety",
            "profile": "full",
            "ownership": {
                "azure": "create",
                "fabricCapacity": "reuse",
                "fabricWorkspace": "create",
                "fabricOntology": "create",
            },
        }
        config.lock_path.parent.mkdir(parents=True, exist_ok=True)
        config.lock_path.write_text(json.dumps(lock), encoding="utf-8")
        self.addCleanup(config.lock_path.unlink, missing_ok=True)
        with mock.patch.object(cli, "CommandRunner", FakeCleanupRunner), mock.patch.object(cli, "write_lock"):
            report = cli.down_report(config, yes=True, quiet=True)
        commands = [" ".join(command) for command in FakeCleanupRunner.history]
        self.assertEqual(report["status"], "partial")
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["ownership"], "warn")
        self.assertFalse(any("fabric-destroy.py" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
