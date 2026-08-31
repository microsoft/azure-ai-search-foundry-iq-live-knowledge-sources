#!/usr/bin/env python3
"""Generate shell-safe legacy env examples from the canonical YAML ledger."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.config import flatten, load_yaml  # noqa: E402


PROFILE_TARGETS = {
    "offline": ROOT / "env/offline.env.example",
    "search-index": ROOT / "env/search-index.env.example",
    "mcp-search-index": ROOT / "env/mcp-search-index.env.example",
    "mcp-only": ROOT / "env/mcp-only.env.example",
    "byo-fabric": ROOT / "env/byo-fabric.env.example",
    "full": ROOT / "env/full.env.example",
}


def shell_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value in {None, ""}:
        return "''"
    return shlex.quote(str(value))


def legacy_shell_value(env_name: str, value: Any) -> str:
    if env_name == "NEXT_TELEMETRY_DISABLED" and isinstance(value, bool):
        return "1" if value else "0"
    return shell_value(value)


def profile_values(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    schema = load_yaml(ROOT / "config/schema.yaml")
    manifest = load_yaml(ROOT / "profiles" / f"{name}.yaml")
    values = flatten(manifest.get("defaults", {}))
    for required in manifest.get("required", []):
        if schema["fields"][required].get("type") == "guid":
            values[required] = "00000000-0000-0000-0000-000000000000"
    return schema, values


def render_profile(name: str) -> str:
    schema, values = profile_values(name)
    reverse = {path: env_name for env_name, path in schema["legacy_env"].items() if env_name not in {"SEARCH_API_VERSION"}}
    if name in {"search-index", "mcp-search-index"}:
        reverse["search.index_name"] = "SEARCH_INDEX_NAME"
    lines = [
        f"# Generated legacy compatibility example for {name}.",
        "# Source of truth: config/schema.yaml and profiles/*.yaml.",
        "# Prefer: ./liveks init --profile %s --env <environment>" % name if name != "offline" else "# Prefer: ./liveks try",
        "",
    ]
    for path, value in values.items():
        env_name = reverse.get(path)
        if env_name:
            lines.append(f"{env_name}={legacy_shell_value(env_name, value)}")
    if name == "byo-fabric":
        lines.append("FABRIC_USER_SEARCH_TOKEN=''")
    return "\n".join(lines) + "\n"


def render_catalog() -> str:
    schema, values = profile_values("mcp-only")
    _, full_values = profile_values("full")
    values.update({path: value for path, value in full_values.items() if path not in values})
    lines = [
        "# Generated legacy environment catalog.",
        "# Source of truth: config/schema.yaml and profiles/*.yaml.",
        "# Prefer .liveks/<env>.yaml created by ./liveks init.",
        "# - search-index: wrap an existing Search index with the stable extractive contract.",
        "# - mcp-search-index: combine reused Search and OpenAI assets with an MCP source.",
        "# - mcp-only: deploy Azure AI Search with the MCP Server Knowledge Source.",
        "# - byo-fabric: connect an existing Fabric ontology without taking ownership.",
        "# - full: create the Fabric sample stack after explicit cost acknowledgement.",
        "",
    ]
    seen: set[str] = set()
    for env_name, path in schema["legacy_env"].items():
        if path in seen or env_name == "SEARCH_API_VERSION":
            continue
        seen.add(path)
        spec = schema["fields"][path]
        value = values.get(path, "")
        if spec.get("secret"):
            value = ""
        lines.append(f"{env_name}={legacy_shell_value(env_name, value)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = {ROOT / ".env.sample": render_catalog()}
    outputs.update({path: render_profile(profile) for profile, path in PROFILE_TARGETS.items()})
    failures = []
    for path, expected in outputs.items():
        if args.check:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                failures.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
    if failures:
        print("Generated env examples are stale: " + ", ".join(failures), file=sys.stderr)
        return 1
    print("Env example generation: PASS" if args.check else "Env examples generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
