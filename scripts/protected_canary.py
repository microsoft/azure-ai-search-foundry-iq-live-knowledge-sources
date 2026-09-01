#!/usr/bin/env python3
"""Prepare and summarize the manual protected lifecycle canary."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.canary import (  # noqa: E402
    CanaryConfigurationError,
    build_canary_evidence,
    generated_canary_environment,
    preflight_from_environment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--environment", required=True)

    evidence = subparsers.add_parser("evidence")
    evidence.add_argument("--environment", required=True)
    evidence.add_argument("--preflight-outcome", default="unknown")
    evidence.add_argument("--login-outcome", default="unknown")
    evidence.add_argument("--lifecycle-outcome", default="unknown")
    evidence.add_argument("--cleanup-outcome", default="unknown")
    evidence.add_argument("--output", type=Path, required=True)
    evidence.add_argument("--detail", type=Path, required=True)
    evidence.add_argument("--summary", type=Path)

    final_status = subparsers.add_parser("final-status")
    final_status.add_argument("--capsule", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preflight":
        try:
            if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_RUN_ATTEMPT"):
                expected_environment = generated_canary_environment(
                    os.environ["GITHUB_RUN_ID"],
                    os.environ["GITHUB_RUN_ATTEMPT"],
                )
                if args.environment != expected_environment:
                    raise CanaryConfigurationError(
                        "Protected canary environment does not match the workflow run identity."
                    )
            path, _ = preflight_from_environment(
                ROOT,
                environment=args.environment,
            )
        except CanaryConfigurationError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(
            "Protected canary preflight: PASS "
            f"({path.name}; configuration values hidden)"
        )
        return 0
    if args.command == "evidence":
        capsule = build_canary_evidence(
            ROOT,
            environment=args.environment,
            preflight_outcome=args.preflight_outcome,
            login_outcome=args.login_outcome,
            lifecycle_outcome=args.lifecycle_outcome,
            cleanup_outcome=args.cleanup_outcome,
            output_path=args.output,
            detail_path=args.detail,
            summary_path=args.summary,
        )
        print(f"Protected canary evidence: {str(capsule['status']).upper()}")
        return 0
    if args.command == "final-status":
        import json

        try:
            capsule = json.loads(args.capsule.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Protected canary evidence is unavailable: {error}", file=sys.stderr)
            return 1
        status = str(capsule.get("status") or "unknown")
        print(f"Protected canary final status: {status.upper()}")
        return 0 if status == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
