#!/usr/bin/env python3
"""Compatibility entry point that reports v2 profile readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from liveks.cli import doctor_report
    from liveks.config import ConfigError, available_profiles, resolve_config
except ModuleNotFoundError as error:
    raise SystemExit("LiveKS dependencies are missing. Run ./liveks bootstrap first.") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Report LiveKS profile readiness.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    reports = []
    for profile in available_profiles():
        try:
            config = resolve_config(profile=profile, environment="offline" if profile == "offline" else f"doctor-{profile}", legacy_env_path=args.env_file)
            reports.append(doctor_report(config, cloud=False))
        except ConfigError as error:
            reports.append({"profile": profile, "status": "fail", "checks": [{"name": "configuration", "status": "fail", "message": str(error)}]})
    ready = [report["profile"] for report in reports if report["status"] in {"pass", "warn"}]
    blocked = [report["profile"] for report in reports if report["status"] == "fail"]
    output = {"schemaVersion": 2, "command": "doctor", "status": "pass" if ready else "fail", "readyProfiles": ready, "blockedProfiles": blocked, "profiles": reports}
    if args.format == "json":
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print("Ready profiles: " + (", ".join(ready) if ready else "none"))
        print("Blocked profiles: " + (", ".join(blocked) if blocked else "none"))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
