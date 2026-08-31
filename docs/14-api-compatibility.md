# API Compatibility

LiveKS has two deliberately separate API contracts. `search-index` uses generally available Azure AI Search `2026-04-01` with an existing index and minimal extractive retrieval. `mcp-only`, `byo-fabric`, and `full` remain pinned to `2026-05-01-preview`. `mcp-search-index` carries both contracts explicitly: only Search Index KS operations use GA, while MCP KS, combined KB, and retrieve operations use preview.

Changing only `search.api_version` never converts one lane into the other. The combined profile uses separate `search.index_api_version` and `search.preview_api_version` fields so no request can silently inherit the wrong shape. Configuration resolution rejects a profile/version mismatch before `plan` or any data-plane write.

## Stable And Preview Matrix

| Contract | `2026-04-01` stable | `2026-05-01-preview` | This accelerator |
| --- | --- | --- | --- |
| Release status | Generally available data-plane API. | Preview API; behavior and schema can change. | Separate stable and preview profiles. |
| Knowledge Source kinds | Search index, Azure Blob, indexed OneLake, and Web. | Stable kinds plus preview kinds, including MCP Server and Fabric Ontology. | `search-index` wraps a BYO index; other live profiles use MCP Server and optional Fabric Ontology. |
| Retrieve input | `intents`. | `intents` and `messages`. | `search-index` uses `intents`; preview profiles use `messages`. |
| Retrieval behavior | Minimal, extractive retrieval. | Query planning, answer synthesis, and configurable reasoning effort. | Stable lane is extractive; preview lane uses answer synthesis and `low` reasoning effort. |
| MCP Server KS | Not accepted. | Supported in preview. | Required by `mcp-search-index`, `mcp-only`, `byo-fabric`, and `full`. |
| Fabric Ontology KS | Not accepted. | Supported in preview. | Required by `byo-fabric` and `full`; intentionally absent from `mcp-only`. |
| Search authentication | API key or Microsoft Entra bearer token. | API key or Microsoft Entra bearer token. | `search-index` uses a transient bearer token; preview sample deployments read their generated admin key transiently. |
| Source authorization | Depends on the selected generally available source. | Fabric calls additionally require delegated `x-ms-query-source-authorization`. | Fabric verification acquires and passes the raw delegated Search token transiently. |
| Supported LiveKS profiles | `search-index`; Search Index KS operations in `mcp-search-index`. | MCP KS, combined KB, and retrieve operations in `mcp-search-index`; all operations in `mcp-only`, `byo-fabric`, and `full`. | Every profile/version pairing fails closed during YAML validation. |

## What The Pin Protects

The preview builders create `mcpServer` and `fabricOntology` payloads. Their Knowledge Bases request `answerSynthesis`, use configurable reasoning effort, and send `messages`. Substituting `2026-04-01` would mix incompatible source kinds and retrieval behavior.

The stable builder creates `searchIndex`, requires a semantic configuration, omits models and preview-only Knowledge Base properties, and sends `intents`. It also treats the Search service and index as reused assets. Substituting the preview API would silently change the lane's availability and evidence contract, so LiveKS rejects it.

The combined builder does not send one payload family through both versions. It creates the Search Index KS through `2026-04-01`, then creates MCP KS and the LLM-backed two-source KB through `2026-05-01-preview`. Its independent and combined calls all use preview `messages`; the stable `intents` body remains confined to the standalone `search-index` profile.

## Upgrade Checklist

Before changing the pinned version:

1. Compare the migration guide and REST schemas for every Knowledge Source and Knowledge Base payload.
2. Confirm MCP Server and Fabric Ontology remain available in the target version.
3. Re-run local builder tests, the stable and preview live profile rehearsals, source-specific retrieve checks, native MCP checks where applicable, and cleanup checks.
4. Update the profile defaults, schema enum, REST samples, notebooks, app API, badges, and this matrix in one change.
5. Keep public PR validation offline; run cloud drift checks only in an approved protected environment.

## Microsoft Sources Of Truth

- [Create a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [Query a Knowledge Base using retrieve or MCP](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
- [Upgrade Azure AI Search REST API versions](https://learn.microsoft.com/azure/search/search-api-migration)
- [Azure AI Search What's New](https://learn.microsoft.com/azure/search/whats-new)
- [Knowledge Source overview](https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview)
- [Create a Search Index Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index)
- [Create an MCP Server Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
