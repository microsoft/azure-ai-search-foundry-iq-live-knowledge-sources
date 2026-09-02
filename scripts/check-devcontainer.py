#!/usr/bin/env python3
"""Validate the reproducible and non-mutating Codespaces first boot."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


CONFIG_PATH = Path(".devcontainer/devcontainer.json")
DOCKERFILE_PATH = Path(".devcontainer/Dockerfile")
LOCK_PATH = Path(".devcontainer/devcontainer-lock.json")
POST_CREATE_PATH = Path(".devcontainer/post-create.sh")
WELCOME_PATH = Path(".devcontainer/welcome.sh")
COMPATIBILITY_PATH = Path("config/compatibility.yaml")

FORBIDDEN_AUTO_COMMANDS = (
    r"^\s*(?:\./)?liveks\s+(?:up|down|e2e)\b",
    r"^\s*azd\s+(?:up|provision|deploy|down)\b",
    r"^\s*az\s+(?:deployment|group\s+(?:create|delete))\b",
    r"^\s*(?:python3?\s+)?scripts/(?:fabric-provision|postprovision)\.py\b",
)


def fail(message: str) -> int:
    print(f"Dev container check: FAIL\n- {message}", file=sys.stderr)
    return 1


def main() -> int:
    for path in (CONFIG_PATH, DOCKERFILE_PATH, LOCK_PATH, POST_CREATE_PATH, WELCOME_PATH, COMPATIBILITY_PATH):
        if not path.is_file():
            return fail(f"missing {path}")

    try:
        compatibility = yaml.safe_load(COMPATIBILITY_PATH.read_text(encoding="utf-8"))
        python_version = str(compatibility["runtimes"]["python"]["minimum"])
        tools = compatibility["tools"]
        required_offline_commands = tuple(
            str(step["display"])
            for step in compatibility["command_sets"]["posix"]["steps"]
            if step["id"] != "validate-local"
        )
    except (KeyError, TypeError, yaml.YAMLError) as exc:
        return fail(f"{COMPATIBILITY_PATH} is invalid: {exc}")

    expected_image = f"mcr.microsoft.com/devcontainers/python:1-{python_version}-bookworm"
    expected_features = {
        "ghcr.io/devcontainers/features/node:2.1.0": {
            "version": str(tools["node"]["pinned_environment"]),
            "pnpmVersion": "none",
        },
        "ghcr.io/devcontainers/features/azure-cli:1.3.0": {
            "version": str(tools["azure_cli"]["pinned_environment"]),
            "installBicep": True,
            "bicepVersion": f"v{tools['bicep']['pinned_environment']}",
        },
        "ghcr.io/azure/azure-dev/azd:0.2.0": {
            "version": str(tools["azd"]["pinned_environment"])
        },
    }

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"{CONFIG_PATH} is not valid JSON: {exc}")

    if config.get("build") != {"dockerfile": "Dockerfile"}:
        return fail("the reviewed dev container Dockerfile is not configured")

    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    if f"FROM {expected_image}" not in dockerfile:
        return fail(f"the Python {python_version} Bookworm image is not pinned as expected")
    if "rm -f /etc/apt/sources.list.d/yarn.list" not in dockerfile:
        return fail("the unused expired Yarn apt source is not removed")

    features = config.get("features")
    if features != expected_features:
        return fail("runtime features or versions differ from the tested contract")

    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"{LOCK_PATH} is not valid JSON: {exc}")
    locked_features = lock.get("features")
    if not isinstance(locked_features, dict) or set(locked_features) != set(expected_features):
        return fail("the Feature lock does not match devcontainer.json")
    for feature_id, locked in locked_features.items():
        if not isinstance(locked, dict):
            return fail(f"the Feature lock entry is invalid for {feature_id}")
        expected_version = feature_id.rsplit(":", 1)[1]
        integrity = locked.get("integrity")
        resolved = locked.get("resolved")
        if locked.get("version") != expected_version:
            return fail(f"the Feature lock version is stale for {feature_id}")
        if not isinstance(integrity, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", integrity):
            return fail(f"the Feature lock integrity is invalid for {feature_id}")
        if not isinstance(resolved, str) or not resolved.endswith(f"@{integrity}"):
            return fail(f"the Feature lock resolution is invalid for {feature_id}")

    if config.get("postCreateCommand") != "bash .devcontainer/post-create.sh":
        return fail("postCreateCommand must delegate to the reviewed setup script")
    if config.get("postAttachCommand") != "bash .devcontainer/welcome.sh":
        return fail("postAttachCommand must delegate to the non-mutating welcome script")

    post_create = POST_CREATE_PATH.read_text(encoding="utf-8")
    missing = [command for command in required_offline_commands if command not in post_create]
    if missing:
        return fail("post-create is missing safe checks: " + ", ".join(missing))

    executable_lines = [
        line
        for line in post_create.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "printf"))
    ]
    for line in executable_lines:
        if any(re.search(pattern, line) for pattern in FORBIDDEN_AUTO_COMMANDS):
            return fail(f"cloud-mutating command is not allowed during container creation: {line.strip()}")

    container_env = config.get("containerEnv", {})
    if container_env.get("NEXT_TELEMETRY_DISABLED") != "1":
        return fail("NEXT_TELEMETRY_DISABLED must remain enabled by default")
    if container_env.get("AZURE_CORE_COLLECT_TELEMETRY") != "false":
        return fail("Azure CLI telemetry must remain disabled by default")
    if container_env.get("AZURE_DEV_COLLECT_TELEMETRY") != "no":
        return fail("Azure Developer CLI telemetry must remain disabled by default")
    if container_env.get("AZURE_BICEP_CHECK_VERSION") != "false":
        return fail("Bicep update checks must not add a first-boot network call")
    if container_env.get("LIVEKS_VENV") != ".liveks/venv-devcontainer":
        return fail("the container must use its own ignored virtual environment")

    if "for tool in python3 node az azd; do" not in post_create:
        return fail("post-create does not enumerate every required runtime")
    if 'command -v "$tool"' not in post_create:
        return fail("post-create does not fail closed when a runtime is missing")
    if "az bicep version" not in post_create:
        return fail("post-create does not validate the pinned Bicep CLI")

    print("Dev container check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
