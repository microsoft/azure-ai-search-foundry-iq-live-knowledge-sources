# Preview Three-Source Knowledge Base

Use `three-source` only when an existing Azure AI Search index, Azure OpenAI deployment, Fabric workspace, and native Fabric ontology are ready. This data-plane-only profile creates no resource group, app, Search service, index, model deployment, Fabric workspace, ontology, or capacity.

It creates four Search objects:

1. Search Index Knowledge Source through GA `2026-04-01`,
2. MCP Server Knowledge Source through `2026-05-01-preview`,
3. native Fabric Ontology Knowledge Source through `2026-05-01-preview`,
4. one three-source Knowledge Base through `2026-05-01-preview`.

## Prerequisites

- The Search index has a semantic configuration and the configured fields satisfy the stable Search Index contract.
- The Search service managed identity has **Cognitive Services OpenAI User** access to the existing Azure OpenAI deployment.
- The Fabric workspace and ontology are in the same Microsoft Entra tenant as Search and are readable by the signed-in user.
- The signed-in user can acquire both Search and Fabric API tokens.
- Search data-plane permissions allow reading the index and creating, retrieving, and deleting Knowledge Sources and Knowledge Bases.

The Fabric path is the native `fabricOntology` Knowledge Source. Do not substitute Fabric MCP through the MCP Server source.

## Create The Ledger

```bash
./liveks bootstrap
./liveks init --profile three-source --env liveks-three
```

Edit ignored `.liveks/liveks-three.yaml`:

```yaml
version: 2
profile: three-source
environment: liveks-three
search:
  endpoint: https://<search-service>.search.windows.net
  index_name: <existing-index>
  semantic_configuration_name: <semantic-configuration>
  search_fields:
    - content
  source_data_fields:
    - id
    - title
    - content
openai:
  endpoint: https://<azure-openai-resource>.openai.azure.com
  deployment_name: <existing-chat-deployment>
  model_name: <model-name>
fabric:
  workspace_id: <existing-workspace-guid>
  ontology_id: <existing-ontology-guid>
  user_search_token:
    env: FABRIC_USER_SEARCH_TOKEN
```

The token reference is optional. When the environment variable is absent, `verify` acquires a transient delegated Search token from Azure CLI. Never put a raw token in YAML.

## Doctor And Plan

```bash
az login --tenant <tenant-guid>
./liveks doctor --env liveks-three
./liveks plan --env liveks-three --format json
```

`doctor` reads the existing index through GA, then reads the existing Fabric workspace and ontology through the Fabric API. It reports the Azure OpenAI managed-identity grant as unknown until retrieve proves it. All calls are read-only.

`plan` performs four GET-only collision checks and emits a redacted payload artifact:

| Object | API | Ownership |
| --- | --- | --- |
| Existing Search index | `2026-04-01` | Reuse |
| Generated Search Index KS | `2026-04-01` | Create |
| Generated MCP Server KS | `2026-05-01-preview` | Create |
| Generated Fabric Ontology KS | `2026-05-01-preview` | Create |
| Generated three-source KB | `2026-05-01-preview` | Create |
| Azure OpenAI deployment | Existing deployment | Reuse |
| Fabric workspace and ontology | Fabric v1 | Reuse |

The artifact replaces Azure OpenAI endpoint, Fabric IDs, and runtime questions with redacted markers. The profile never runs Bicep, `azd`, npm, `PUT`, or `DELETE` during plan.

## Create And Verify

```bash
./liveks up \
  --env liveks-three \
  --query "<question answerable from the existing index>" \
  --expect-term "<known non-sensitive indexed term>" \
  --mcp-query "<Microsoft Learn question>" \
  --fabric-query "<question answerable from the ontology>" \
  --combined-query "<question that can use any of the three sources>"
```

After plan review, type `create liveks-three`. Creation order is Search Index KS, MCP Server KS, Fabric Ontology KS, then Knowledge Base. Every pending name is journaled before `PUT`; successful objects record the remote ETag. Creation uses `If-None-Match`, reuse requires the recorded matching ETag and definition, and changed or unowned objects fail closed.

Verification uses the same KB in this strict order:

1. Search Index only: require `search-index-retrieve=pass`; expected terms match `references[*].sourceData`, never answer text.
2. MCP only: require `mcp-retrieve=pass`.
3. Fabric only: require `fabric-source-authorization=pass` and `fabric-retrieve=pass`.
4. All three available to the planner: require `combined-retrieve=pass`.

The Fabric-only and combined calls attach `x-ms-query-source-authorization` transiently. Combined routing is accepted only when recognized `searchIndex`, `mcpServer`, or `fabricOntology` evidence appears in activity, references, or reference sourceData. A fluent answer proves nothing about routing, and the planner may legitimately select one, two, or all three sources.

Run verification again without creating:

```bash
./liveks verify \
  --env liveks-three \
  --query "<index question>" \
  --expect-term "<known indexed term>" \
  --mcp-query "<MCP question>" \
  --fabric-query "<Fabric question>" \
  --combined-query "<combined question>"
```

Reports retain only normalized statuses, API contracts, evidence types/counts, and match counts. They exclude queries, expected terms, answers, raw responses, endpoints, Fabric IDs, and credentials.

## Cleanup

```bash
./liveks down --env liveks-three
```

Type `delete liveks-three`. A matching profile, environment, configuration digest, generated name, and remote ETag must prove each delete. Cleanup order is:

1. three-source KB through preview,
2. Fabric Ontology KS through preview,
3. MCP Server KS through preview,
4. Search Index KS through GA,
5. read the existing index through GA.

Require `search-index-preserved=pass`, `azure-openai-preserved=pass`, and `fabric-assets-preserved=pass`. A missing/mismatched lock or changed object preserves everything and returns `cleanup-incomplete`.

## Failure Signals

| Signal | Action |
| --- | --- |
| `search.index_api_version` failure | Restore GA `2026-04-01`; do not send the preview KS shape through stable. |
| `search.preview_api_version` failure | Restore `2026-05-01-preview` for MCP, Fabric, KB, and `messages` retrieve. |
| `fabric-workspace` or `fabric-ontology` failure | Confirm tenant alignment, IDs, and Fabric API permissions. |
| `fabric-source-authorization=fail` | Acquire a Search-scoped delegated user token; do not use a service token or persist it. |
| `*-name=fail` | Choose another environment/name; LiveKS will not overwrite an unowned object. |
| `combined-retrieve=fail` after an independent failure | Fix the failed source first; combined retrieval is intentionally not attempted. |

## Evidence Boundary

The checked-in `airline-ops.three-source-replay` scenario demonstrates response shape only. **Azure live validation: NOT RUN. Fabric live validation: NOT RUN. Protected canary: NOT RUN.**

Official contracts: [Search Index KS](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index), [MCP Server KS](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server), [Fabric Ontology KS](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology), [Knowledge Base creation](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base), and [retrieve](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve).
