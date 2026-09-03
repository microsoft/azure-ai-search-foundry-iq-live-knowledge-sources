from __future__ import annotations

import io
import json
import socket
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import cli, mcp_client, runtime  # noqa: E402


MCP_ENDPOINT = (
    "https://unit-search.search.windows.net/knowledgebases/unit-kb/mcp"
    "?api-version=2026-05-01-preview"
)


def consumer_environment(**overrides: str) -> dict[str, str]:
    values = {
        "AZURE_SEARCH_MCP_ENDPOINT": MCP_ENDPOINT,
        "AZURE_SEARCH_MCP_AUTH_MODE": "bearer",
        "AZURE_SEARCH_MCP_BEARER_TOKEN": "secret-bearer-token",
        "AZURE_SEARCH_MCP_QUERY": "Which synthetic carrier has the highest exposure?",
        "AZURE_SEARCH_MCP_EXPECT_TERM": "Alpine Air",
    }
    values.update(overrides)
    return values


def successful_responses(text: str = "Alpine Air has the highest synthetic exposure."):
    return [
        (
            200,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {"name": "knowledge_base_retrieve"},
                        {"name": "unrelated_tool"},
                    ]
                },
            },
        ),
        (
            200,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": text}]},
            },
        ),
    ]


class FakeResponse:
    def __init__(self, raw: str, *, content_type: str = "application/json"):
        self.status = 200
        self.headers = {"Content-Type": content_type}
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.raw.encode("utf-8")


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        MCP_ENDPOINT,
        status,
        "private error",
        {},
        io.BytesIO(b'{"error":{"message":"private response"}}'),
    )


