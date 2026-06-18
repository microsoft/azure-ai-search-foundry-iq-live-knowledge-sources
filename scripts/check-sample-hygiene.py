#!/usr/bin/env python3
"""Check public-sample packaging hygiene.

This complements the no-secret scanner. It checks structural rules that make the
repo safer to promote: generated paths stay ignored, tracked files do not live in
local workbench folders, and .env.sample contains placeholders instead of local
tenant values.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
    "CODE_OF_CONDUCT.md",
    ".env.sample",
    "azure.yaml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/validate.yml",
)

REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "!.env.sample",
    "deployments/",
    ".deployment/",
    "scratch/",
    "*.local.md",
    "spec/",
    "planning/",
    "worklog/",
)

FORBIDDEN_TRACKED_PREFIXES = (
    ".deployment/",
    "deployments/",
    "scratch/",
    "_scratch/",
    "spec/",
    "specs/",
    "_spec/",
    "_specs/",
    "planning/",
    "_planning/",
    "worklog/",
    "worklogs/",
    "_worklog/",
    "_worklogs/",
)

FORBIDDEN_TRACKED_NAMES = (
    ".env",
    ".env.external.local",
    "deployment-summary.md",
)

PLACEHOLDER_KEYS = (
    "SEARCH_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "FABRIC_USER_SEARCH_TOKEN",
    "FABRIC_CAPACITY_NAME",
    "FABRIC_CAPACITY_ADMIN",
    "FABRIC_WORKSPACE_NAME",
)

ZERO_GUID_KEYS = (
    "FABRIC_WORKSPACE_ID",
    "FABRIC_ONTOLOGY_ID",
    "EXTERNAL_TENANT_ID",
)

EXPECTED_DEPLOYMENT_MODES = {"mcp-only", "byo-fabric", "full"}


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def parse_env_sample(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def is_placeholder(value: str) -> bool:
    return value.startswith("<") and value.endswith(">")


def is_zero_guid(value: str) -> bool:
    return bool(re.fullmatch(r"0{8}-0{4}-0{4}-0{4}-0{11}[0-9a-fA-F]", value))


def main() -> int:
    failures: list[str] = []
    tracked = git_ls_files()
    tracked_set = set(tracked)

    for file_path in REQUIRED_FILES:
        if file_path not in tracked_set:
            failures.append(f"required file is missing or untracked: {file_path}")

    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        failures.append(".gitignore is missing")
    else:
        gitignore_lines = {
            line.strip()
            for line in gitignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        for pattern in REQUIRED_GITIGNORE_PATTERNS:
            if pattern not in gitignore_lines:
                failures.append(f".gitignore missing required pattern: {pattern}")

    for file_path in tracked:
        path = Path(file_path)
        if file_path in FORBIDDEN_TRACKED_NAMES or path.name in FORBIDDEN_TRACKED_NAMES:
            failures.append(f"forbidden tracked file: {file_path}")
        if file_path.endswith(".local.md"):
            failures.append(f"local-only markdown should not be tracked: {file_path}")
        if any(file_path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES):
            failures.append(f"forbidden tracked workbench/generated path: {file_path}")

    env_path = Path(".env.sample")
    if env_path.exists():
        env = parse_env_sample(env_path)
        modes = {
            item.strip("# - ").split(":", 1)[0].strip()
            for item in env_path.read_text(encoding="utf-8").splitlines()
            if item.strip().startswith("# - ")
        }
        missing_modes = EXPECTED_DEPLOYMENT_MODES - modes
        if missing_modes:
            failures.append(".env.sample does not document deployment modes: " + ", ".join(sorted(missing_modes)))

        for key in PLACEHOLDER_KEYS:
            value = env.get(key, "")
            if value and not is_placeholder(value):
                failures.append(f".env.sample {key} should use an angle-bracket placeholder")

        for key in ZERO_GUID_KEYS:
            value = env.get(key, "")
            if value and not is_zero_guid(value):
                failures.append(f".env.sample {key} should use a zero GUID placeholder")

        if env.get("RUN_LIVE_CALLS") != "false":
            failures.append(".env.sample RUN_LIVE_CALLS must default to false")
        if env.get("NEXT_TELEMETRY_DISABLED") != "1":
            failures.append(".env.sample NEXT_TELEMETRY_DISABLED must default to 1")

    if failures:
        print("Sample hygiene check: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Sample hygiene check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
