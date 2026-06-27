#!/usr/bin/env python3
"""Machine-readable profile validation for agents and maintainers."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROFILES: dict[str, dict[str, Any]] = {
    "offline": {
        "required_tools": ["python3"],
        "required_env": [],
        "next_safe_step": "Run the offline response inspector against samples/responses/*.sample.json.",
    },
    "mcp-only": {
        "required_tools": ["bash", "python3", "azd", "az", "node", "npm"],
        "required_env": [],
        "next_safe_step": "Run bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus.",
    },
    "byo-fabric": {
        "required_tools": ["bash", "python3", "azd", "az", "node", "npm"],
        "required_env": ["FABRIC_WORKSPACE_ID", "FABRIC_ONTOLOGY_ID"],
        "next_safe_step": "Fill an ignored env file from env/byo-fabric.env.example, then run the byo-fabric deploy wrapper.",
    },
    "semantic-join": {
        "required_tools": ["python3"],
        "required_env": [],
        "next_safe_step": "Inspect samples/responses/combined-airline-ops-retrieve.sample.json.",
    },
}

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

FORBIDDEN_TRACKED_NAMES = {
    ".env",
    ".env.external.local",
    "deployment-summary.md",
}

ZERO_GUID_RE = re.compile(r"^0{8}-0{4}-0{4}-0{4}-0{11}[0-9a-fA-F]$")


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return Path(result.stdout.strip())


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def effective_env(env_file: Path | None) -> dict[str, str]:
    values = dict(os.environ)
    if env_file:
        values.update(parse_env_file(env_file))
    return values


def is_placeholder(value: str) -> bool:
    if not value:
        return True
    if value.startswith("<") and value.endswith(">"):
        return True
    if ZERO_GUID_RE.fullmatch(value):
        return True
    return False


def git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def forbidden_tracked_files(root: Path) -> list[str]:
    failures: list[str] = []
    for file_path in git_ls_files(root):
        path = Path(file_path)
        if file_path in FORBIDDEN_TRACKED_NAMES or path.name in FORBIDDEN_TRACKED_NAMES:
            failures.append(file_path)
        elif any(file_path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES):
            failures.append(file_path)
    return sorted(set(failures))


def check_profile(profile: str, env_file: Path | None = None) -> dict[str, Any]:
    root = repo_root()
    config = PROFILES[profile]
    env = effective_env(env_file)

    missing_tools = [tool for tool in config["required_tools"] if shutil.which(tool) is None]
    missing_env = [
        key
        for key in config["required_env"]
        if is_placeholder(env.get(key, ""))
    ]
    forbidden_files = forbidden_tracked_files(root)

    checks = [
        {
            "name": "required_tools",
            "status": "pass" if not missing_tools else "fail",
            "missing": missing_tools,
        },
        {
            "name": "required_env",
            "status": "pass" if not missing_env else "fail",
            "missing": missing_env,
        },
        {
            "name": "forbidden_tracked_outputs",
            "status": "pass" if not forbidden_files else "fail",
            "files": forbidden_files,
        },
    ]

    status = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
    return {
        "profile": profile,
        "status": status,
        "env_file": str(env_file) if env_file else None,
        "checks": checks,
        "next_safe_step": config["next_safe_step"],
    }


def run_local_gate(root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["bash", "scripts/validate-local.sh", "--no-color"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return {
        "name": "validate_local",
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "output_tail": result.stdout.splitlines()[-30:],
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [f"Profile: {report['profile']}", f"Status: {report['status']}"]
    for check in report["checks"]:
        lines.append(f"- {check['name']}: {check['status']}")
        missing = check.get("missing") or check.get("files") or []
        if missing:
            lines.append("  " + ", ".join(missing))
    lines.append(f"Next safe step: {report['next_safe_step']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repo agent-operability profile readiness.")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="offline")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--run-local-gate", action="store_true", help="Also run scripts/validate-local.sh.")
    args = parser.parse_args()

    if args.env_file and not args.env_file.exists():
        print(f"Missing env file: {args.env_file}", file=sys.stderr)
        return 2

    report = check_profile(args.profile, args.env_file)
    if args.run_local_gate:
        gate = run_local_gate(repo_root())
        report["checks"].append(gate)
        if gate["status"] != "pass":
            report["status"] = "fail"

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))

    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
