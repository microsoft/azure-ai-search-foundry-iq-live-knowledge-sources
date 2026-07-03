#!/usr/bin/env python3
"""Fail when tracked files make the sample repository unnecessarily heavy."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_MEDIA_MAX_BYTES = 256 * 1024

MEDIA_OR_ARCHIVE_EXTENSIONS = {
    ".7z",
    ".avi",
    ".gz",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".tar",
    ".tgz",
    ".webm",
    ".zip",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help="Maximum allowed size for any tracked file.",
    )
    parser.add_argument(
        "--media-max-bytes",
        type=int,
        default=DEFAULT_MEDIA_MAX_BYTES,
        help="Maximum allowed size for tracked media or archive files.",
    )
    return parser.parse_args()


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def human_size(size: int) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    tracked_sizes: list[tuple[int, str]] = []

    for file_path in git_ls_files():
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            continue

        size = path.stat().st_size
        tracked_sizes.append((size, file_path))
        suffix = path.suffix.lower()

        if size > args.max_file_bytes:
            failures.append(
                f"{file_path} is {human_size(size)}, above the tracked-file limit "
                f"of {human_size(args.max_file_bytes)}"
            )
        elif suffix in MEDIA_OR_ARCHIVE_EXTENSIONS and size > args.media_max_bytes:
            failures.append(
                f"{file_path} is a tracked media/archive file of {human_size(size)}, "
                f"above the media limit of {human_size(args.media_max_bytes)}"
            )

    if failures:
        print("Repository size check: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        print(
            "Move large walkthrough media, recordings, archives, and generated build "
            "outputs to GitHub Releases or another artifact store instead of git.",
            file=sys.stderr,
        )
        return 1

    tracked_sizes.sort(reverse=True)
    largest = ", ".join(f"{path} ({human_size(size)})" for size, path in tracked_sizes[:3])
    print(f"Repository size check: PASS; largest tracked files: {largest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
