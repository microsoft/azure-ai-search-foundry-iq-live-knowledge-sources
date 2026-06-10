"""Helpers for inspecting retrieve responses."""

from __future__ import annotations

from typing import Any


def summarize_activity(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact view of retrieve activity records."""
    activity = response.get("activity", [])
    return [
        {
            "type": item.get("type"),
            "knowledgeSourceName": item.get("knowledgeSourceName"),
            "toolName": item.get("toolName"),
        }
        for item in activity
    ]


def summarize_references(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact view of retrieve references."""
    references = response.get("references", [])
    return [
        {
            "type": item.get("type"),
            "title": item.get("title"),
            "knowledgeSourceName": item.get("knowledgeSourceName"),
            "toolName": item.get("toolName"),
            "hasSourceData": "sourceData" in item,
        }
        for item in references
    ]

