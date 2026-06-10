# Combined Knowledge Base Routing

The combined scenario attaches both live Knowledge Sources to one Knowledge Base:

- Fabric Ontology KS for governed business semantics.
- MCP Server KS for dynamic tool-backed retrieval.

## Validation Goal

The first validation question is not only whether the answer is useful. It is whether the Knowledge Base selected and called the expected source.

Inspect:

- `activity`
- selected knowledge source
- MCP tool name and arguments
- Fabric ontology response
- `references`
- `sourceData`

## Routing Guidance

Good descriptions and retrieval instructions help source selection. Keep each source description specific:

- Fabric source: business entities, relationships, governed semantic terms.
- MCP source: remote tool-backed documentation or operational API data.