class IndependentMcpConsumerTests(unittest.TestCase):
    def test_json_and_sse_success_emit_the_same_sanitized_contract(self):
        list_payload, call_payload = [payload for _, payload in successful_responses()]
        with mock.patch.object(
            runtime.urllib.request,
            "urlopen",
            side_effect=[
                FakeResponse(json.dumps(list_payload)),
                FakeResponse(
                    f"event: message\ndata: {json.dumps(call_payload)}\n\n",
                    content_type="text/event-stream",
                ),
            ],
        ):
            report = mcp_client.run_from_environment(
                consumer_environment(),
                request=runtime.http_mcp_json,
            )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            [check["status"] for check in report["checks"]],
            ["pass"] * 6,
        )
        self.assertEqual(report["checks"][2]["toolCount"], 2)
        self.assertEqual(report["checks"][4]["contentBlockCount"], 1)
        self.assertEqual(report["checks"][5]["matchedExpectedTermCount"], 1)
        self.assertEqual(report["mode"]["responseFormats"], ["json", "sse"])

    def test_bearer_and_admin_key_modes_use_supported_headers_and_request_shapes(self):
        cases = [
            (
                consumer_environment(),
                "Authorization",
                "Bearer secret-bearer-token",
            ),
            (
                consumer_environment(
                    AZURE_SEARCH_MCP_AUTH_MODE="admin-key",
                    AZURE_SEARCH_MCP_BEARER_TOKEN="",
                    AZURE_SEARCH_ADMIN_KEY="secret-admin-key",
                ),
                "api-key",
                "secret-admin-key",
            ),
        ]
        for environ, header_name, header_value in cases:
            with self.subTest(header_name=header_name):
                request = mock.Mock(side_effect=successful_responses())

                report = mcp_client.run_from_environment(
                    environ,
                    request=request,
                )

                self.assertEqual(report["status"], "pass")
                list_call, tool_call = request.call_args_list
                self.assertEqual(
                    list_call.kwargs["body"],
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                    },
                )
                self.assertEqual(
                    tool_call.kwargs["body"],
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "knowledge_base_retrieve",
                            "arguments": {
                                "queries": [
                                    "Which synthetic carrier has the highest exposure?"
                                ]
                            },
                        },
                    },
                )
                self.assertEqual(
                    list_call.kwargs["headers"][header_name],
                    header_value,
                )
                self.assertEqual(list_call.kwargs["retry_mode"], "read")
                self.assertEqual(list_call.kwargs["attempts"], 3)

    def test_source_authorization_is_transient_and_count_only(self):
        request = mock.Mock(side_effect=successful_responses())
        report = mcp_client.run_from_environment(
            consumer_environment(
                AZURE_SEARCH_MCP_SOURCE_AUTHORIZATION="secret-source-token"
            ),
            request=request,
        )

        self.assertEqual(
            request.call_args_list[0].kwargs["headers"][
                "x-ms-query-source-authorization"
            ],
            "secret-source-token",
        )
        self.assertEqual(report["mode"]["sourceAuthorization"], "present")
        self.assertEqual(report["checks"][1]["headerCount"], 2)

    def test_expected_term_mismatch_is_a_content_failure(self):
        report = mcp_client.run_from_environment(
            consumer_environment(),
            request=mock.Mock(
                side_effect=successful_responses("A fluent but unverified answer.")
            ),
        )

        grounding = report["checks"][5]
        self.assertEqual(report["status"], "fail")
        self.assertEqual(grounding["status"], "fail")
        self.assertEqual(grounding["errorCategory"], "expected-term-mismatch")
        self.assertEqual(grounding["matchedExpectedTermCount"], 0)
        self.assertEqual(mcp_client.exit_code(report), 1)

    def test_missing_expected_term_fails_before_network(self):
        request = mock.Mock()
        report = mcp_client.run_from_environment(
            consumer_environment(AZURE_SEARCH_MCP_EXPECT_TERM=""),
            request=request,
        )

        self.assertEqual(report["status"], "fail")
        self.assertEqual(
            report["checks"][0]["errorCategory"],
            "missing-configuration",
        )
        self.assertEqual(mcp_client.exit_code(report), 2)
        request.assert_not_called()

    def test_configuration_rejects_unsafe_or_drifted_endpoints(self):
        cases = [
            ("http://unit-search.search.windows.net/mcp", "invalid-endpoint"),
            (
                "https://example.test/knowledgebases/unit-kb/mcp"
                "?api-version=2026-05-01-preview",
                "invalid-endpoint",
            ),
            (
                "https://unit-search.search.windows.net/knowledgebases/unit-kb/mcp"
                "?api-version=2026-08-01-preview",
                "unsupported-api-version",
            ),
        ]
        for endpoint, category in cases:
            with self.subTest(category=category):
                report = mcp_client.run_from_environment(
                    consumer_environment(AZURE_SEARCH_MCP_ENDPOINT=endpoint),
                    request=mock.Mock(),
                )
                self.assertEqual(
                    report["checks"][0]["errorCategory"],
                    category,
                )

    def test_missing_tool_tool_error_and_missing_text_are_normalized(self):
        cases = [
            (
                [
                    (200, {"result": {"tools": [{"name": "other"}]}}),
                ],
                "tools-list",
                "missing-tool",
            ),
            (
                [
                    successful_responses()[0],
                    (
                        200,
                        {
                            "result": {
                                "isError": True,
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "private source failure",
                                    }
                                ],
                            }
                        },
                    ),
                ],
                "tools-call",
                "tool-call-error",
            ),
            (
                [
                    successful_responses()[0],
                    (200, {"result": {"content": []}}),
                ],
                "text-content",
                "missing-text-content",
            ),
        ]
        for responses, check_name, category in cases:
            with self.subTest(category=category):
                report = mcp_client.run_from_environment(
                    consumer_environment(),
                    request=mock.Mock(side_effect=responses),
                )
                check = next(
                    item for item in report["checks"] if item["name"] == check_name
                )
                self.assertEqual(check["status"], "fail")
                self.assertEqual(check["errorCategory"], category)

    def test_http_and_protocol_failures_have_stable_categories(self):
        cases = [
            (401, {}, "authentication-rejected"),
            (403, {}, "authentication-rejected"),
            (404, {}, "endpoint-not-found"),
            (429, {}, "throttling-exhausted"),
            (503, {}, "service-error"),
            (200, {"error": {"message": "private"}}, "json-rpc-error"),
        ]
        for status, payload, category in cases:
            with self.subTest(status=status, category=category):
                report = mcp_client.run_from_environment(
                    consumer_environment(),
                    request=mock.Mock(return_value=(status, payload)),
                )
                self.assertEqual(
                    report["checks"][2]["errorCategory"],
                    category,
                )

    def test_malformed_response_and_network_error_are_redacted(self):
        private_error = (
            "https://private.example/"
            "11111111-1111-1111-1111-111111111111/secret-token"
        )
        for error, category in [
            (ValueError(private_error), "malformed-response"),
            (RuntimeError(private_error), "network-error"),
        ]:
            with self.subTest(category=category):
                report = mcp_client.run_from_environment(
                    consumer_environment(),
                    request=mock.Mock(side_effect=error),
                )
                serialized = json.dumps(report)
                self.assertEqual(
                    report["checks"][2]["errorCategory"],
                    category,
                )
                self.assertNotIn(private_error, serialized)
                self.assertNotIn("11111111-1111-1111-1111-111111111111", serialized)
                self.assertNotIn("secret-token", serialized)

    def test_public_report_omits_inputs_credentials_content_and_source_identity(self):
        secret_values = [
            MCP_ENDPOINT,
            "secret-bearer-token",
            "secret-source-token",
            "Which synthetic carrier has the highest exposure?",
            "Alpine Air",
            "private source identity",
        ]
        report = mcp_client.run_from_environment(
            consumer_environment(
                AZURE_SEARCH_MCP_SOURCE_AUTHORIZATION="secret-source-token"
            ),
            request=mock.Mock(
                side_effect=successful_responses(
                    "Alpine Air from private source identity and secret-bearer-token"
                )
            ),
        )
        serialized = json.dumps(report, sort_keys=True)

        self.assertEqual(report["status"], "pass")
        for secret in secret_values:
            self.assertNotIn(secret, serialized)
        self.assertEqual(
            set(report),
            {"schemaVersion", "command", "status", "mode", "checks"},
        )

    def test_main_has_deterministic_json_and_text_exit_contracts(self):
        with redirect_stdout(io.StringIO()) as output:
            passing = mcp_client.main(
                ["--format", "json"],
                environ=consumer_environment(),
                request=mock.Mock(side_effect=successful_responses()),
            )
        self.assertEqual(passing, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "pass")

        with redirect_stdout(io.StringIO()) as output:
            configuration_failure = mcp_client.main(
                ["--format", "text"],
                environ={},
                request=mock.Mock(),
            )
        self.assertEqual(configuration_failure, 2)
        self.assertIn("MCP consumer: FAIL", output.getvalue())
        self.assertNotIn("AZURE_SEARCH", output.getvalue())

    def test_liveks_mcp_uses_the_same_protocol_request_contract(self):
        query = "synthetic query"

        self.assertIs(cli.tools_list_request, mcp_client.tools_list_request)
        self.assertIs(cli.tools_call_request, mcp_client.tools_call_request)
        self.assertEqual(
            cli.tools_list_request(),
            mcp_client.tools_list_request(),
        )
        self.assertEqual(
            cli.tools_call_request(query),
            mcp_client.tools_call_request(query),
        )
        self.assertEqual(
            cli._mcp_text_blocks(successful_responses()[1][1]),
            ["Alpine Air has the highest synthetic exposure."],
        )


