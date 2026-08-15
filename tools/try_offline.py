#!/usr/bin/env python3
"""Dependency-free first-success path for checked-in retrieve traces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.evidence import generated_at, repository_revision, runtime_summary, sha256_file, write_json  # noqa: E402


SAMPLES = {
    "mcp": ROOT / "samples/responses/mcp-retrieve.sample.json",
    "fabric": ROOT / "samples/responses/fabric-airline-ops-retrieve.sample.json",
    "combined": ROOT / "samples/responses/combined-airline-ops-retrieve.sample.json",
}
CONTRACTS = {
    "mcp": {
        "sourceTypes": {"mcpServer"},
        "sourceNames": {"microsoft-learn-mcp-ks"},
        "knownAnswerTerm": "Azure AI Search",
    },
    "fabric": {
        "sourceTypes": {"fabricOntology"},
        "sourceNames": {"fabric-ontology-ks"},
        "knownAnswerTerm": "Alpine Air",
    },
    "combined": {
        "sourceTypes": {"fabricOntology", "mcpServer"},
        "sourceNames": {"fabric-ontology-ks", "microsoft-learn-mcp-ks"},
        "knownAnswerTerm": "Alpine Air",
    },
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


def _types(items: list[Any]) -> set[str]:
    return {
        str(item["type"])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("type"), str)
    }


def build_checks(sample: str, response: dict[str, Any]) -> list[dict[str, Any]]:
    contract = CONTRACTS[sample]
    expected_types = set(contract["sourceTypes"])
    expected_names = set(contract["sourceNames"])
    activity_types = _types(response.get("activity", []))
    reference_types = _types(response.get("references", []))
    observed_names = set(source_names(response))
    answer = answer_text(response)
    known_answer = str(contract["knownAnswerTerm"])

    return [
        {
            "name": "known-answer",
            "status": "pass" if known_answer.casefold() in answer.casefold() else "fail",
            "message": "The packaged answer contains the scenario's known non-sensitive fact.",
            "expectedTermCount": 1,
            "matchedExpectedTermCount": 1 if known_answer.casefold() in answer.casefold() else 0,
        },
        {
            "name": "activity-evidence",
            "status": "pass" if expected_types.issubset(activity_types) else "fail",
            "message": "Activity contains every source type required by the replay contract.",
            "expectedSourceTypes": sorted(expected_types),
            "observedSourceTypes": sorted(activity_types),
        },
        {
            "name": "reference-evidence",
            "status": "pass" if expected_types.issubset(reference_types) else "fail",
            "message": "References contain every source type required by the replay contract.",
            "expectedSourceTypes": sorted(expected_types),
            "observedSourceTypes": sorted(reference_types),
        },
        {
            "name": "source-identity",
            "status": "pass" if expected_names.issubset(observed_names) else "fail",
            "message": "The packaged trace names every Knowledge Source required by the scenario.",
            "expectedSourceNames": sorted(expected_names),
            "observedSourceNames": sorted(observed_names),
        },
    ]


def build_report(sample: str) -> dict[str, Any]:
    response = json.loads(SAMPLES[sample].read_text(encoding="utf-8"))
    checks = build_checks(sample, response)
    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    return {
        "schemaVersion": 2,
        "command": "try",
        "status": status,
        "mode": "offline-replay",
        "sample": sample,
        "answer": answer_text(response),
        "sources": source_names(response),
        "sourceTypes": sorted(_types(response.get("activity", [])) | _types(response.get("references", []))),
        "activityCount": len(response.get("activity", [])),
        "referenceCount": len(response.get("references", [])),
        "checks": checks,
        "response": response,
    }


def build_evidence_capsule(report: dict[str, Any]) -> dict[str, Any]:
    sample_path = SAMPLES[str(report["sample"])]
    safe_check_fields = (
        "name",
        "status",
        "expectedTermCount",
        "matchedExpectedTermCount",
        "expectedSourceTypes",
        "observedSourceTypes",
        "expectedSourceNames",
        "observedSourceNames",
    )
    assertions = [
        {key: check[key] for key in safe_check_fields if key in check}
        for check in report.get("checks", [])
        if isinstance(check, dict)
    ]
    return {
        "schemaVersion": 1,
        "kind": "liveks-evidence-capsule",
        "scope": "offline-first-success",
        "status": report["status"],
        "generatedAt": generated_at(),
        "repositoryRevision": repository_revision(ROOT),
        "command": f"./liveks try --sample {report['sample']}",
        "mode": "offline-replay",
        "networkCalls": 0,
        "runtime": runtime_summary(),
        "fixture": {
            "path": str(sample_path.relative_to(ROOT)),
            "sha256": sha256_file(sample_path),
        },
        "evidence": {
            "activityCount": report["activityCount"],
            "referenceCount": report["referenceCount"],
            "sourceNames": report["sources"],
            "sourceTypes": report["sourceTypes"],
        },
        "assertions": assertions,
        "privacy": {
            "answerIncluded": False,
            "queryIncluded": False,
            "rawResponseIncluded": False,
            "credentialsIncluded": False,
        },
    }


def render_text(report: dict[str, Any], details: bool, evidence_path: Path | None = None) -> str:
    passed = sum(check.get("status") == "pass" for check in report.get("checks", []))
    total = len(report.get("checks", []))
    lines = [
        "Answer",
        str(report["answer"]),
        "",
        "Sources",
        ", ".join(report["sources"]) or "No source evidence",
        "",
        f"Trace: {report['activityCount']} activity items, {report['referenceCount']} references (offline replay)",
        f"Contract: {str(report['status']).upper()} ({passed}/{total} assertions)",
    ]
    for check in report.get("checks", []):
        if check.get("status") == "fail":
            lines.append(f"[FAIL] {check.get('name')}: {check.get('message')}")
    if evidence_path:
        lines.append(f"Evidence capsule: {evidence_path}")
    if details:
        lines.extend(["", "Full response", json.dumps(report["response"], indent=2)])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a checked-in retrieve trace without cloud resources.")
    parser.add_argument("--sample", choices=sorted(SAMPLES), default="combined")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--evidence-out", type=Path, help="Write a sanitized machine-readable evidence capsule.")
    args = parser.parse_args(argv)
    report = build_report(args.sample)
    if args.evidence_out:
        write_json(args.evidence_out, build_evidence_capsule(report))
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report, args.details, args.evidence_out))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
