#!/usr/bin/env python3
"""Dependency-free first-success path backed by declarative scenario packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.evidence import write_json  # noqa: E402
from liveks.scenarios import (  # noqa: E402
    ScenarioError,
    build_evidence_capsule,
    load_registry,
    run_case,
    safe_run_report,
)


def build_report(sample: str, *, fixture_override: Path | None = None) -> dict:
    return run_case(sample, root=ROOT, fixture_override=fixture_override)


def render_text(
    report: dict,
    details: bool,
    evidence_path: Path | None = None,
) -> str:
    passed = sum(check.get("status") == "pass" for check in report.get("checks", []))
    total = len(report.get("checks", []))
    if report["status"] != "pass":
        lines = [
            f"Scenario: {report['scenarioId']} ({report['scenarioVersion']})",
            "Contract: FAIL",
        ]
        lines.extend(
            f"[FAIL] {check['id']}: {check['message']}"
            for check in report["checks"]
            if check["status"] == "fail"
        )
        lines.append("Failure output is redacted; inspect the synthetic fixture locally.")
        return "\n".join(lines)
    lines = [
        "Answer",
        str(report["answer"]),
        "",
        "Sources",
        ", ".join(report["sourceNames"]) or "No source evidence",
        "",
        f"Trace: {report['activityCount']} activity items, "
        f"{report['referenceCount']} references (offline replay)",
        f"Contract: PASS ({passed}/{total} assertions)",
    ]
    if evidence_path:
        lines.append(f"Evidence capsule: {evidence_path}")
    if details:
        lines.extend(["", "Full response", json.dumps(report["response"], indent=2)])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        registry = load_registry(ROOT, deep=False)
    except ScenarioError as error:
        print(f"Scenario configuration: FAIL\n- {error}", file=sys.stderr)
        return 2
    aliases = sorted(registry["aliases"])
    parser = argparse.ArgumentParser(
        description="Inspect a checked-in scenario replay without cloud resources."
    )
    parser.add_argument("--sample", choices=aliases, default="combined")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--evidence-out",
        type=Path,
        help="Write a sanitized machine-readable evidence capsule.",
    )
    args = parser.parse_args(argv)
    try:
        report = build_report(args.sample)
    except (OSError, ScenarioError, ValueError) as error:
        failure = {
            "schemaVersion": 1,
            "command": "try",
            "status": "fail",
            "mode": "offline-replay",
            "checks": [
                {
                    "id": "scenario-configuration",
                    "status": "fail",
                    "message": str(error),
                }
            ],
        }
        if args.format == "json":
            print(json.dumps(failure, indent=2, sort_keys=True))
        else:
            print("Scenario configuration: FAIL")
            print(f"[FAIL] scenario-configuration: {error}")
        return 2
    if args.evidence_out:
        write_json(args.evidence_out, build_evidence_capsule(report, root=ROOT))
    if args.format == "json":
        output = report if report["status"] == "pass" else safe_run_report(report)
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(render_text(report, args.details, args.evidence_out))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
