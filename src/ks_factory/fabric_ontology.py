"""Fabric Ontology Knowledge Source payload helpers."""

from __future__ import annotations

from typing import Any


def create_fabric_ontology_knowledge_source(
    *,
    name: str,
    workspace_id: str,
    ontology_id: str,
    description: str = "Fabric Ontology Knowledge Source.",
) -> dict[str, Any]:
    """Build a Fabric Ontology Knowledge Source request payload."""
    return {
        "name": name,
        "kind": "fabricOntology",
        "description": description,
        "fabricOntologyParameters": {
            "workspaceId": workspace_id,
            "ontologyId": ontology_id,
        },
    }

