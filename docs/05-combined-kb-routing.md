# Combined Knowledge Base Routing

LiveKS includes three combined paths:

- `mcp-search-index`: a GA Search Index KS plus a preview MCP Server KS in one preview KB.
- `three-source`: the same two sources plus a preview native Fabric Ontology KS over existing governed assets.
- `byo-fabric` and `full`: Fabric Ontology KS plus MCP Server KS.

Use [MCP + Search Index Knowledge Base](24-mcp-search-index-kb.md) for the data-plane-only existing-index lifecycle. It proves Search Index and MCP independently through the same combined KB before allowing both source parameters in the final query.

Use [Preview Three-Source Knowledge Base](25-three-source-kb.md) to prove Search Index, MCP, and Fabric independently before offering all three to the planner.

## Validation Goal

The first validation question is not only whether the answer is useful. It is whether the Knowledge Base selected and called the expected source.

Inspect:

- `activity`
- selected knowledge source
- MCP tool name and arguments
- Fabric ontology response
- `references`
- `sourceData`

The direct combined profiles claim routing only from those fields. They never infer routing from the synthesized answer.

## REST Flow

Run the combined path after both Knowledge Sources exist:

```text
samples/rest/01-create-mcp-server-ks.http
samples/rest/04-create-fabric-ontology-ks.http
samples/rest/05-create-combined-kb.http
samples/rest/03-retrieve-mcp.http
samples/rest/06-retrieve-fabric-ontology.http
samples/rest/08-retrieve-combined-airline-ops.http
```

## Routing Guidance

Good descriptions and retrieval instructions help source selection. Keep each source description specific:

- Search Index source: domain content held in the existing agentic-ready index.
- Fabric source: business entities, relationships, governed semantic terms.
- MCP source: remote tool-backed documentation or operational API data.

For the Airline Ops walkthrough, use Fabric Ontology for business data questions such as customer-care exposure, controllable delay categories, delayed flights, and route relationships. Use Microsoft Learn MCP for implementation questions such as how to create Knowledge Sources, how retrieve responses expose `activity`, and how to inspect references.

## Combined Demo Query

Use this query after both sources are attached:

```text
Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response.
```

Expected behavior:

- Fabric Ontology KS provides the airline ranking and exposure data.
- MCP Server KS provides implementation guidance for inspecting retrieve traces.
- Depending on routing behavior, one or both sources may appear. Use the offline replay file to show the ideal combined trace shape.
