"""Inspect a saved retrieve response.

Usage:
    python samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ks_factory.diagnostics import summarize_activity, summarize_references


def summarize_source_data(response: dict) -> list[dict]:
    """Return a tiny sourceData preview for terminal demos."""
    previews = []
    for item in response.get("references", []):
        source_data = item.get("sourceData")
        if not isinstance(source_data, dict):
            continue

        compact = {}
        for key in sorted(source_data.keys())[:3]:
            value = source_data.get(key)
            if isinstance(value, str):
                compact[key] = value[:220] + ("..." if len(value) > 220 else "")
            elif isinstance(value, (int, float, bool)) or value is None:
                compact[key] = value
            elif isinstance(value, list):
                compact[key] = f"list[{len(value)}]"
            elif isinstance(value, dict):
                compact[key] = f"object[{len(value)}]"
            else:
                compact[key] = type(value).__name__

        previews.append(
            {
                "type": item.get("type"),
                "title": item.get("title"),
                "knowledgeSourceName": item.get("knowledgeSourceName"),
                "sourceDataPreview": compact,
            }
        )
    return previews


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python samples/python/inspect_retrieve_response.py <response.json>")

    response_path = Path(sys.argv[1])
    response = json.loads(response_path.read_text(encoding="utf-8"))

    print("Activity")
    print(json.dumps(summarize_activity(response), indent=2))
    print()
    print("References")
    print(json.dumps(summarize_references(response), indent=2))
    print()
    print("Source Data Preview")
    print(json.dumps(summarize_source_data(response), indent=2))


if __name__ == "__main__":
    main()
