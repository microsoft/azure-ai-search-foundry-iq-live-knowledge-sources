# API Compatibility

The live profiles in this accelerator are intentionally pinned to Azure AI Search `2026-05-01-preview`. They use two preview-only Knowledge Source kinds and the full retrieval behavior. Changing only `search.api_version` does not convert those payloads into a stable API workload.

LiveKS therefore rejects any other API version during configuration resolution, before `plan` or provisioning. A future stable lane needs a separate profile and payload contract; it must not silently weaken the current source evidence.

## Stable And Preview Matrix

| Contract | `2026-04-01` stable | `2026-05-01-preview` | This accelerator |
| --- | --- | --- | --- |
| Release status | Generally available data-plane API. | Preview API; behavior and schema can change. | Pinned preview lane only. |
| Knowledge Source kinds | Search index, Azure Blob, indexed OneLake, and Web. | Stable kinds plus preview kinds, including MCP Server and Fabric Ontology. | MCP Server and Fabric Ontology are first-class; the uploaded sample index is not yet wrapped as a Knowledge Source. |
| Retrieve input | `intents`. | `intents` and `messages`. | Uses the preview `messages` contract. |
| Retrieval behavior | Minimal, extractive retrieval. | Query planning, answer synthesis, and configurable reasoning effort. | Uses answer synthesis and `low` reasoning effort. |
| MCP Server KS | Not accepted. | Supported in preview. | Required by `mcp-only`, `byo-fabric`, and `full`. |
| Fabric Ontology KS | Not accepted. | Supported in preview. | Required by `byo-fabric` and `full`; intentionally absent from `mcp-only`. |
| Search authentication | API key or Microsoft Entra bearer token. | API key or Microsoft Entra bearer token. | Sample default reads an admin key transiently; bearer with **Search Index Data Reader** is the managed-client path. |
| Source authorization | Depends on the selected generally available source. | Fabric calls additionally require delegated `x-ms-query-source-authorization`. | Fabric verification acquires and passes the raw delegated Search token transiently. |
| Supported LiveKS profiles | None. | `mcp-only`, `byo-fabric`, and `full`. | Stable plus MCP/Fabric fails closed during YAML validation. |

## What The Pin Protects

The repository's builders create `mcpServer` and `fabricOntology` payloads. Its Knowledge Bases request `answerSynthesis`, use configurable reasoning effort, and its retrieve requests expect the preview evidence envelope. Substituting `2026-04-01` would mix incompatible source kinds and retrieval behavior.

This fail-closed rule is narrower than claiming the stable API is unsupported by Azure AI Search. The stable API is valid for its generally available source kinds and minimal, extractive behavior; this repository simply does not implement that separate lane yet.

## Upgrade Checklist

Before changing the pinned version:

1. Compare the migration guide and REST schemas for every Knowledge Source and Knowledge Base payload.
2. Confirm MCP Server and Fabric Ontology remain available in the target version.
3. Re-run local builder tests, all three live profile rehearsals, source-specific retrieve checks, native MCP checks, and cleanup checks.
4. Update the profile defaults, schema enum, REST samples, notebooks, app API, badges, and this matrix in one change.
5. Keep public PR validation offline; run cloud drift checks only in an approved protected environment.

## Microsoft Sources Of Truth

- [Create a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [Query a Knowledge Base using retrieve or MCP](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
- [Upgrade Azure AI Search REST API versions](https://learn.microsoft.com/azure/search/search-api-migration)
- [Azure AI Search What's New](https://learn.microsoft.com/azure/search/whats-new)
- [Knowledge Source overview](https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview)
