# Offline Replay

Offline replay exposes the Foundry IQ retrieve response contract without Azure resources, tenant access, Fabric, network calls, or package installation.

## CLI

```bash
./liveks try
./liveks try --sample mcp
./liveks try --sample fabric
./liveks try --sample combined --details
```

The default combined replay prints the answer before trace details. `--details` expands `activity`, `references`, and source-specific `sourceData`.

## Browser

[Open the combined replay](https://microsoft.github.io/azure-ai-search-foundry-iq-live-knowledge-sources/demo/?demo=combined){ .md-button .md-button--primary }

GitHub Pages has no server-side API, so the app labels the result `offline-replay` and loads canonical JSON fixtures from the site. An Azure deployment uses the same interface and calls the managed API first.

## Evidence To Inspect

For MCP Server KS:

- `activity[*].type == "mcpServer"`
- `toolName` or `mcpServerArguments.toolName`
- MCP references with `sourceData`

For Fabric Ontology KS:

- `activity[*].type == "fabricOntology"`
- `fabricOntologyArguments.search`
- `sourceData.fabricAnswer`
- `sourceData.fabricRawData`

The three canonical fixtures live under `samples/responses/`. The CLI, Pages build, and managed API all reuse these files to prevent demo drift.

## Boundary

The responses use synthetic Airline Ops data and demonstrate trace shape and teaching flow. They do not prove that Azure AI Search called Microsoft Learn MCP, that a Fabric GraphModel was ready, or that delegated Fabric authorization worked. Use `liveks verify` and live E2E reports for those claims.
