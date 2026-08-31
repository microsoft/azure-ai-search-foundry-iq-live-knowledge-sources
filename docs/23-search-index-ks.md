# Stable Search Index Knowledge Source

Use this profile when an Azure AI Search service already contains an index that is ready for agentic retrieval. LiveKS reuses that service and index, creates only a Search Index Knowledge Source and a minimal extractive Knowledge Base, proves a real retrieve call, and then deletes only those two generated objects.

This lane uses the generally available `2026-04-01` REST contract. It does not deploy the demo app, Azure OpenAI, MCP Server KS, Fabric Ontology KS, or any Azure resource group.

## 1. Check The Existing Index

The index must:

- be on the Search service where the Knowledge Source and Knowledge Base will be created,
- contain searchable text or vector content,
- have a semantic configuration,
- expose every configured `search_fields` field as searchable,
- expose every configured `source_data_fields` field as retrievable.

The signed-in identity needs **Search Service Contributor** to inspect and create the Knowledge Source and Knowledge Base, plus **Search Index Data Reader** to run retrieve. LiveKS follows Microsoft's keyless path, acquires a short-lived Azure AI Search bearer token from Azure CLI, and never asks for, prints, or persists an admin key or bearer token.

Agentic retrieval is usage-billed. Search services start on the free plan with a monthly allowance; after that allowance is consumed, requests that require paid usage can return a payment-required error. An Owner or Contributor can deliberately select the Standard knowledge retrieval plan under **Settings > Premium features**. LiveKS reports the failure but never changes this management-plane billing setting.

## 2. Create The Ledger

```bash
./liveks bootstrap
./liveks init --profile search-index --env liveks-index
```

Edit the ignored `.liveks/liveks-index.yaml`:

```yaml
version: 2
profile: search-index
environment: liveks-index
search:
  endpoint: https://<search-service>.search.windows.net
  index_name: <existing-index-name>
  semantic_configuration_name: <semantic-configuration-name>
  search_fields:
    - content
  source_data_fields:
    - id
    - title
```

`search_fields` and `source_data_fields` can be empty when the Knowledge Source should use the index defaults. Unknown fields, duplicate list values, an HTTP endpoint, a preview API override, or a missing required value fails before any write.

The generated object names are derived from the environment:

```text
liveks-index-search-index-ks
liveks-index-search-index-kb
```

Override `search.index_knowledge_source_name` or `search.index_knowledge_base_name` only when a deliberate naming convention requires it. LiveKS refuses to overwrite an object with the same name unless the matching environment lock already proves ownership.

## 3. Sign In And Inspect

```bash
az login --tenant <tenant-guid>
./liveks doctor --env liveks-index
```

Expected checks include:

```text
[PASS] azure-login: Azure CLI account is active
[PASS] search-auth: A transient Azure AI Search bearer token was acquired.
[PASS] search-index: The existing Search index is readable.
[PASS] semantic-configuration: Configured semantic configuration exists.
[PASS] search-fields: Configured search fields exist and are searchable.
[PASS] source-data-fields: Configured source-data fields exist and are retrievable.
```

Representative failures are explicit:

```text
[FAIL] semantic-configuration: Configured semantic configuration was not found on the index.
[FAIL] search-fields: One or more configured search fields are missing or not searchable.
```

No endpoint, token, raw index definition, or document content is included in these messages.

An HTTP `402` during retrieve means the free agentic retrieval allowance is unavailable or exhausted and the service hasn't opted into Standard knowledge retrieval billing. Review the billing plan with the service owner; do not treat it as a payload or index failure.

## 4. Plan Without Mutation

```bash
./liveks plan --env liveks-index
```

The plan:

1. reruns the read-only index checks,
2. serializes the stable `searchIndex` Knowledge Source payload,
3. serializes a Knowledge Base without models, answer synthesis, or configurable reasoning,
4. serializes the stable `intents` retrieve request,
5. checks generated names for unowned collisions,
6. writes ignored plan and ownership artifacts.

It does not run Bicep, `azd`, app builds, `PUT`, or `DELETE`.

## 5. Create And Verify

```bash
./liveks up \
  --env liveks-index \
  --query "<question answerable from the existing index>" \
  --expect-term "<known non-sensitive term>"
```

Review the two generated objects and the reuse ownership statement, then type:

```text
create liveks-index
```

`up` journals each pending name before its conditional PUT, records the returned ETag, creates the Knowledge Source before the Knowledge Base, and runs a stable extractive retrieve with the supplied content assertion. A partial or ambiguous failure remains in the ignored lock for exact-definition reconciliation. An unchanged owned object is reused without another PUT; definition changes require cleanup and recreation. Every delete requires the recorded ETag, so a replaced object is preserved.

Repeat verification with a non-sensitive query and known fact from the index:

```bash
./liveks verify \
  --env liveks-index \
  --query "<question answerable from the existing index>" \
  --expect-term "<known non-sensitive term>" \
  --format json
```

Acceptance requires:

- the existing index, generated Knowledge Source, and generated Knowledge Base are readable,
- the Knowledge Source still names the configured index and semantic configuration,
- the Knowledge Base references the generated source and contains no preview-only properties,
- retrieve returns extracted text plus `searchIndex` activity or references,
- every supplied expected term is found.

The ignored verify report stores only normalized messages and expected-term counts. It does not store the query, expected terms, extracted content, endpoint, or bearer token.

## 6. Reproduce A Controlled Failure

Use an expected term that is known to be absent:

```bash
./liveks verify \
  --env liveks-index \
  --query "<same non-sensitive question>" \
  --expect-term "term-that-is-not-present"
```

Expected result:

```text
[FAIL] grounding-content: Extracted content matched 0/1 expected term(s).
```

This proves that a transport success cannot be mistaken for content acceptance.

## 7. Clean Up Without Deleting The Index

```bash
./liveks down --env liveks-index
```

Type `delete liveks-index`. Cleanup deletes the recorded Knowledge Base first and the recorded Knowledge Source second. It never sends a delete request for the Search service or index, and it finishes by requiring:

```text
[PASS] search-index-preserved: The existing Search index remains readable after cleanup.
```

If the lock is missing, mismatched, invalid, or lacks an ETag that can be reconciled to a pending exact definition, cleanup returns `cleanup-incomplete` and preserves the object for manual review.

## Stable Boundary

The stable lane intentionally uses:

- `2026-04-01`,
- `kind: searchIndex`,
- `intents` input,
- minimal extractive retrieval,
- Microsoft Entra bearer authentication,
- BYO ownership for the Search service and index.

Use `mcp-search-index` to keep this GA Search Index KS contract while attaching it to a preview MCP Server KS and combined Knowledge Base. Use `mcp-only`, `byo-fabric`, or `full` when the accelerator should provision the preview stack. The preview objects and retrieve calls remain pinned to `2026-05-01-preview`.

## Microsoft Sources Of Truth

- [Create a Search Index Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index)
- [Create a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [Query a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
- [Create an index for agentic retrieval](https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-index)
- [Use role-based access in Azure AI Search](https://learn.microsoft.com/azure/search/search-security-rbac)
- [Enable or disable agentic retrieval billing](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-enable-disable)
- [Migrate agentic retrieval code to the latest version](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate)
