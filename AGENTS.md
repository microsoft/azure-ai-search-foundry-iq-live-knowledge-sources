# Agent Runbook

This repo is a public sample accelerator for Azure AI Search / Foundry IQ live Knowledge Sources. Use this file as the first stop when a coding agent is asked to inspect, run, validate, or modify the repo.

## Default Path

Use the safest path that matches the user's tenant state:

```text
offline -> mcp-only -> byo-fabric
```

- Start with offline replay unless the user explicitly asks for live Azure resources.
- Use `mcp-only` for the fastest live validation without Fabric.
- Use `byo-fabric` only when the user already has a Fabric workspace ID and ontology ID.
- Treat `full` as a maintainer or greenfield demo path. It can create Fabric capacity and sample Fabric assets.

## First Commands

Inspect offline traces with no cloud resources:

```bash
python3 samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

Run the local validation gate:

```bash
bash scripts/validate-local.sh
```

Run agent-readable preflight:

```bash
python3 tools/doctor.py --format json
python3 tools/validate.py --profile offline --format json
```

## Profile Entry Points

- `profiles/offline.yaml`: learn the retrieve contract without Azure, Fabric, or tenant access.
- `profiles/mcp-only.yaml`: deploy and validate MCP Server Knowledge Source only.
- `profiles/byo-fabric.yaml`: connect an existing Fabric ontology to Azure AI Search.
- `profiles/semantic-join.yaml`: inspect combined MCP + Fabric trace behavior.

Use mode-specific env examples under `env/` when creating ignored local env files. Keep `.env.sample` as the full variable catalog.

## Public Sample Boundaries

Do not add or publish:

- internal Fabric ontology authoring steps,
- private preview instructions,
- tenant allowlisting processes,
- internal endpoints,
- real workspace IDs, ontology IDs, tenant IDs, tokens, API keys, customer data, raw live responses, or screenshots with sensitive values,
- Fabric MCP through MCP Server KS as the recommended path.

This repo can connect to an existing Fabric ontology. It should not teach private or internal Fabric ontology authoring flows.

## Source Of Truth

Azure AI Search Knowledge Source APIs are in public preview. Keep official Microsoft Learn docs as the source of truth for API behavior:

- Create an MCP Server knowledge source
- Create a Fabric Ontology knowledge source
- Create a knowledge base
- Query a knowledge base

When behavior differs between offline replay and live retrieval, state that offline replay only demonstrates trace shape.

## Safe Output Rules

- Generated logs, reports, env files, screenshots, and deployment summaries stay in ignored paths.
- Do not paste raw access tokens into issues, PRs, docs, screenshots, or final answers.
- Do not print full live retrieve responses if they may contain tenant-specific values.
- Prefer sanitized counts, status, and source names over raw payloads in public-facing summaries.

## Validation Expectations

Before proposing a public PR, run:

```bash
python3 tools/validate.py --profile offline --format json
bash scripts/validate-local.sh
```

For live deployment claims, use the matching deployment or E2E flow and summarize only sanitized evidence.
