# MCP + Search Index Knowledge Base

Use `mcp-search-index` when an agentic-ready Azure AI Search index and an Azure OpenAI deployment already exist and you want one preview Knowledge Base that can route between indexed domain content and a remote MCP tool.

When an existing native Fabric ontology should join the same data-plane-only composition, use [Preview Three-Source Knowledge Base](25-three-source-kb.md).

This profile creates no resource group, Search service, index, Azure OpenAI deployment, hosting, or Fabric asset. It creates only:

1. a Search Index Knowledge Source through GA `2026-04-01`,
2. an MCP Server Knowledge Source through `2026-05-01-preview`,
3. one combined Knowledge Base through `2026-05-01-preview`.

The cross-version composition is deliberate. The persisted Search Index KS keeps the GA request shape, while the preview KB supplies the LLM-backed MCP tool selection and `messages` retrieve contract.

## Prerequisites

The existing index must have a semantic configuration and satisfy the same field rules as the [stable Search Index profile](23-search-index-ks.md). The signed-in identity needs Search data-plane permissions to read the index and create, retrieve, and delete Knowledge Sources and Knowledge Bases.

The existing Search service must have a managed identity with **Cognitive Services OpenAI User** access to the configured Azure OpenAI resource. `doctor` cannot prove this cross-resource runtime grant without invoking retrieve, so it reports the boundary as unknown. The independent protected retrieve checks are authoritative.

The default MCP source is the public Microsoft Learn endpoint:

```text
https://learn.microsoft.com/api/mcp
```

Review external service terms, data movement, and MCP security before replacing it.

## Create The Ledger

```bash
./liveks bootstrap
./liveks init --profile mcp-search-index --env liveks-combined
```

Edit the ignored `.liveks/liveks-combined.yaml`:

```yaml
version: 2
profile: mcp-search-index
environment: liveks-combined
search:
  endpoint: https://<search-service>.search.windows.net
  index_name: <existing-index-name>
  semantic_configuration_name: <semantic-configuration-name>
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
```

The profile pins these values internally:

```yaml
search:
  index_api_version: '2026-04-01'
  preview_api_version: 2026-05-01-preview
mcp:
  server_url: https://learn.microsoft.com/api/mcp
  tool_name: microsoft_docs_search
```

Changing either API version to the other lane fails configuration resolution. Unknown fields, untrusted endpoints, duplicate field names, missing required values, and collisions among the three generated object names also fail before a write.

## Doctor And Plan Are Read-Only

```bash
az login --tenant <tenant-guid>
./liveks doctor --env liveks-combined
./liveks plan --env liveks-combined --format json
```

`doctor` reads the existing index through GA `2026-04-01`. `plan` performs only three additional GET requests:

| Object | API |
| --- | --- |
| Generated Search Index KS name | `2026-04-01` |
| Generated MCP Server KS name | `2026-05-01-preview` |
| Generated combined KB name | `2026-05-01-preview` |

The plan names both sources, both API versions, reuse/create ownership, existing-service costs, and cleanup order. Its ignored payload artifact replaces the Azure OpenAI endpoint and all runtime questions with redacted markers. It never runs Bicep, `azd`, npm, `PUT`, or `DELETE`.

## Create And Prove

```bash
./liveks up \
  --env liveks-combined \
  --query "<question answerable from the existing index>" \
  --expect-term "<known non-sensitive term>" \
  --combined-query "<question that can use indexed content and Microsoft Learn>"
```

After reviewing the plan, type:

```text
create liveks-combined
```

Creation order is Search Index KS, MCP Server KS, then combined KB. `plan`, `up`, and `down` take one environment-scoped operation lock so concurrent lifecycle runs cannot overwrite ownership state. Each pending name is journaled before its PUT, and every successful response records the remote ETag before the next write. Create uses `If-None-Match`. An unchanged owned object with the same ETag is reused without another PUT; a definition change requires `down` followed by a clean recreation. Delete uses `If-Match`. An unowned, replaced, or concurrently created object is never overwritten. If a response is lost after Azure accepts a PUT, LiveKS reconciles the remote definition and ETag before continuing or preserving it for guarded cleanup.

`verify` uses the combined KB for three preview retrieve calls in this order:

1. Search Index only,
2. MCP Server only,
3. both sources available to the combined planner.

The Search Index expected term is matched against `references[*].sourceData`, not synthesized answer text. Independent acceptance requires `searchIndex` and `mcpServer` evidence respectively. Combined routing is reported only from `activity`, `references`, or `sourceData`; a fluent answer is not evidence, and the planner can legitimately select one or both sources.

