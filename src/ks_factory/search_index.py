"""Search Index Knowledge Source payload helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _field_references(names: Iterable[str]) -> list[dict[str, str]]:
    return [{"name": name} for name in names if name]


def create_search_index_knowledge_source(
    *,
    name: str,
    search_index_name: str,
    semantic_configuration_name: str,
    search_fields: Iterable[str] = (),
    source_data_fields: Iterable[str] = (),
    description: str = "Knowledge Source over an existing Azure AI Search index.",
) -> dict[str, Any]:
    """Build the generally available Search Index Knowledge Source payload."""
    if not name or not search_index_name or not semantic_configuration_name:
        raise ValueError("name, search_index_name, and semantic_configuration_name are required")

    parameters: dict[str, Any] = {
        "searchIndexName": search_index_name,
        "semanticConfigurationName": semantic_configuration_name,
    }
    search_field_references = _field_references(search_fields)
    source_data_field_references = _field_references(source_data_fields)
    if search_field_references:
        parameters["searchFields"] = search_field_references
    if source_data_field_references:
        parameters["sourceDataFields"] = source_data_field_references

    return {
        "name": name,
        "kind": "searchIndex",
        "description": description,
        "searchIndexParameters": parameters,
    }
