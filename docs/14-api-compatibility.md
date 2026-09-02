# API Compatibility

LiveKS has two deliberately separate API contracts. `search-index` uses generally available Azure AI Search `2026-04-01` with an existing index and minimal extractive retrieval. `mcp-only`, `byo-fabric`, and `full` remain pinned to `2026-05-01-preview`. `mcp-search-index` and `three-source` carry both contracts explicitly: only Search Index KS operations use GA, while MCP KS, native Fabric KS, combined KB, and retrieve operations use preview.

Changing only `search.api_version` never converts one lane into the other. The combined profile uses separate `search.index_api_version` and `search.preview_api_version` fields so no request can silently inherit the wrong shape. Configuration resolution rejects a profile/version mismatch before `plan` or any data-plane write.

<!-- compatibility-contract:start -->
## Continuously Checked Compatibility

This table reports requirements and executed evidence separately. A launcher accepting a version is not a claim that CI exercised it.

| Runtime or tool | Required or minimum | Continuously checked evidence | Not claimed |
| --- | --- | --- | --- |
| Python | Python 3.11 or newer is required by every profile and both launchers. | GitHub Actions runs the documented command contract on Python 3.11 for ubuntu-latest and windows-latest. | Python 3.12 through 3.14 are accepted by the launchers but are not continuously exercised by this repository. |
| Runner OS | The repository has separate POSIX Bash and Windows PowerShell command contracts. | validate.yml exercises ubuntu-latest and windows-latest; these labels are floating runner images, not OS release pins. | Other Linux distributions, macOS, and other Windows releases are not continuously exercised. |
| Azure CLI | Required by every live profile; the repository enforces presence but does not declare a supported version range. | The dev container pin is checked at 2.86.0; validate-local exercises the hosted runner's unpinned Azure CLI and Bicep capability. | Azure CLI versions other than the dev container pin are not compatibility claims. |
| Azure Developer CLI | Required only by provisioned preview profiles; doctor enforces 1.27.0 or newer. | The dev container declaration is checked at 1.28.0; ordinary credential-free CI does not run an azd deployment command. | No broader azd version range or live deployment compatibility is claimed. |
| Node.js | Required by provisioned preview profiles and by the static demo build. | setup-node runs Node.js 22 for the Ubuntu, Windows, and Pages jobs, and npm builds the static demo. | Other Node.js major versions are not continuously exercised. |
| npm | Required with Node.js for provisioned preview profiles and npm ci/build validation. | Ubuntu, Windows, and Pages jobs use the npm bundled by setup-node 22. | A standalone npm version range is not claimed. |
| Bicep CLI | Required through Azure CLI for provisioned preview plan and deployment paths. | The dev container pin is checked at 0.44.1; validate-local compiles infra/main.bicep with the hosted runner capability. | Bicep versions other than the dev container pin are not compatibility claims. |

The exact continuously exercised combinations are:

| Workflow job | Runner | Python | Node.js | Evidence |
| --- | --- | --- | --- | --- |
| [`local-validation`](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/.github/workflows/validate.yml) | `ubuntu-latest` | `3.11` | `22` | Runs the complete documented no-cloud command contract and repository gate. |
| [`cli-windows`](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/.github/workflows/validate.yml) | `windows-latest` | `3.11` | `22` | Runs the PowerShell command contract and the Windows-compatible repository gate. |
| [`build`](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/.github/workflows/pages.yml) | `ubuntu-latest` | `3.11` | `22` | Builds the MkDocs manual strictly and builds the static demo. |

## Pinned Azure AI Search API Contracts

| Lane | Version and status | Bound profiles and operations | Checked authority |
| --- | --- | --- | --- |
| Search Index KS | `2026-04-01` (generally available) | `search-index`, `mcp-search-index`, `three-source`: Search Index KS creation; the standalone stable profile also uses minimal extractive retrieval. | config/schema.yaml and the search-index, mcp-search-index, and three-source profiles. |
| MCP Server, Fabric Ontology, and preview KB | `2026-05-01-preview` (public preview) | `mcp-search-index`, `three-source`, `mcp-only`, `byo-fabric`, `full`: MCP Server KS, Fabric Ontology KS, combined KB, messages retrieve, and Knowledge Base MCP. | config/schema.yaml, preview profiles, generated examples, infrastructure, app, REST samples, and notebooks. |

