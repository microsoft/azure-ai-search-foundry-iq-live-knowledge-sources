"""Knowledge Base payload helpers."""

from __future__ import annotations

from typing import Any


def create_knowledge_base(
    *,
    name: str,
    knowledge_source_names: list[str],
    description: str = "Knowledge Base with live Knowledge Sources.",
    retrieval_instructions: str = "Use the configured live Knowledge Sources to answer with references.",
    reasoning_effort: str = "low",
) -> dict[str, Any]:
    """Build a Knowledge Base request payload."""
    return {
        "name": name,
        "description": description,
        "retrievalInstructions": retrieval_instructions,
        "outputMode": "answerSynthesis",
        "retrievalReasoningEffort": {
            "kind": reasoning_effort,
        },
        "knowledgeSources": [{"name": source_name} for source_name in knowledge_source_names],
    }

