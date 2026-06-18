#!/usr/bin/env python3
"""Validate local Markdown links without network access."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


LINK_PATTERN = re.compile(r"!?\[[^\]\n]+\]\(([^)\n]+)\)")
FENCED_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
EXTERNAL_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "#",
)


def tracked_markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def extract_destination(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1 : raw.index(">")]
    if raw.startswith('"') or raw.startswith("'"):
        return ""
    return raw.split()[0]


def local_target(path: Path, destination: str) -> Path | None:
    destination = unquote(destination.strip())
    if not destination or destination.startswith(EXTERNAL_PREFIXES):
        return None
    if destination.startswith("data:"):
        return None

    destination = destination.split("#", 1)[0].split("?", 1)[0]
    if not destination:
        return None

    if destination.startswith("/"):
        return Path(destination[1:])
    return path.parent / destination


def main() -> int:
    failures: list[str] = []
    checked = 0

    for markdown_path in tracked_markdown_files():
        text = markdown_path.read_text(encoding="utf-8")
        text = FENCED_BLOCK_PATTERN.sub("", text)
        for match in LINK_PATTERN.finditer(text):
            destination = extract_destination(match.group(1))
            target = local_target(markdown_path, destination)
            if target is None:
                continue
            checked += 1
            normalized = target.resolve(strict=False)
            repo_relative = Path.cwd().resolve()
            try:
                display_target = normalized.relative_to(repo_relative)
            except ValueError:
                display_target = target
            if not normalized.exists():
                failures.append(f"{markdown_path}: missing link target `{destination}` -> `{display_target}`")

    if failures:
        print("Markdown link check: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Markdown link check: PASS ({checked} local links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
