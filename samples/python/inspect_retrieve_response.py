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


if __name__ == "__main__":
    main()
