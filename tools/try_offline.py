#!/usr/bin/env python3
"""Dependency-free first-success path for checked-in retrieve traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "mcp": ROOT / "samples/responses/mcp-retrieve.sample.json",
    "fabric": ROOT / "samples/responses/fabric-airline-ops-retrieve.sample.json",
    "combined": ROOT / "samples/responses/combined-airline-ops-retrieve.sample.json",
}


def answer_text(response: dict[str, Any]) -> str:
    for message in response.get("response", []):
        for content in message.get("content", []):
            if content.get("type") == "text" and content.get("text"):
                return str(content["text"])
    return "No answer returned."


def source_names(response: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in response.get("activity", []) + response.get("references", []):
        name = item.get("knowledgeSourceName")
        if name and name not in names:
            names.append(str(name))
    return names


def build_report(sample: str) -> dict[str, Any]:
    response = json.loads(SAMPLES[sample].read_text(encoding="utf-8"))
    return {
        "schemaVersion": 2,
        "command": "try",
        "status": "pass",
        "mode": "offline-replay",
        "sample": sample,
        "answer": answer_text(response),
        "sources": source_names(response),
        "activityCount": len(response.get("activity", [])),
        "referenceCount": len(response.get("references", [])),
        "response": response,
    }


def render_text(report: dict[str, Any], details: bool) -> str:
    lines = [
        "Answer",
        str(report["answer"]),
        "",
        "Sources",
        ", ".join(report["sources"]) or "No source evidence",
        "",
        f"Trace: {report['activityCount']} activity items, {report['referenceCount']} references (offline replay)",
    ]
    if details:
        lines.extend(["", "Full response", json.dumps(report["response"], indent=2)])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a checked-in retrieve trace without cloud resources.")
    parser.add_argument("--sample", choices=sorted(SAMPLES), default="combined")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    report = build_report(args.sample)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report, args.details))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
