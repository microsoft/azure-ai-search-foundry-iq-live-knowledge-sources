"""Process, environment, and HTTP helpers for the LiveKS CLI."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable


RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
MAX_HTTP_ATTEMPTS = 20


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str


@dataclass(frozen=True)
class RetryClassification:
    category: str
    retryable: bool


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0
    retry_after_cap_seconds: float = 30.0


@dataclass
class RetryTelemetry:
    retry_count: int = 0
    recovered_count: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    terminal_categories: dict[str, int] = field(default_factory=dict)

    def record_retry(self, category: str) -> None:
        self.retry_count += 1
        self.category_counts[category] = self.category_counts.get(category, 0) + 1

    def record_recovered(self) -> None:
        self.recovered_count += 1

    def record_terminal(self, category: str) -> None:
        self.terminal_categories[category] = self.terminal_categories.get(category, 0) + 1

    def summary(self) -> dict[str, Any]:
        return {
            "retryCount": self.retry_count,
            "recoveredCount": self.recovered_count,
            "categoryCounts": dict(sorted(self.category_counts.items())),
            "terminalCategories": dict(sorted(self.terminal_categories.items())),
        }


_RETRY_TELEMETRY = RetryTelemetry()


def reset_retry_telemetry() -> None:
    global _RETRY_TELEMETRY
    _RETRY_TELEMETRY = RetryTelemetry()


def retry_telemetry_summary() -> dict[str, Any]:
    return _RETRY_TELEMETRY.summary()


def classify_retry(
    *,
    status_code: int | None = None,
    error: BaseException | None = None,
) -> RetryClassification:
    if status_code is not None:
        return RetryClassification(
            category=f"http-{status_code}",
            retryable=status_code in RETRYABLE_HTTP_STATUSES,
        )
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return RetryClassification(category="network-timeout", retryable=True)
    return RetryClassification(category="network-error", retryable=False)


def retry_is_semantically_safe(
    method: str,
    retry_mode: str,
    headers: dict[str, str] | None = None,
) -> bool:
    normalized_method = method.upper()
    normalized_headers = {key.lower(): str(value) for key, value in (headers or {}).items()}
    if retry_mode == "none":
        return False
    if retry_mode == "auto":
        return normalized_method in {"GET", "HEAD", "OPTIONS"}
    if retry_mode == "read":
        return normalized_method in {"GET", "HEAD", "OPTIONS", "POST"}
    if retry_mode == "conditional-write":
        if normalized_method == "PUT":
            return normalized_headers.get("if-none-match") == "*" or bool(normalized_headers.get("if-match"))
        if normalized_method == "DELETE":
            return bool(normalized_headers.get("if-match"))
        return False
    raise ValueError(f"Unsupported retry mode: {retry_mode}")


def retry_after_seconds(
    headers: Any,
    *,
    cap_seconds: float,
    now: datetime | None = None,
) -> float | None:
    raw_value = headers.get("Retry-After") if headers is not None else None
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        seconds = max(0.0, (parsed - current).total_seconds())
    if seconds < 0:
        return None
    return min(seconds, cap_seconds)


def retry_delay_seconds(
    retry_index: int,
    headers: Any,
    policy: RetryPolicy,
) -> float:
    retry_after = retry_after_seconds(
        headers,
        cap_seconds=policy.retry_after_cap_seconds,
    )
    if retry_after is not None:
        return retry_after
    return min(
        policy.base_delay_seconds * (2**retry_index),
        policy.max_delay_seconds,
    )


def close_http_error(error: urllib.error.HTTPError) -> None:
    """Close HTTPError across Python versions, including fp-less test doubles."""
    try:
        error.close()
    except (AttributeError, KeyError):
        response = getattr(error, "fp", None)
        if response is not None:
            response.close()


class CommandRunner:
    def __init__(self, *, root: Path, env: dict[str, str], quiet: bool = False) -> None:
        self.root = root
        self.env = env
        self.quiet = quiet
        self.history: list[list[str]] = []

    def run(
        self,
        command: Iterable[str],
        *,
        check: bool = False,
        cwd: Path | None = None,
        timeout: int | None = None,
        sensitive_output: bool = False,
    ) -> CommandResult:
        args = [str(part) for part in command]
        self.history.append(args)
        result = subprocess.run(
            args,
            cwd=cwd or self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        if not self.quiet and not sensitive_output and result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        wrapped = CommandResult(args, result.returncode, result.stdout)
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout[-3000:]}")
        return wrapped


class EnvironmentOperationLock:
    """Serialize lifecycle commands that update one environment ownership ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "EnvironmentOperationLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.handle.close()
            self.handle = None
            raise RuntimeError("Another lifecycle operation is active for this environment.") from error
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def parse_version(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        return ()
    return tuple(int(part or 0) for part in match.groups())


def parse_azd_values(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in output.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        values[key] = str(value)
    return values


def http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 1,
    delay_seconds: float = 2,
    timeout: int = 30,
    retry_mode: str = "auto",
    retry_policy: RetryPolicy | None = None,
) -> tuple[int, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers.setdefault("Content-Type", "application/json")
    policy = retry_policy or RetryPolicy(
        max_attempts=min(max(1, attempts), MAX_HTTP_ATTEMPTS),
        base_delay_seconds=delay_seconds,
    )
    effective_attempts = min(max(1, attempts), max(1, policy.max_attempts), MAX_HTTP_ATTEMPTS)
    retry_safe = retry_is_semantically_safe(method, retry_mode, request_headers)
    retries_before = _RETRY_TELEMETRY.retry_count
    for attempt in range(effective_attempts):
        request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                if _RETRY_TELEMETRY.retry_count > retries_before:
                    _RETRY_TELEMETRY.record_recovered()
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            classification = classify_retry(status_code=error.code)
            can_retry = (
                classification.retryable
                and retry_safe
                and attempt < effective_attempts - 1
            )
            if can_retry:
                delay = retry_delay_seconds(attempt, error.headers, policy)
                close_http_error(error)
                _RETRY_TELEMETRY.record_retry(classification.category)
                time.sleep(delay)
                continue
            if classification.retryable:
                suffix = "exhausted" if retry_safe else "unsafe-not-retried"
                _RETRY_TELEMETRY.record_terminal(f"{classification.category}-{suffix}")
            try:
                raw = error.read().decode("utf-8", errors="replace")
            finally:
                close_http_error(error)
            try:
                return error.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return error.code, {"error": raw}
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            classification = classify_retry(error=error)
            can_retry = (
                classification.retryable
                and retry_safe
                and attempt < effective_attempts - 1
            )
            if can_retry:
                _RETRY_TELEMETRY.record_retry(classification.category)
                time.sleep(retry_delay_seconds(attempt, None, policy))
                continue
            suffix = "exhausted" if classification.retryable and retry_safe else "non-retryable"
            _RETRY_TELEMETRY.record_terminal(f"{classification.category}-{suffix}")
            raise RuntimeError(
                f"Request failed with {classification.category} after {attempt + 1} attempt(s)."
            ) from error
    raise RuntimeError("Request failed without a terminal classification.")


def parse_json_or_sse(raw: str, content_type: str) -> Any:
    """Parse a JSON response or the first JSON data event from an SSE response."""
    if "text/event-stream" not in content_type.lower():
        return json.loads(raw) if raw else {}

    event_data: list[str] = []
    for line in raw.splitlines() + [""]:
        if line.startswith("data:"):
            event_data.append(line[5:].lstrip())
            continue
        if line or not event_data:
            continue
        payload = "\n".join(event_data)
        event_data = []
        if payload and payload != "[DONE]":
            return json.loads(payload)
    raise ValueError("MCP SSE response did not contain a JSON data event.")


def http_mcp_json(
    url: str,
    *,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
    attempts: int = 1,
    delay_seconds: float = 2,
    timeout: int = 120,
    retry_mode: str = "none",
    retry_policy: RetryPolicy | None = None,
) -> tuple[int, Any]:
    """POST one stateless MCP JSON-RPC request and accept JSON or SSE."""
    payload = json.dumps(body).encode("utf-8")
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        **(headers or {}),
    }
    policy = retry_policy or RetryPolicy(
        max_attempts=min(max(1, attempts), MAX_HTTP_ATTEMPTS),
        base_delay_seconds=delay_seconds,
    )
    effective_attempts = min(max(1, attempts), max(1, policy.max_attempts), MAX_HTTP_ATTEMPTS)
    retry_safe = retry_is_semantically_safe("POST", retry_mode, request_headers)
    retries_before = _RETRY_TELEMETRY.retry_count
    for attempt in range(effective_attempts):
        request = urllib.request.Request(url, data=payload, headers=request_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                content_type = response.headers.get("Content-Type", "application/json")
                if _RETRY_TELEMETRY.retry_count > retries_before:
                    _RETRY_TELEMETRY.record_recovered()
                return response.status, parse_json_or_sse(raw, content_type)
        except urllib.error.HTTPError as error:
            classification = classify_retry(status_code=error.code)
            can_retry = (
                classification.retryable
                and retry_safe
                and attempt < effective_attempts - 1
            )
            if can_retry:
                delay = retry_delay_seconds(attempt, error.headers, policy)
                close_http_error(error)
                _RETRY_TELEMETRY.record_retry(classification.category)
                time.sleep(delay)
                continue
            if classification.retryable:
                suffix = "exhausted" if retry_safe else "unsafe-not-retried"
                _RETRY_TELEMETRY.record_terminal(f"{classification.category}-{suffix}")
            try:
                raw = error.read().decode("utf-8", errors="replace")
                content_type = error.headers.get("Content-Type", "application/json") if error.headers else "application/json"
            finally:
                close_http_error(error)
            try:
                return error.code, parse_json_or_sse(raw, content_type)
            except (json.JSONDecodeError, ValueError):
                return error.code, {"error": "non-JSON MCP error response"}
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            classification = classify_retry(error=error)
            can_retry = (
                classification.retryable
                and retry_safe
                and attempt < effective_attempts - 1
            )
            if can_retry:
                _RETRY_TELEMETRY.record_retry(classification.category)
                time.sleep(retry_delay_seconds(attempt, None, policy))
                continue
            suffix = "exhausted" if classification.retryable and retry_safe else "non-retryable"
            _RETRY_TELEMETRY.record_terminal(f"{classification.category}-{suffix}")
            raise RuntimeError(
                f"MCP request failed with {classification.category} after {attempt + 1} attempt(s)."
            ) from error
    raise RuntimeError("MCP request failed without a terminal classification.")
