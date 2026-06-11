# Choose a Pattern

| Pattern | Use when | Start here |
| --- | --- | --- |
| MCP Server KS | You need a low-friction public preview quickstart or tool-backed live retrieval | `samples/rest/01-create-mcp-server-ks.http` |
| Fabric Ontology KS | You need governed business semantics from Microsoft Fabric | `samples/rest/04-create-fabric-ontology-ks.http` |
| Combined KB | You need to validate multi-source routing and trace behavior | `samples/rest/05-create-combined-kb.http` |

## Recommended Order

1. Create the MCP Server KS.
2. Create the MCP-only Knowledge Base.
3. Retrieve from MCP and inspect `activity`, `references`, and source data.
4. Add Fabric Ontology KS after your Fabric workspace and ontology are ready.
5. Create a combined Knowledge Base and repeat trace validation.
