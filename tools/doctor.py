#!/usr/bin/env python3
"""Summarize which repo profiles are ready in the current environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import validate as profile_validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Report runnable profiles for the current checkout.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    reports = [
        profile_validate.check_profile(profile, args.env_file)
        for profile in sorted(profile_validate.PROFILES)
    ]
    ready = [report["profile"] for report in reports if report["status"] == "pass"]
    blocked = [report["profile"] for report in reports if report["status"] != "pass"]
    output = {
        "status": "pass" if ready else "fail",
        "ready_profiles": ready,
        "blocked_profiles": blocked,
        "profiles": reports,
    }

    if args.format == "json":
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print("Ready profiles: " + (", ".join(ready) if ready else "none"))
        print("Blocked profiles: " + (", ".join(blocked) if blocked else "none"))
        for report in reports:
            print()
            print(profile_validate.render_text(report))

    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
