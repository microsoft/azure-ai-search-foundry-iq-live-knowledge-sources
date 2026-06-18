#!/usr/bin/env python3
"""Create a sanitized E2E evidence summary from ignored test reports.

The input reports under deployments/<env>/ can contain resource names, service
URLs, tenant IDs, and other local values. This script intentionally copies only
safe fields plus checklist status/check names. It never copies checklist notes.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SAFE_RUN_FIELDS = (
    "Deployment mode",
    "Location",
    "Fabric location",
    "Cleanup requested",
    "Generated",
    "Hosting mode",
)


RUN_FIELD_RE = re.compile(r"^- ([^:]+): `([^`]*)`$")
CHECK_RE = re.compile(r"^\| `?(PASS|FAIL|SKIP)`? \| ([^|]+) \|")


@dataclass
class Check:
    status: str
    name: str


@dataclass
class Report:
    path: Path
    fields: dict[str, str]
    checks: list[Check]

    @property
    def status_counts(self) -> Counter[str]:
        return Counter(check.status for check in self.checks)

    @property
    def verdict(self) -> str:
        counts = self.status_counts
        if counts["FAIL"] > 0:
            return "FAIL"
        if self.checks:
            return "PASS"
        return "UNKNOWN"


def parse_report(path: Path) -> Report:
    fields: dict[str, str] = {}
    checks: list[Check] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        field_match = RUN_FIELD_RE.match(line.strip())
        if field_match:
            key, value = field_match.groups()
            if key in SAFE_RUN_FIELDS:
                fields[key] = value
            continue

        check_match = CHECK_RE.match(line.strip())
        if check_match:
            status, name = check_match.groups()
            if name.strip() == "Check":
                continue
            checks.append(Check(status=status, name=name.strip()))

    return Report(path=path, fields=fields, checks=checks)


def progress_bar(passed: int, failed: int, skipped: int, width: int = 24) -> str:
    total = passed + failed + skipped
    if total == 0:
        return "[" + "-" * width + "] 0/0"
    done = passed + skipped
    filled = round(done * width / total)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {done}/{total}"


def render_report(report: Report, index: int, include_local_paths: bool) -> list[str]:
    counts = report.status_counts
    passed = counts["PASS"]
    failed = counts["FAIL"]
    skipped = counts["SKIP"]
    mode = report.fields.get("Deployment mode", "unknown")
    generated = report.fields.get("Generated", "unknown")
    location = report.fields.get("Location", "unknown")
    cleanup = report.fields.get("Cleanup requested", "unknown")

    lines = [
        f"### Report {index}: `{mode}`",
        "",
        f"- Verdict: `{report.verdict}`",
        f"- Generated: `{generated}`",
        f"- Location: `{location}`",
        f"- Cleanup requested: `{cleanup}`",
        f"- Checklist: `{passed} PASS`, `{failed} FAIL`, `{skipped} SKIP`",
        f"- Progress: `{progress_bar(passed, failed, skipped)}`",
    ]

    fabric_location = report.fields.get("Fabric location")
    if fabric_location:
        lines.append(f"- Fabric location: `{fabric_location}`")

    hosting_mode = report.fields.get("Hosting mode")
    if hosting_mode:
        lines.append(f"- Hosting mode: `{hosting_mode}`")

    if include_local_paths:
        lines.append(f"- Local report path: `{report.path.as_posix()}`")

    lines.extend(
        [
            "",
            "| Status | Check |",
            "| --- | --- |",
        ]
    )
    for check in report.checks:
        lines.append(f"| `{check.status}` | {check.name} |")
    lines.append("")
    return lines


def render_summary(reports: list[Report], include_local_paths: bool) -> str:
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        "# Sanitized E2E Evidence Summary",
        "",
        f"Generated: {generated}",
        "",
        "> Local ignored summary. Do not commit this file. It intentionally omits raw report notes, app URLs, Search endpoints, resource group names, subscription IDs, tenant IDs, keys, and tokens.",
        "",
        "## Summary",
        "",
        "| Report | Mode | Generated | Location | Checks | Verdict |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for index, report in enumerate(reports, start=1):
        counts = report.status_counts
        mode = report.fields.get("Deployment mode", "unknown")
        generated_at = report.fields.get("Generated", "unknown")
        location = report.fields.get("Location", "unknown")
        checks = f"{counts['PASS']} PASS / {counts['FAIL']} FAIL / {counts['SKIP']} SKIP"
        lines.append(f"| Report {index} | `{mode}` | `{generated_at}` | `{location}` | {checks} | `{report.verdict}` |")

    lines.extend(
        [
            "",
            "## Details",
            "",
        ]
    )

    for index, report in enumerate(reports, start=1):
        lines.extend(render_report(report, index, include_local_paths))

    lines.extend(
        [
            "## Safe Sharing Guidance",
            "",
            "Safe to copy into a private review note:",
            "",
            "- mode",
            "- generated timestamp",
            "- location",
            "- PASS / FAIL / SKIP counts",
            "- checklist status and check names",
            "- high-level caveats from docs",
            "",
            "Do not copy from raw reports without redaction:",
            "",
            "- checklist notes",
            "- app URLs",
            "- Search endpoints",
            "- resource group names",
            "- tenant or subscription IDs",
            "- keys, tokens, connection strings, or bearer headers",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a sanitized E2E evidence summary from ignored test reports.")
    parser.add_argument("reports", nargs="+", help="One or more deployments/<env>/test-report.md paths.")
    parser.add_argument(
        "--output",
        default="",
        help="Output markdown path. Defaults to scratch/review-packets/e2e-evidence-summary-<timestamp>.local.md.",
    )
    parser.add_argument(
        "--include-local-paths",
        action="store_true",
        help="Include local report paths in the generated ignored summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_paths = [Path(report) for report in args.reports]
    missing = [path for path in report_paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing report: {path}", flush=True)
        return 2

    reports = [parse_report(path) for path in report_paths]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(args.output) if args.output else Path(f"scratch/review-packets/e2e-evidence-summary-{timestamp}.local.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_summary(reports, include_local_paths=args.include_local_paths), encoding="utf-8")
    print(f"Sanitized E2E evidence summary written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
