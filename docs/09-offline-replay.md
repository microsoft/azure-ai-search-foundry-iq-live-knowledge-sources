# Offline Replay

Offline replay exposes the Foundry IQ retrieve response contract without Azure resources, tenant access, Fabric, network calls, or package installation.

## CLI

```bash
./liveks try --evidence-out .deployment/first-run-evidence.json
./liveks try --sample mcp
./liveks try --sample fabric
./liveks try --sample combined --details
```

The default combined replay prints the answer before trace details and fails unless all four manifest assertions pass: known facts, required activity types, required reference types, and the source identity plus `sourceData` contract. `--details` expands `activity`, `references`, and source-specific `sourceData` only on a passing synthetic replay. Failure output is redacted.

The aliases resolve to versioned scenario IDs:

| Alias | Scenario |
| --- | --- |
| `mcp` | `microsoft-learn-mcp.guidance-replay` |
| `fabric` | `airline-ops.fabric-exposure-replay` |
| `combined` | `airline-ops.combined-guidance-replay` |

## Evidence Capsule

`--evidence-out` writes a machine-readable, ignored capsule for the exact first-success command. It includes:

- scenario and pack IDs/versions,
- repository revision and runtime,
- manifest and fixture paths plus SHA-256 digests,
- activity and reference counts,
- observed source types and sourceData count,
- assertion IDs/status, profile, ownership class, cleanup expectation, and the explicit `offline-replay` boundary.

The capsule excludes the answer, query, expected terms, raw response, source identities, sourceData, resource identifiers, endpoints, tenant values, and credentials. The `Validate` workflow validates all packs, runs every case, and uploads the default `first-success-evidence` artifact after the local gate passes.

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

The three canonical fixtures live under `samples/responses/`. Their scenario manifests pin fixture digests; the CLI, Pages build, and managed API reuse the same files to prevent demo drift.

## Boundary

The Airline Ops responses use one clearly labeled synthetic example domain; the MCP guidance pack is domain-neutral. They do not prove that Azure AI Search called Microsoft Learn MCP, that a Fabric GraphModel was ready, or that delegated Fabric authorization worked. Use `liveks verify` and live E2E reports for those claims. The current protected canary cannot consume these source combinations, so the protected scenario adapter is explicitly not implemented and **NOT RUN**. See [Scenario Packs](18-scenario-packs.md).
