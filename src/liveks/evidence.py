"""Small, dependency-free helpers for sanitized execution evidence."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repository_revision(root: Path) -> str:
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    if COMMIT_SHA_RE.fullmatch(github_sha):
        return github_sha.lower()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    revision = result.stdout.strip()
    return revision.lower() if result.returncode == 0 and COMMIT_SHA_RE.fullmatch(revision) else "unavailable"


def runtime_summary() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "os": platform.system().lower() or sys.platform,
        "architecture": platform.machine().lower() or "unknown",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
