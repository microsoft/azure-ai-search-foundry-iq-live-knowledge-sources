"""MCP Server Knowledge Source payload helpers."""

from __future__ import annotations

from typing import Any


def create_mcp_server_knowledge_source(
    *,
    name: str,
    server_url: str,
    tool_name: str,
    description: str = "Remote MCP Server Knowledge Source.",
    output_parsing_kind: str = "auto",
    max_output_tokens: int = 1000,
) -> dict[str, Any]:
    """Build an MCP Server Knowledge Source request payload."""
    return {
        "name": name,
        "kind": "mcpServer",
        "description": description,
        "mcpServerParameters": {
            "serverURL": server_url,
            "tools": [
                {
                    "name": tool_name,
                    "outputParsing": {
                        "kind": output_parsing_kind,
                    },
                    "inclusionMode": "reranked",
                    "maxOutputTokens": max_output_tokens,
                }
            ],
        },
    }

