# MCP Server Knowledge Source

Official manual: [Create an MCP Server knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)

## What It Demonstrates

MCP Server KS lets Azure AI Search invoke explicitly allowed tools from a compatible remote HTTPS MCP server during Knowledge Base retrieval.

This repo starts with the public Microsoft Learn MCP server so the first run has no tenant-specific dependency:

```text
https://learn.microsoft.com/api/mcp
```

## Key Design Points

- The MCP server must be reachable over HTTPS.
- Tool names must be explicitly listed.
- Tool output parsing must be configured.
- Long-running tools can need higher `maxRuntimeInSeconds`.
- Per-request credentials should use query-time header passthrough.
- Remote MCP servers must be vetted before enterprise use.

## One MCP Execution Contract

Use `mcp-only` for the smallest end-to-end provisioned deployment. Use `mcp-search-index` when the Search service, agentic-ready index, and Azure OpenAI deployment already exist and only the two KS objects plus combined KB should be created. Both use the public Microsoft Learn MCP endpoint, so no Fabric workspace or ontology is required. The sequence below moves from local payload evidence to live source evidence; `up` is the first command that mutates cloud state.

Use [Codespaces First Live](15-codespaces-first-live.md) when you want the supported Python, Node.js, Azure CLI, Bicep, and Azure Developer CLI versions preinstalled. Container creation does not authenticate or provision.

Before a live run, review [Public Preview Limitations and Caveats](13-public-preview-limitations.md) alongside the official manual.

### 1. Replay And Inspect The Payload

Run from the repository root:

```bash
./liveks try --sample mcp --details
./liveks bootstrap
python3 samples/python/build_payloads.py
PATH="$PWD/.liveks/venv/bin:$PATH" bash scripts/validate-local.sh --no-color
```

The replay is checked-in response-shape evidence, not a live call. The payload generator prints representative JSON with safe placeholders and makes no cloud request. Inspect these two top-level members in its output:

| JSON path | Expected value |
| --- | --- |
| `mcp.name` | `microsoft-learn-mcp-ks` |
| `mcp.kind` | `mcpServer` |
| `mcp.mcpServerParameters.serverURL` | `https://learn.microsoft.com/api/mcp` |
| `mcp.mcpServerParameters.tools[0].name` | `microsoft_docs_search` |
| `mcpOnlyKnowledgeBase.name` | `live-knowledge-sources-mcp-kb` |
| `mcpOnlyKnowledgeBase.knowledgeSources[0].name` | `microsoft-learn-mcp-ks` |

The local gate uses the dependency installed by `bootstrap`. Require `PASS Python contract tests`, `PASS Sample payload generation`, and a final `Local validation: PASS`. The pull-request [Validate workflow](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/.github/workflows/validate.yml) installs the same pinned dependency and runs the same gate on Python 3.11 and Node.js 22 with `contents: read` permission.

The generator, REST samples, and live postprovision path use or mirror the same `src/ks_factory` payload builders. They have different evidence boundaries: generated JSON proves local shape, while live success requires activity or reference evidence from Azure AI Search.

### 2. Resolve And Plan The Deployment

Prerequisites are Python 3.11 or newer, Azure Developer CLI 1.27.0 or newer, Azure CLI, Node.js 22 or newer with npm, and permission to create the Azure resources listed by the plan.

```bash
./liveks init --profile mcp-only --env liveks-mcp
az login --tenant <tenant-guid>
azd auth login
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
```

The generated `.liveks/liveks-mcp.yaml` ledger is ignored and the checked-in profile defaults are otherwise runnable. `doctor` and `plan` must contain no failed checks. In the plan, require `bicep-build=pass`, `payload-dry-run=pass`, `app-install=pass`, and `app-build=pass`. The payload dry-run resolves the selected environment through `scripts/postprovision.py`; it does not select or change `azd env`, provision, or deploy.

### 3. Deploy And Prove The Live Source

Review the resource list, estimated duration, and cost before `up`. The command runs an ARM preview and then requires the exact phrase `create liveks-mcp` before provisioning.

```bash
./liveks up --env liveks-mcp
./liveks verify --env liveks-mcp --format json
./liveks mcp \
  --env liveks-mcp \
  --query "What must be configured for an Azure AI Search MCP Server knowledge source?" \
  --expect-term "Azure AI Search"
```

Use one acceptance table for the complete path:

