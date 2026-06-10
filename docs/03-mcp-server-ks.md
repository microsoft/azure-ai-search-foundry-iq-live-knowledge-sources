# MCP Server Knowledge Source

Primary manual: https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server

## What It Demonstrates

MCP Server KS lets Azure AI Search invoke explicitly allowed tools from a compatible remote HTTPS MCP server during Knowledge Base retrieval.

## Key Design Points

- The MCP server must be reachable over HTTPS.
- Tool names must be explicitly listed.
- Tool output parsing must be configured.
- Long-running tools can need higher `maxRuntimeInSeconds`.
- Per-request credentials should use query-time header passthrough.
- Remote MCP servers must be vetted before enterprise use.

## Quickstart Source

The first sample uses:

```text
https://learn.microsoft.com/api/mcp
```

This keeps the first run reproducible without tenant-specific MCP infrastructure.

