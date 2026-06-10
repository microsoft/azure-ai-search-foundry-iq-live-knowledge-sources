# Azure AI Search Foundry IQ Live Knowledge Sources

A reusable accelerator for Foundry IQ live grounding with two public preview Azure AI Search Knowledge Sources:

- Fabric Ontology Knowledge Source
- MCP Server Knowledge Source

This repository shows how to connect live enterprise knowledge to a Foundry IQ Knowledge Base, inspect retrieval traces, and reuse the same grounding layer across agents, apps, and demos.

## Primary Manuals

The sample assets in this repository follow these Azure AI Search preview manuals:

- [Create an MCP Server knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
- [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology)

## What You Will Build

```text
Agent / App
  -> Foundry IQ Knowledge Base
    -> Fabric Ontology Knowledge Source
    -> MCP Server Knowledge Source
  -> Grounded answer with activity, references, and source data
```

## Scenarios

| Scenario | What it demonstrates |
| --- | --- |
| MCP Server KS quickstart | Tool-backed live retrieval from an MCP-compatible HTTPS endpoint |
| Fabric Ontology KS | Governed business-semantic grounding from Microsoft Fabric |
| Combined KB routing | Multi-source routing, references, activity diagnostics, and source data inspection |

## Quickstart

1. Copy `.env.sample` to `.env`.
2. Configure your Azure AI Search endpoint and auth settings.
3. Start with `samples/rest/01-create-mcp-server-ks.http`.
4. Add Fabric workspace and ontology IDs when ready.
5. Create a knowledge base with one or both live sources.
6. Query with retrieve requests and inspect `activity`, `references`, and source data.
7. Run cleanup when finished.

## Repository Layout

```text
docs/          Architecture, pattern guidance, security, troubleshooting
samples/rest/  REST Client files for Knowledge Source and Knowledge Base operations
samples/python Python helpers for generating request payloads and inspecting traces
src/ks_factory Reusable payload builders for live Knowledge Sources
notebooks/     Workshop-style notebook placeholders
evals/         Source routing testset skeleton
assets/        Diagrams and screenshots
```

## Authentication Notes

Use API keys only for quick proof-of-concept flows. Use Microsoft Entra ID and Azure RBAC for reusable implementations. Fabric Ontology retrieval requires delegated user context at query time through `x-ms-query-source-authorization`. MCP Server knowledge sources can use no auth, stored headers, Foundry connections, or query-time header passthrough depending on the remote server.

## Preview Notes

These capabilities use preview APIs and can change. Keep API versions explicit in every request file and notebook. Validate data handling, tenant alignment, region behavior, and authorization before using regulated or customer data.

