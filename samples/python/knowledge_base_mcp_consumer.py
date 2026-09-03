#!/usr/bin/env python3
"""Run the standalone, environment-configured Knowledge Base MCP consumer."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from liveks.mcp_client import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
