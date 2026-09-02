"""Load the repository's machine-readable compatibility authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/compatibility.yaml"


class CompatibilityError(ValueError):
    """Raised when the compatibility authority is missing or malformed."""


def load_compatibility_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    try:
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CompatibilityError(f"Compatibility contract not found: {path}") from error
    except yaml.YAMLError as error:
        raise CompatibilityError(f"Invalid compatibility YAML in {path}: {error}") from error
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise CompatibilityError(f"{path} must be a schema_version: 1 mapping.")
    return contract


def version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError as error:
        raise CompatibilityError(f"Invalid dotted compatibility version: {value}") from error


CONTRACT = load_compatibility_contract()
STABLE_SEARCH_API_VERSION = str(CONTRACT["api_contracts"]["search_index"]["version"])
PREVIEW_SEARCH_API_VERSION = str(CONTRACT["api_contracts"]["preview"]["version"])
PYTHON_MINIMUM = version_tuple(str(CONTRACT["runtimes"]["python"]["minimum"]))
AZD_MINIMUM = version_tuple(str(CONTRACT["tools"]["azd"]["minimum"]))
NODE_MINIMUM = version_tuple(str(CONTRACT["tools"]["node"]["minimum"]))
