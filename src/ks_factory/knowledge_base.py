"""Knowledge Base payload helpers."""

from __future__ import annotations

from typing import Any


def create_knowledge_base(
    *,
    name: str,
    knowledge_source_names: list[str],
    azure_openai_endpoint: str | None = None,
    azure_openai_deployment_id: str | None = None,
    azure_openai_model_name: str | None = None,
    azure_openai_api_key: str | None = None,
    description: str = "Knowledge Base with live Knowledge Sources.",
    retrieval_instructions: str | None = "Use the configured live Knowledge Sources to answer with references.",
    reasoning_effort: str = "low",
) -> dict[str, Any]:
    """Build a Knowledge Base request payload."""
    payload: dict[str, Any] = {
        "name": name,
        "description": description,
        "outputMode": "answerSynthesis",
        "retrievalReasoningEffort": {
            "kind": reasoning_effort,
        },
        "knowledgeSources": [{"name": source_name} for source_name in knowledge_source_names],
    }

    if retrieval_instructions:
        payload["retrievalInstructions"] = retrieval_instructions

    if azure_openai_endpoint and azure_openai_deployment_id and azure_openai_model_name:
        payload["models"] = [
            {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": azure_openai_endpoint.rstrip("/"),
                    "deploymentId": azure_openai_deployment_id,
                    "modelName": azure_openai_model_name,
                    **({"apiKey": azure_openai_api_key} if azure_openai_api_key else {}),
                },
            }
        ]

    return payload
