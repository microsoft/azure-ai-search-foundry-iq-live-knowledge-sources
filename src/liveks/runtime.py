"""Process, environment, and HTTP helpers for the LiveKS CLI."""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str


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
) -> tuple[int, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers.setdefault("Content-Type", "application/json")
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code < 500 or attempt == attempts - 1:
                try:
                    raw = error.read().decode("utf-8", errors="replace")
                finally:
                    close_http_error(error)
                try:
                    return error.code, json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return error.code, {"error": raw}
            close_http_error(error)
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == attempts - 1:
                break
        time.sleep(delay_seconds)
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}: {last_error}")


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
) -> tuple[int, Any]:
    """POST one stateless MCP JSON-RPC request and accept JSON or SSE."""
    payload = json.dumps(body).encode("utf-8")
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        **(headers or {}),
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=payload, headers=request_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                content_type = response.headers.get("Content-Type", "application/json")
                return response.status, parse_json_or_sse(raw, content_type)
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code < 500 or attempt == attempts - 1:
                try:
                    raw = error.read().decode("utf-8", errors="replace")
                    content_type = error.headers.get("Content-Type", "application/json") if error.headers else "application/json"
                finally:
                    close_http_error(error)
                try:
                    return error.code, parse_json_or_sse(raw, content_type)
                except (json.JSONDecodeError, ValueError):
                    return error.code, {"error": "non-JSON MCP error response"}
            close_http_error(error)
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == attempts - 1:
                break
        time.sleep(delay_seconds)
    raise RuntimeError(f"MCP request failed after {attempts} attempts: {last_error}")
