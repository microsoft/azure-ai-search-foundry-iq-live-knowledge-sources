# Choose a Pattern

![Deployment modes](assets/deployment-modes.svg)

Start with offline replay, then choose the smallest live profile that proves the behavior you need.

| Profile | Use when | Main risk or prerequisite | Success signal |
| --- | --- | --- | --- |
| `offline` | You need to inspect the response contract immediately. | It proves shape, not live retrieval. | Answer plus MCP and Fabric trace evidence. |
| `search-index` | An agentic-ready Search index already exists and you want the lowest-risk live path. | Search data-plane permissions and a semantic configuration. | Stable retrieve returns extracted text and `searchIndex` evidence; cleanup preserves the index. |
| `mcp-search-index` | You want preview MCP routing over an existing Search service and index. | Existing Azure OpenAI deployment plus Search managed identity model access. | Independent Search and MCP checks pass before combined evidence; cleanup preserves all reused assets. |
| `mcp-only` | You want the first preview live path without Fabric. | Azure AI Search preview and model availability. | `microsoft_docs_search` appears in activity or references. |
| `byo-fabric` | Existing governed Fabric semantics should ground retrieval. | Workspace/ontology IDs and delegated user authorization. | Separate checks prove both KS paths; the combined KB shows planner-selected routing. |
| `full` | A greenfield platform demo must create everything. | Billable Fabric F2 quota, longer duration, tenant settings, cleanup. | Fabric GraphModel, both KS paths, app, and teardown pass. |

## Decision

Use `search-index` when an agentic-ready index already exists and stable extractive retrieval is enough. Upgrade that same service to `mcp-search-index` when an existing Azure OpenAI deployment and its Search managed identity grant are ready. Otherwise use `mcp-only` unless the answer to one of these is yes:

- Existing Fabric workspace and ontology IDs are ready: use `byo-fabric`.
- The audience must see Fabric sample creation from zero and quota is confirmed: use `full`.
- No cloud mutation should occur: remain on `offline`.

## Command Shapes

```bash
./liveks init --profile search-index --env liveks-index
# Add the existing endpoint, index, semantic configuration, and optional field lists.
./liveks plan --env liveks-index
./liveks up --env liveks-index
```

```bash
./liveks init --profile mcp-search-index --env liveks-combined
# Add the existing Search and Azure OpenAI deployment values.
./liveks plan --env liveks-combined
./liveks up --env liveks-combined --query "<index question>" --expect-term "<known term>"
```

```bash
./liveks init --profile mcp-only --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
```

```bash
./liveks init --profile byo-fabric --env liveks-byo
# Add fabric.workspace_id and fabric.ontology_id to .liveks/liveks-byo.yaml.
./liveks plan --env liveks-byo
./liveks up --env liveks-byo
```

```bash
./liveks init --profile full --env liveks-full
./liveks plan --env liveks-full
./liveks up --env liveks-full --accept-fabric-capacity
```

## Source Pattern

| Knowledge Source pattern | Sample entry point |
| --- | --- |
| Search Index KS | [Stable Search Index Knowledge Source](23-search-index-ks.md) |
| Search Index KS + MCP Server KS | [MCP + Search Index Knowledge Base](24-mcp-search-index-kb.md) |
| MCP Server KS | `samples/rest/01-create-mcp-server-ks.http` |
| Fabric Ontology KS | `samples/rest/04-create-fabric-ontology-ks.http` |
| Combined Knowledge Base | `samples/rest/05-create-combined-kb.http` |

The `mcp-search-index` verifier uses one combined Knowledge Base but supplies one source parameter at a time before the combined query. In any combined Knowledge Base, the returned `activity`, `references`, and `sourceData` are the evidence of what actually ran.
