#!/usr/bin/env python3
"""Compatibility entry point for v2 profile validation."""

from __future__ import annotations

import argparse
import json
import subprocess
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
    parser = argparse.ArgumentParser(description="Validate a LiveKS execution profile.")
    parser.add_argument("--profile", choices=available_profiles(), default="offline")
    parser.add_argument("--env", dest="environment")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--run-local-gate", action="store_true")
    args = parser.parse_args()
    try:
        config = resolve_config(
            profile=args.profile,
            environment=args.environment or ("offline" if args.profile == "offline" else f"validate-{args.profile}"),
            config_path=args.config,
            legacy_env_path=args.env_file,
        )
        report = doctor_report(config, cloud=False)
    except ConfigError as error:
        report = {"schemaVersion": 2, "command": "validate", "status": "fail", "profile": args.profile, "checks": [{"name": "configuration", "status": "fail", "message": str(error)}]}
    if args.run_local_gate:
        result = subprocess.run(["bash", "scripts/validate-local.sh", "--no-color"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        report["checks"].append({"name": "validate-local", "status": "pass" if result.returncode == 0 else "fail", "message": "completed" if result.returncode == 0 else "failed", "outputTail": result.stdout.splitlines()[-30:]})
        if result.returncode != 0:
            report["status"] = "fail"
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Profile: {args.profile}\nStatus: {report['status']}")
        for check in report["checks"]:
            print(f"- {check['name']}: {check['status']} - {check['message']}")
    return 0 if report["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
