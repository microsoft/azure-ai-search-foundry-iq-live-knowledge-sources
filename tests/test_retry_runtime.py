import io
import json
import socket
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import runtime  # noqa: E402


class FakeResponse:
    def __init__(self, payload=None, *, status=200, content_type="application/json"):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self.payload = payload if payload is not None else {"ok": True}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def http_error(status, *, retry_after=None):
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError(
        "https://private-search.example/secret",
        status,
        "error",
        headers,
        io.BytesIO(b'{"error":"private response"}'),
    )


class RetryClassificationTests(unittest.TestCase):
    def test_required_http_statuses_are_retryable(self):
        for status in (408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                classification = runtime.classify_retry(status_code=status)
                self.assertTrue(classification.retryable)
                self.assertEqual(classification.category, f"http-{status}")

    def test_deterministic_http_failures_are_not_retryable(self):
        for status in (400, 401, 403, 404, 409, 412, 422):
            with self.subTest(status=status):
                self.assertFalse(runtime.classify_retry(status_code=status).retryable)

    def test_only_explicit_read_or_conditional_write_modes_retry(self):
        self.assertTrue(runtime.retry_is_semantically_safe("GET", "auto"))
        self.assertFalse(runtime.retry_is_semantically_safe("POST", "auto"))
        self.assertTrue(runtime.retry_is_semantically_safe("POST", "read"))
        self.assertFalse(runtime.retry_is_semantically_safe("PUT", "conditional-write"))
        self.assertTrue(
            runtime.retry_is_semantically_safe(
                "PUT",
                "conditional-write",
                {"If-None-Match": "*"},
            )
        )
        self.assertTrue(
            runtime.retry_is_semantically_safe(
                "DELETE",
                "conditional-write",
                {"If-Match": "etag"},
            )
        )

    def test_retry_after_seconds_and_http_date_are_capped(self):
        self.assertEqual(
            runtime.retry_after_seconds(
                {"Retry-After": "120"},
                cap_seconds=30,
            ),
            30,
        )
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        retry_at = format_datetime(now + timedelta(seconds=9), usegmt=True)
        self.assertEqual(
            runtime.retry_after_seconds(
                {"Retry-After": retry_at},
                cap_seconds=30,
                now=now,
            ),
            9,
        )
        self.assertIsNone(
            runtime.retry_after_seconds(
                {"Retry-After": "not-valid"},
                cap_seconds=30,
            )
        )

    def test_exponential_backoff_has_a_hard_cap(self):
        policy = runtime.RetryPolicy(
            max_attempts=6,
            base_delay_seconds=2,
            max_delay_seconds=5,
            retry_after_cap_seconds=30,
        )
        self.assertEqual(
            [runtime.retry_delay_seconds(index, None, policy) for index in range(4)],
            [2, 4, 5, 5],
        )


class RetryExecutionTests(unittest.TestCase):
    def setUp(self):
        runtime.reset_retry_telemetry()

    def test_get_respects_retry_after_then_records_recovery(self):
        first = http_error(429, retry_after=3)
        with (
            mock.patch.object(runtime.urllib.request, "urlopen", side_effect=[first, FakeResponse()]) as urlopen,
            mock.patch.object(runtime.time, "sleep") as sleep,
        ):
            status, payload = runtime.http_json(
                "https://private-search.example",
                attempts=3,
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(3)
        self.assertEqual(
            runtime.retry_telemetry_summary(),
            {
                "retryCount": 1,
                "recoveredCount": 1,
                "categoryCounts": {"http-429": 1},
                "terminalCategories": {},
            },
        )

    def test_deterministic_4xx_is_returned_without_retry(self):
        failure = http_error(403)
        with (
            mock.patch.object(runtime.urllib.request, "urlopen", side_effect=failure) as urlopen,
            mock.patch.object(runtime.time, "sleep") as sleep,
        ):
            status, payload = runtime.http_json(
                "https://private-search.example",
                attempts=4,
            )

        self.assertEqual(status, 403)
        self.assertEqual(payload, {"error": "private response"})
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(runtime.retry_telemetry_summary()["retryCount"], 0)

    def test_unsafe_post_is_not_retried(self):
        failure = http_error(503)
        with (
            mock.patch.object(runtime.urllib.request, "urlopen", side_effect=failure) as urlopen,
            mock.patch.object(runtime.time, "sleep") as sleep,
        ):
            status, _ = runtime.http_json(
                "https://private-search.example",
                method="POST",
                body={"private": "payload"},
                attempts=4,
            )

        self.assertEqual(status, 503)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(
            runtime.retry_telemetry_summary()["terminalCategories"],
            {"http-503-unsafe-not-retried": 1},
        )

    def test_conditional_delete_can_retry(self):
        first = http_error(500)
        with (
            mock.patch.object(runtime.urllib.request, "urlopen", side_effect=[first, FakeResponse()]) as urlopen,
            mock.patch.object(runtime.time, "sleep"),
        ):
            status, _ = runtime.http_json(
                "https://private-search.example",
                method="DELETE",
                headers={"If-Match": "etag"},
                attempts=3,
                retry_mode="conditional-write",
            )

        self.assertEqual(status, 200)
        self.assertEqual(urlopen.call_count, 2)

    def test_timeout_retries_are_bounded_and_terminal_message_is_redacted(self):
        timeout = urllib.error.URLError(socket.timeout("private timeout"))
        policy = runtime.RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
            max_delay_seconds=0,
        )
        with (
            mock.patch.object(runtime.urllib.request, "urlopen", side_effect=timeout) as urlopen,
            mock.patch.object(runtime.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "network-timeout after 3 attempt"):
                runtime.http_json(
                    "https://private-search.example/secret",
                    attempts=25,
                    retry_policy=policy,
                )

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        summary = runtime.retry_telemetry_summary()
        self.assertEqual(summary["retryCount"], 2)
        self.assertEqual(
            summary["terminalCategories"],
            {"network-timeout-exhausted": 1},
        )

    def test_native_mcp_retry_requires_explicit_read_mode(self):
        first = http_error(502)
        response = FakeResponse(
            {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}},
        )
        with (
            mock.patch.object(runtime.urllib.request, "urlopen", side_effect=[first, response]) as urlopen,
            mock.patch.object(runtime.time, "sleep"),
        ):
            status, payload = runtime.http_mcp_json(
                "https://private-search.example/mcp",
                body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                attempts=3,
                retry_mode="read",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["result"]["tools"], [])
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
