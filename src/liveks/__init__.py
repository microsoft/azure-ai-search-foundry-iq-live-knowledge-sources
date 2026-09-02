"""LiveKS plan-first deployment helpers."""

from __future__ import annotations

import json
from pathlib import Path


_RELEASE_PATH = Path(__file__).resolve().parents[2] / "config/release.json"
__version__ = str(json.loads(_RELEASE_PATH.read_text(encoding="utf-8"))["product"]["version"])
