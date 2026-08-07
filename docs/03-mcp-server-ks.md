# MCP Server Knowledge Source

Primary manual: https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server

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

## Notebook Walkthrough

Use `notebooks/01-mcp-server-ks-quickstart.ipynb` for the guided MCP path. It builds the MCP Knowledge Source payload, creates an MCP-only Knowledge Base payload, optionally performs live retrieve, and inspects an offline MCP trace.

## First Live Success With LiveKS

Use `mcp-only` for the smallest end-to-end live deployment. It uses the public Microsoft Learn MCP endpoint, so no Fabric workspace or ontology is required. The REST files in the next section remain the payload-level path for manual API inspection.

Prerequisites are Python 3.11 or newer, Azure Developer CLI 1.27.0 or newer, Azure CLI, Node.js 22 or newer with npm, and permission to create the Azure resources listed by the plan.

```bash
./liveks try --sample mcp
./liveks bootstrap
az login --tenant <tenant-guid>
azd auth login
./liveks init --profile mcp-only --env liveks-mcp
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
./liveks verify --env liveks-mcp --format json
```

The generated `.liveks/liveks-mcp.yaml` ledger is ignored and the checked-in profile defaults are otherwise runnable. `doctor` and `plan` must contain no failed checks. Review the resource list, estimated duration, and cost before `up`; the command runs an ARM preview and then requires the exact phrase `create liveks-mcp` before provisioning.

Accept the first live pass only when `verify` reports all of these checks as `pass`:

| Check | What it proves |
| --- | --- |
| `resource-group` | The selected deployment environment resolves to an existing Azure resource group. |
| `app-status` | The deployed app API is reachable. |
| `mcp-retrieve` | A live retrieve returned `mcpServer` activity or reference evidence. |
| `knowledge-base-mcp` | The native Knowledge Base MCP endpoint completed tool discovery, tool execution, and the profile's known-content check. |

For an explicit native MCP content check, run:

```bash
./liveks mcp \
  --env liveks-mcp \
  --query "What must be configured for an Azure AI Search MCP Server knowledge source?" \
  --expect-term "Azure AI Search"
```

Require `tools-list=pass`, `tools-call=pass`, and `grounding-content=pass`. The command persists counts only under ignored `deployments/liveks-mcp/`; it does not persist the query, response content, endpoint, key, or token.

The lifecycle boundary is explicit:

| Command | Boundary |
| --- | --- |
| `try`, `bootstrap`, `init` | Local only. Bootstrap installs into ignored `.liveks/venv`; no cloud resources are created. |
| `doctor` | Local checks plus read-only Azure account, provider, and availability probes. |
| `plan` | Repeats doctor, builds Bicep and the app, and dry-runs payload generation. It does not select or change `azd env`, provision, or deploy. |
| `up` | Mutates cloud state only after preview and confirmation, then runs verification. |
| `verify`, `mcp` | Read/call only. They write sanitized reports under ignored paths. |
| `down` | Deletes generated assets after ownership checks. |

When the evaluation is complete:

```bash
./liveks down --env liveks-mcp
```

Require `resource-group-absent=pass`. See [LiveKS CLI](20-liveks-cli.md), [One-Command Deployment](10-one-command-deployment.md), and [Post-Deployment Tests](08-test-queries.md) for the complete command and evidence contracts.

## REST Payload Quickstart

Run these files in order:

```text
samples/rest/01-create-mcp-server-ks.http
samples/rest/02-create-mcp-only-kb.http
samples/rest/03-retrieve-mcp.http
```

The retrieve request asks for references, source data, and activity. A good first response should include:

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
