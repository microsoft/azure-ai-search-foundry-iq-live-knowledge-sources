"""Generate sample payloads for live Knowledge Sources.

Usage:
    python samples/python/build_payloads.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ks_factory import (
    create_fabric_ontology_knowledge_source,
    create_knowledge_base,
    create_mcp_server_knowledge_source,
)


def main() -> None:
    mcp_source = create_mcp_server_knowledge_source(
        name="microsoft-learn-mcp-ks",
        server_url="https://learn.microsoft.com/api/mcp",
        tool_name="microsoft_docs_search",
        description="Microsoft Learn MCP grounding source for official documentation.",
    )

    fabric_source = create_fabric_ontology_knowledge_source(
        name="fabric-ontology-ks",
        workspace_id="00000000-0000-0000-0000-000000000000",
        ontology_id="00000000-0000-0000-0000-000000000001",
        description="Governed business-semantic grounding source from Microsoft Fabric.",
    )

    knowledge_base = create_knowledge_base(
        name="live-knowledge-sources-kb",
        knowledge_source_names=["microsoft-learn-mcp-ks", "fabric-ontology-ks"],
        retrieval_instructions=(
            "Use Fabric Ontology for governed business entities and relationships. "
            "Use MCP Server for remote tool-backed documentation or API data."
        ),
    )

    print(json.dumps({"mcp": mcp_source, "fabric": fabric_source, "knowledgeBase": knowledge_base}, indent=2))


if __name__ == "__main__":
    main()