MCP Server KS and Fabric Ontology KS remain public preview. Their request and response behavior can change; review the official Microsoft Learn links below before changing either pin. This accelerator is not a production-readiness claim.

## Documentation Command Contract

From a fresh checkout, the canonical path installs only the pinned local Python dependency, inspects checked-in data, and runs local validation. It does not authenticate, call Azure or Fabric, or run `up`, `down`, or `e2e`.

**macOS and Linux**

```bash
./liveks try
./liveks bootstrap
./liveks profiles
./liveks doctor --profile offline --format json
bash scripts/validate-local.sh
```

**Windows PowerShell**

```powershell
.\liveks.ps1 try
.\liveks.ps1 bootstrap
.\liveks.ps1 profiles
.\liveks.ps1 doctor --profile offline --format json
.\scripts\validate-local.ps1
```

Each command must exit `0`. The runner also checks replay assertions, bootstrap completion, profile output, the offline doctor JSON envelope, and the final local-validation pass signal.

**Azure live validation: NOT RUN. Fabric live validation: NOT RUN.** Ordinary compatibility CI is credential-free and non-mutating.
<!-- compatibility-contract:end -->

## Stable And Preview Matrix

| Contract | `2026-04-01` stable | `2026-05-01-preview` | This accelerator |
| --- | --- | --- | --- |
| Release status | Generally available data-plane API. | Preview API; behavior and schema can change. | Separate stable and preview profiles. |
| Knowledge Source kinds | Search index, Azure Blob, indexed OneLake, and Web. | Stable kinds plus preview kinds, including MCP Server and Fabric Ontology. | `search-index` wraps a BYO index; other live profiles use MCP Server and optional Fabric Ontology. |
| Retrieve input | `intents`. | `intents` and `messages`. | `search-index` uses `intents`; preview profiles use `messages`. |
| Retrieval behavior | Minimal, extractive retrieval. | Query planning, answer synthesis, and configurable reasoning effort. | Stable lane is extractive; preview lane uses answer synthesis and `low` reasoning effort. |
| MCP Server KS | Not accepted. | Supported in preview. | Required by `mcp-search-index`, `three-source`, `mcp-only`, `byo-fabric`, and `full`. |
| Fabric Ontology KS | Not accepted. | Supported in preview. | Required by `three-source`, `byo-fabric`, and `full`; intentionally absent from `mcp-only`. |
| Search authentication | API key or Microsoft Entra bearer token. | API key or Microsoft Entra bearer token. | `search-index` uses a transient bearer token; preview sample deployments read their generated admin key transiently. |
| Source authorization | Depends on the selected generally available source. | Fabric calls additionally require delegated `x-ms-query-source-authorization`. | Fabric verification acquires and passes the raw delegated Search token transiently. |
| Supported LiveKS profiles | `search-index`; Search Index KS operations in `mcp-search-index` and `three-source`. | MCP/KB/retrieve operations in both combined profiles, Fabric KS in `three-source`, and all operations in `mcp-only`, `byo-fabric`, and `full`. | Every profile/version pairing fails closed during YAML validation. |

## What The Pin Protects

The preview builders create `mcpServer` and `fabricOntology` payloads. Their Knowledge Bases request `answerSynthesis`, use configurable reasoning effort, and send `messages`. Substituting `2026-04-01` would mix incompatible source kinds and retrieval behavior.

The stable builder creates `searchIndex`, requires a semantic configuration, omits models and preview-only Knowledge Base properties, and sends `intents`. It also treats the Search service and index as reused assets. Substituting the preview API would silently change the lane's availability and evidence contract, so LiveKS rejects it.

The combined builder does not send one payload family through both versions. It creates Search Index KS through `2026-04-01`, then creates MCP KS, optional native Fabric Ontology KS, and the LLM-backed combined KB through `2026-05-01-preview`. Independent and combined calls all use preview `messages`; stable `intents` remains confined to standalone `search-index`.

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
- [Create a Fabric Ontology Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology)
