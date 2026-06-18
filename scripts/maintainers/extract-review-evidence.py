#!/usr/bin/env python3
"""Extract safe review-packet evidence from a sanitized E2E summary."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path


def parse_summary(path: Path) -> tuple[list[tuple[str, str, str]], dict[str, dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    bt = chr(96)
    summary_re = re.compile(
        r"^\| Report \d+ \| "
        + bt
        + r"([^"
        + bt
        + r"]+)"
        + bt
        + r" \| "
        + bt
        + r"([^"
        + bt
        + r"]+)"
        + bt
        + r" \| "
        + bt
        + r"([^"
        + bt
        + r"]+)"
        + bt
        + r" \| ([^|]+) \| "
        + bt
        + r"([^"
        + bt
        + r"]+)"
        + bt
        + r" \|$"
    )
    detail_re = re.compile(r"^### Report \d+: " + bt + r"([^" + bt + r"]+)" + bt + r"$")
    check_re = re.compile(r"^\| " + bt + r"?(PASS|FAIL|SKIP)" + bt + r"? \| ([^|]+) \|$")

    mode_verdicts: list[tuple[str, str, str]] = []
    checks_by_mode: dict[str, dict[str, str]] = defaultdict(dict)
    current_mode: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        summary_match = summary_re.match(line)
        if summary_match:
            mode, _generated, _location, counts, verdict = summary_match.groups()
            mode_verdicts.append((mode, counts.strip(), verdict))
            continue

        detail_match = detail_re.match(line)
        if detail_match:
            current_mode = detail_match.group(1)
            continue

        check_match = check_re.match(line)
        if check_match and current_mode:
            status, name = check_match.groups()
            if name.strip() != "Check":
                checks_by_mode[current_mode][name.strip()] = status

    return mode_verdicts, checks_by_mode


def render_evidence(mode_verdicts: list[tuple[str, str, str]], checks_by_mode: dict[str, dict[str, str]]) -> str:
    def modes_with(check_name: str, status: str = "PASS") -> list[str]:
        return [mode for mode, checks in checks_by_mode.items() if checks.get(check_name) == status]

    mode_order = [mode for mode, _counts, _verdict in mode_verdicts]

    def ordered_modes(modes: list[str] | set[str]) -> list[str]:
        mode_set = set(modes)
        ordered = [mode for mode in mode_order if mode in mode_set]
        extras = sorted(mode_set - set(ordered))
        return ordered + extras

    def sentence_for(check_name: str, label: str, skip_phrase: str = "") -> str:
        passed = ordered_modes(modes_with(check_name, "PASS"))
        skipped = ordered_modes(modes_with(check_name, "SKIP"))
        if passed:
            text = f"{label} PASS in {', '.join(passed)}"
            if skipped and skip_phrase:
                text += f"; SKIP in {', '.join(skipped)} ({skip_phrase})"
            return text + "."
        if skipped:
            return f"{label} SKIP in {', '.join(skipped)}."
        return f"{label}: not proven by the sanitized summary."

    mode_line = "No summarized E2E modes found."
    if mode_verdicts:
        mode_line = "; ".join(f"{mode}={verdict} ({counts})" for mode, counts, verdict in mode_verdicts) + "."

    app_checks = [
        "Demo app root returns HTTP 200",
        "GET /api/status returns non-secret config",
        "POST /api/retrieve/mcp works",
        "POST /api/retrieve/fabric returns expected offline/live response",
        "POST /api/retrieve/combined returns expected offline/live response",
    ]
    if all(modes_with(check_name, "PASS") for check_name in app_checks):
        app_pass_modes = ordered_modes(set.intersection(*[set(modes_with(check_name, "PASS")) for check_name in app_checks]))
    else:
        app_pass_modes = []

    cleanup_checks = ["destroy.sh cleanup completes", "Resource group is deleted or not found"]
    if all(modes_with(check_name, "PASS") for check_name in cleanup_checks):
        cleanup_pass_modes = ordered_modes(
            set.intersection(*[set(modes_with(check_name, "PASS")) for check_name in cleanup_checks])
        )
    else:
        cleanup_pass_modes = []

    retrieval_parts = [
        sentence_for("MCP retrieve returns activity/reference evidence", "MCP retrieve"),
        sentence_for(
            "Fabric live retrieve returns ontology activity when token is provided",
            "Fabric live retrieve",
            "mcp-only does not configure Fabric live mode",
        ),
    ]

    offline_modes = ordered_modes(modes_with("Fabric live retrieve returns ontology activity when token is provided", "SKIP"))
    offline_text = "No offline/SKIP path recorded in the sanitized summary."
    if offline_modes:
        offline_text = (
            "Fabric-specific live checks are SKIP in "
            + ", ".join(offline_modes)
            + " by design; app routes still returned expected offline/live responses where checked."
        )

    lines = [
        f"- E2E modes: {mode_line}",
        "- MCP KS: " + sentence_for("Microsoft Learn MCP Knowledge Source exists", "Microsoft Learn MCP KS"),
        "- Fabric KS: "
        + sentence_for(
            "Fabric Ontology Knowledge Source exists when configured",
            "Fabric Ontology KS",
            "mcp-only skips Fabric",
        ),
        "- Knowledge Base: "
        + sentence_for("MCP-only Knowledge Base exists", "MCP-only KB")
        + " "
        + sentence_for("Combined Knowledge Base exists", "Combined KB"),
        "- Retrieve evidence: " + " ".join(retrieval_parts),
        "- App load: "
        + (
            f"Root, status, MCP, Fabric, and combined API checks PASS in {', '.join(app_pass_modes)}."
            if app_pass_modes
            else "not fully proven by the sanitized summary."
        ),
        "- Cleanup: "
        + (
            f"destroy.sh and resource-group deletion checks PASS in {', '.join(cleanup_pass_modes)}."
            if cleanup_pass_modes
            else "not fully proven by the sanitized summary."
        ),
        f"- Offline replay used: {offline_text}",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract safe review-packet evidence from a sanitized E2E summary.")
    parser.add_argument("summary", help="Path to scratch/review-packets/e2e-evidence-summary-*.local.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"Missing sanitized E2E summary: {summary_path}")
        return 2
    mode_verdicts, checks_by_mode = parse_summary(summary_path)
    print(render_evidence(mode_verdicts, checks_by_mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
