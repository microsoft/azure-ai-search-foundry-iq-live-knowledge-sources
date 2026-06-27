# Repo Boundaries

This repo is a public sample accelerator for Azure AI Search / Foundry IQ live Knowledge Sources. It is not a production reference architecture and it is not a Fabric ontology authoring guide.

## In Scope

- Synthetic Airline Operations sample data.
- Offline retrieve responses that demonstrate the trace contract.
- MCP Server Knowledge Source payloads and walkthroughs.
- BYO Fabric Ontology Knowledge Source validation.
- Combined Knowledge Base routing examples.
- Deployment automation for Azure AI Search, Azure OpenAI, app hosting, and sample Knowledge Source assets.
- Public-preview caveats and validation guidance.

## Out Of Scope

- Internal Fabric ontology authoring steps.
- Private preview setup, allowlisting, or unpublished tenant instructions.
- Customer data, real tenant IDs, real workspace IDs, real ontology IDs, API keys, bearer tokens, raw live responses, or screenshots with sensitive values.
- Recommending Fabric MCP through MCP Server Knowledge Source as the primary path. Use native Fabric Ontology Knowledge Source for the Fabric path.
- Production hardening claims that are not backed by explicit evidence.

## Agent Rules

- Start with offline replay unless the user asks for live resources.
- Prefer `mcp-only` before Fabric paths.
- Use `byo-fabric` only when existing Fabric workspace and ontology IDs are available.
- Treat `full` as maintainer/demo-oriented because it can create Fabric capacity and sample Fabric assets.
- Keep generated reports and logs in ignored paths.
- Summarize live evidence with sanitized status and counts, not raw tenant payloads.

## Evidence Standards

Use the right evidence for the claim:

- Repo shape: `bash scripts/validate-local.sh`
- Offline trace shape: `samples/responses/*.sample.json`
- Route expectations: `evals/expected_routes.yaml`
- Live MCP path: `mcp-only` deployment or E2E evidence
- Live Fabric path: `byo-fabric` deployment or E2E evidence with delegated source authorization
- Greenfield demo path: `full` mode evidence plus cleanup evidence

Offline replay is useful learning evidence. It is not proof of live Fabric retrieval.
