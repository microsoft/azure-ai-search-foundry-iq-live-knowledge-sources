import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import cli  # noqa: E402
from liveks.config import resolve_config  # noqa: E402
from liveks.runtime import CommandResult, parse_json_or_sse  # noqa: E402


class McpRunner:
    def __init__(self, *, root, env, quiet=False):
        self.root = root
        self.env = env
        self.quiet = quiet

    def run(self, command, **kwargs):
        args = [str(item) for item in command]
        if args[:4] == ["azd", "env", "get-values"]:
            output = (
                'AZURE_RESOURCE_GROUP="rg-unit-mcp"\n'
                'AZURE_SEARCH_ENDPOINT="https://unit-search.search.windows.net"\n'
                'AZURE_SEARCH_SERVICE_NAME="unit-search"\n'
                'AZURE_SEARCH_API_VERSION="2026-05-01-preview"\n'
                'FABRIC_ONLY_KNOWLEDGE_BASE_NAME="unit-fabric-kb"\n'
                'KNOWLEDGE_BASE_NAME="unit-kb"\n'
            )
            return CommandResult(args, 0, output)
        if "admin-key" in args:
            return CommandResult(args, 0, "super-secret-key\n")
        if "get-access-token" in args:
            return CommandResult(args, 0, "super-secret-token\n")
        return CommandResult(args, 0, "")


class McpInvocationTests(unittest.TestCase):
    def test_json_and_sse_payloads_parse_to_same_shape(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        raw = json.dumps(payload)
        self.assertEqual(parse_json_or_sse(raw, "application/json"), payload)
        self.assertEqual(parse_json_or_sse(f"event: message\ndata: {raw}\n\n", "text/event-stream"), payload)

    def test_mcp_report_records_only_sanitized_counts(self):
        config = resolve_config(profile="full", environment="unit-mcp")
        responses = [
            (
                200,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"tools": [{"name": "knowledge_base_retrieve"}]},
                },
            ),
            (
                200,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "Alpine Air is grounded in the ontology. super-secret-token",
                            }
                        ]
                    },
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)), mock.patch.object(
            cli, "CommandRunner", McpRunner
        ), mock.patch.object(cli, "http_mcp_json", side_effect=responses):
            report = cli.mcp_report(config, expected_terms=["Alpine Air"])
            persisted = (Path(temp_dir) / "deployments/unit-mcp/mcp-call-report.json").read_text(encoding="utf-8")

        self.assertEqual(report["status"], "pass")
        self.assertIn("matched 1/1 expected term", persisted)
        self.assertNotIn("super-secret", persisted)
        self.assertNotIn("Alpine Air", persisted)
        self.assertNotIn("unit-search.search.windows.net", persisted)

    def test_mcp_report_marks_content_unverified_without_expected_terms(self):
        config = resolve_config(profile="full", environment="unit-mcp")
        responses = [
            (200, {"result": {"tools": [{"name": "knowledge_base_retrieve"}]}}),
            (200, {"result": {"content": [{"type": "text", "text": "A fluent but unverified answer."}]}}),
        ]
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)), mock.patch.object(
            cli, "CommandRunner", McpRunner
        ), mock.patch.object(cli, "http_mcp_json", side_effect=responses):
            report = cli.mcp_report(config)

        grounding = next(check for check in report["checks"] if check["name"] == "grounding-content")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(grounding["status"], "warn")

    def test_expected_term_mismatch_fails_grounding_without_persisting_content(self):
        config = resolve_config(profile="full", environment="unit-mcp")
        responses = [
            (200, {"result": {"tools": [{"name": "knowledge_base_retrieve"}]}}),
            (200, {"result": {"content": [{"type": "text", "text": "A fluent but ungrounded answer."}]}}),
        ]
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)), mock.patch.object(
            cli, "CommandRunner", McpRunner
        ), mock.patch.object(cli, "http_mcp_json", side_effect=responses):
            report = cli.mcp_report(config, expected_terms=["Known ontology fact"])
            persisted = (Path(temp_dir) / "deployments/unit-mcp/mcp-call-report.json").read_text(encoding="utf-8")

        grounding = next(check for check in report["checks"] if check["name"] == "grounding-content")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(grounding["status"], "fail")
        self.assertNotIn("ungrounded", persisted)
        self.assertNotIn("Known ontology fact", persisted)

    def test_expected_failure_requires_protocol_or_tool_failure(self):
        config = resolve_config(profile="full", environment="unit-mcp")
        responses = [
            (200, {"result": {"tools": [{"name": "knowledge_base_retrieve"}]}}),
            (200, {"result": {"content": [{"type": "text", "text": "Ordinary content."}]}}),
        ]
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)), mock.patch.object(
            cli, "CommandRunner", McpRunner
        ), mock.patch.object(cli, "http_mcp_json", side_effect=responses):
            report = cli.mcp_report(config, expected_terms=["Missing"], expect_failure=True)

        self.assertEqual(report["status"], "fail")
        self.assertIn("expected a failure", report["checks"][-1]["message"])

    def test_tool_discovery_exception_is_normalized_even_when_failure_is_expected(self):
        config = resolve_config(profile="full", environment="unit-mcp")
        raw_error = "https://private-search.example/secret-token"
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)), mock.patch.object(
            cli, "CommandRunner", McpRunner
        ), mock.patch.object(cli, "http_mcp_json", side_effect=RuntimeError(raw_error)):
            report = cli.mcp_report(config, expect_failure=True)
            persisted = (Path(temp_dir) / "deployments/unit-mcp/mcp-call-report.json").read_text(encoding="utf-8")

        self.assertEqual(report["status"], "fail")
        self.assertIn("could not complete tool discovery", persisted)
        self.assertNotIn(raw_error, persisted)

    def test_expected_tool_failure_is_normalized_without_raw_error(self):
        config = resolve_config(profile="full", environment="unit-mcp")
        raw_error = "workspace 11111111-1111-1111-1111-111111111111 denied for super-secret-token"
        responses = [
            (
                200,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"tools": [{"name": "knowledge_base_retrieve"}]},
                },
            ),
            (
                200,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {"isError": True, "content": [{"type": "text", "text": raw_error}]},
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(cli, "ROOT", Path(temp_dir)), mock.patch.object(
            cli, "CommandRunner", McpRunner
        ), mock.patch.object(cli, "http_mcp_json", side_effect=responses):
            report = cli.mcp_report(config, omit_source_authorization=True, expect_failure=True)
            persisted = (Path(temp_dir) / "deployments/unit-mcp/mcp-call-report.json").read_text(encoding="utf-8")

        self.assertEqual(report["status"], "pass")
        self.assertIn("Expected failure reproduced", persisted)
        self.assertNotIn(raw_error, persisted)
        self.assertNotIn("11111111-1111-1111-1111-111111111111", persisted)


if __name__ == "__main__":
    unittest.main()