| Stage | Required signal | What it proves |
| --- | --- | --- |
| Generated payload | The six expected fields above are present. | The representative MCP KS and MCP-only KB shape is internally aligned. |
| Local gate | `Python contract tests`, `Sample payload generation`, and the final gate pass. | Builders, generated output, and the repository's local contracts execute together. |
| Plan | No failed checks and `payload-dry-run=pass`. | Resolved deployment settings can produce the postprovision payload without cloud mutation. |
| Retrieve | `resource-group=pass`, `app-status=pass`, and `mcp-retrieve=pass`. | The deployment exists and a live retrieve returned `mcpServer` activity or reference evidence. |
| Knowledge Base MCP | `knowledge-base-mcp=pass`, then `tools-list=pass`, `tools-call=pass`, and `grounding-content=pass`. | The native MCP endpoint discovered and called `knowledge_base_retrieve`, and returned the expected non-sensitive content term. |
| Cleanup | `resource-group-absent=pass`. | Generated Azure resources for this environment were released. |

The explicit `mcp` command persists counts only under ignored `deployments/liveks-mcp/`; it does not persist the query, response content, endpoint, key, or token.

For the existing-index composition path, follow [MCP + Search Index Knowledge Base](24-mcp-search-index-kb.md). Its verifier uses the combined KB for an index-only retrieve, an MCP-only retrieve, and then a combined planner query. This ordering is the source proof; native MCP output alone cannot identify routing.

When the evaluation is complete:

```bash
./liveks down --env liveks-mcp
```

See [LiveKS CLI](20-liveks-cli.md), [One-Command Deployment](10-one-command-deployment.md), and [Post-Deployment Tests](08-test-queries.md) for the complete command and evidence contracts.

## Notebook Walkthrough

Use `notebooks/01-mcp-server-ks-quickstart.ipynb` after the contract above when you want a guided payload walkthrough. It builds the MCP Knowledge Source payload, creates an MCP-only Knowledge Base payload, optionally performs live retrieve, and inspects an offline MCP trace.

## Manual REST Inspection

These files expose the raw API requests for manual inspection. They are not a separate success contract; use the live acceptance signals above.

Run the files in order:

```text
samples/rest/01-create-mcp-server-ks.http
samples/rest/02-create-mcp-only-kb.http
samples/rest/03-retrieve-mcp.http
```

The generated `mcp` and `mcpOnlyKnowledgeBase` members match the first two request bodies after replacing the REST placeholders. The retrieve request asks for references, source data, and activity. A good first response should include:

- an `activity` entry with `type` set to `mcpServer`,
- `knowledgeSourceName` set to `microsoft-learn-mcp-ks`,
- `toolName` set to `microsoft_docs_search`,
- one or more `references` entries with `type` set to `mcpServer`.

## Tool Allowlist

The Knowledge Source does not automatically allow every tool exposed by the remote MCP server. List only the tools the Knowledge Base is allowed to call:

```json
{
  "name": "microsoft_docs_search",
  "outputParsing": {
    "kind": "auto"
  },
  "inclusionMode": "reranked",
  "maxOutputTokens": 1000
}
```

## Output Parsing

Start with `auto` for simple validation. Use more specific parsing once you control the remote server response shape:

| Mode | Use when |
| --- | --- |
| `auto` | You want Azure AI Search to infer rankable content from the tool output |
| `json` | The tool returns predictable JSON and documents live at a known JSONPath |
| `split` | The tool returns long text, Markdown, or HTML that should be chunked |
| `none` | You want the raw output passed through without additional parsing |

## Query-Time Headers

For MCP servers that require per-user credentials or rotating credentials, use query-time header passthrough instead of storing user tokens in the Knowledge Source.

The control header format is:

```http
<knowledge-source-name>-header-name: Authorization
<knowledge-source-name>-header-value: Bearer <mcp-server-access-token>
```

Static service credentials can use stored headers, but do not use stored headers for user-specific tokens.

## Validation Checklist

- The MCP endpoint is HTTPS and reachable from Azure AI Search.
- The tool name matches the remote MCP server exactly.
- `maxRuntimeInSeconds` gives the tool enough time to respond.
- `includeActivity` is true while validating.
- `includeReferences` and `includeReferenceSourceData` are true while validating.
- Any external system terms, data movement, and compliance boundaries are reviewed before customer use.