class IndependentMcpRetryTests(unittest.TestCase):
    def setUp(self):
        runtime.reset_retry_telemetry()

    def test_transient_mcp_failure_retries_and_recovers(self):
        list_payload = successful_responses()[0][1]
        with (
            mock.patch.object(
                runtime.urllib.request,
                "urlopen",
                side_effect=[
                    http_error(429),
                    FakeResponse(json.dumps(list_payload)),
                ],
            ) as urlopen,
            mock.patch.object(runtime.time, "sleep"),
        ):
            status, payload = runtime.http_mcp_json(
                MCP_ENDPOINT,
                body=mcp_client.tools_list_request(),
                attempts=3,
                delay_seconds=0,
                retry_mode="read",
            )

        self.assertEqual(status, 200)
        self.assertTrue(mcp_client.mcp_has_tool(payload))
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(runtime.retry_telemetry_summary()["retryCount"], 1)

    def test_authentication_failure_is_not_retried(self):
        with (
            mock.patch.object(
                runtime.urllib.request,
                "urlopen",
                side_effect=http_error(401),
            ) as urlopen,
            mock.patch.object(runtime.time, "sleep") as sleep,
        ):
            status, _ = runtime.http_mcp_json(
                MCP_ENDPOINT,
                body=mcp_client.tools_list_request(),
                attempts=3,
                retry_mode="read",
            )

        self.assertEqual(status, 401)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_timeout_retry_exhaustion_is_normalized(self):
        with (
            mock.patch.object(
                runtime.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError(socket.timeout("private timeout")),
            ),
            mock.patch.object(runtime.time, "sleep"),
        ):
            report = mcp_client.run_from_environment(
                consumer_environment(),
                request=runtime.http_mcp_json,
            )

        self.assertEqual(
            report["checks"][2]["errorCategory"],
            "network-timeout-exhausted",
        )


if __name__ == "__main__":
    unittest.main()
