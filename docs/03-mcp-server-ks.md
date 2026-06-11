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

## Quickstart

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
