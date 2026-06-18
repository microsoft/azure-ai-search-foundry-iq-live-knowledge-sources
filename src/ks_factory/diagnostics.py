"""Helpers for inspecting retrieve responses."""

from __future__ import annotations

from typing import Any


def summarize_activity(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact view of retrieve activity records."""
    activity = response.get("activity", [])
    summary: list[dict[str, Any]] = []

    for item in activity:
        record = {
            "type": item.get("type"),
            "knowledgeSourceName": item.get("knowledgeSourceName"),
            "toolName": item.get("toolName"),
        }
        if "count" in item:
            record["count"] = item.get("count")
        if "mcpServerArguments" in item:
            record["mcpServerArguments"] = item.get("mcpServerArguments")
        if "fabricOntologyArguments" in item:
            record["fabricOntologyArguments"] = item.get("fabricOntologyArguments")
        summary.append(record)

    return summary


def summarize_references(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact view of retrieve references."""
    references = response.get("references", [])
    summary: list[dict[str, Any]] = []

    for item in references:
        source_data = item.get("sourceData")
        record = {
            "type": item.get("type"),
            "title": item.get("title"),
            "knowledgeSourceName": item.get("knowledgeSourceName"),
            "toolName": item.get("toolName"),
            "hasSourceData": "sourceData" in item,
        }
        if isinstance(source_data, dict):
            record["sourceDataKeys"] = sorted(source_data.keys())
        summary.append(record)

    return summary