Run the same contract without recreating objects:

```bash
./liveks verify \
  --env liveks-combined \
  --query "<index question>" \
  --expect-term "<known term>" \
  --mcp-query "<Microsoft Learn question>" \
  --combined-query "<combined question>"
```

The ignored verify report contains normalized statuses, counts, source types, and API contracts only. It excludes endpoints, questions, expected terms, answers, raw retrieve payloads, and credentials.

The combined KB also exposes a native MCP endpoint. Call it only after REST source proof:

```bash
./liveks mcp --env liveks-combined --auth bearer --expect-term "<known term>"
```

Native MCP output does not include the REST `activity` and `references` envelope, so it cannot replace the three-step retrieve contract.

## Protected Live Contract

`.github/workflows/protected-mcp-search-index.yml` is manual-only, accepts only an explicit `run-with-cleanup` confirmation on `main`, and uses the protected `mcp-search-index-live` GitHub Environment. Forks, pull requests, and untrusted refs cannot enter the credentialed job.

The first protected step checks required configuration names without printing values. Only then does OIDC login run. One generated environment name is used per workflow run and attempt. The lifecycle test invokes the actual guarded E2E path:

```text
doctor -> plan -> conditional create -> Search Index verify -> MCP verify
       -> combined verify -> dependency-ordered cleanup
```

The command is bounded by its own timeout and the job has a finite timeout. Workflow concurrency prevents two canaries from operating on the shared BYO target simultaneously. An `always()` step reruns lock/ETag-guarded cleanup after success, failure, or command timeout. The path never uses `--keep-resources`, `full`, or Fabric.

Only `.deployment/canary-evidence.json` is uploaded. Detailed E2E, cleanup, lock, and retry inputs remain ignored on the runner. The capsule retains only:

- revision, profile, assertion names/statuses,
- source types and evidence counts,
- retry categories/counts and terminal categories,
- generated-versus-BYO ownership classes,
- cost-sensitive resource classes,
- cleanup result and detailed-report digest.

It excludes questions, answers, raw payloads, tokens, endpoints, resource names, tenant/subscription IDs, GUID-shaped identifiers, and customer data.

Normal unit discovery skips this test:

```text
protected MCP + Search Index contract is opt-in
protected MCP + Search Index lifecycle canary is opt-in
```

Repository tests prove trigger, preflight, retry, cleanup, and capsule shape without Azure calls. They are not live evidence. Configure the protected environment only with approved non-customer acceptance questions and expected terms, then run the manual protected job to establish live evidence.

Operational references: [Azure AI Search HTTP status codes](https://learn.microsoft.com/rest/api/searchservice/http-status-codes), [GitHub deployment environments](https://docs.github.com/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), and [GitHub workflow concurrency](https://docs.github.com/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

## Cleanup

```bash
./liveks down --env liveks-combined
```

Type `delete liveks-combined`. A matching configuration digest, generated name, and remote ETag must prove each deletion. A pending object from an ambiguous PUT is deleted only when its live definition matches the expected payload and supplies an ETag. Cleanup sends requests in dependency order:

1. combined KB with `2026-05-01-preview`,
2. MCP Server KS with `2026-05-01-preview`,
3. Search Index KS with `2026-04-01`,
4. read the existing index with `2026-04-01`.

Require `search-index-preserved=pass`. No Fabric or Azure OpenAI delete request exists in this path. A missing or mismatched lock preserves every object and returns `cleanup-incomplete`.

## Failure Signals

| Signal | Meaning |
| --- | --- |
| `environment-lock=fail` | Another ledger owns one or more generated names. |
| `*-name=fail` | An unowned Search object already uses that name. |
| `openai-runtime-access=unknown` | The Search managed identity grant is not proved until retrieve. |
| HTTP `401` or `403` | Check Search permissions and Search managed identity access to Azure OpenAI. |
| HTTP `402` | Review the Search knowledge retrieval billing plan with the service owner. |
| HTTP `206` | A source partially failed; inspect protected activity errors locally. |
| HTTP `502` | Every selected source, or one required source, failed. |

## Microsoft Sources Of Truth

- [Create a Search Index Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index)
- [Create an MCP Server Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
- [Create a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [Query a Knowledge Base using retrieve or MCP](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
- [Use role-based access in Azure AI Search](https://learn.microsoft.com/azure/search/search-security-rbac)
