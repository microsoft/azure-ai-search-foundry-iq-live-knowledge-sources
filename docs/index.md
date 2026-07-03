# Live Knowledge Sources Manual

This manual shows what this repo can run, which path to choose, and what to check after each command. It is designed to sit next to a terminal during a workshop, review, or demo rehearsal.

![Live Knowledge Sources Architecture](assets/live-knowledge-sources-architecture.svg)

!!! note "Source of truth"
    Azure AI Search Knowledge Source APIs are in public preview. Use the official Microsoft Learn articles as the source of truth when preview behavior changes. This repo adds runnable payloads, deployment scripts, notebooks, and offline traces around those docs.

## What This Repo Can Do

| Capability | What you run | What you learn |
| --- | --- | --- |
| Offline trace replay | `samples/python/inspect_retrieve_response.py` | The retrieve response shape: `activity`, `references`, and `sourceData`. |
| Local validation | `tools/validate.py` and `scripts/validate-local.sh` | Whether the repo, payloads, samples, docs, and app still line up. |
| MCP-only live path | `scripts/deploy.sh --mode mcp-only` | Azure AI Search can call a remote HTTPS MCP server at retrieve time. |
| BYO Fabric path | `scripts/deploy.sh --mode byo-fabric` | Azure AI Search can connect an existing Fabric ontology as a live Knowledge Source. |
| Full greenfield path | `scripts/deploy.sh --mode full` | The sample can create Azure resources and a small Fabric Airline Ops stack for end-to-end validation. |
| Combined trace inspection | Offline responses or a combined KB | One Knowledge Base can route across MCP Server KS and Fabric Ontology KS. |

## Choose The First Path

![Deployment modes](assets/deployment-modes.svg)

| Start here | Use when | Next page |
| --- | --- | --- |
| `offline` | You want to learn the trace contract with no cloud resources. | [Offline Replay](09-offline-replay.md) |
| `mcp-only` | You want the fastest live Azure AI Search validation without Fabric. | [MCP Server KS](03-mcp-server-ks.md) |
| `byo-fabric` | You already have a Fabric workspace ID and ontology ID. | [BYO Fabric Validation](11-fabric-live-byo-validation.md) |
| `full` | You are doing a greenfield demo and can create Fabric capacity and sample assets. | [One-Command Deployment](10-one-command-deployment.md) |

The safest default order is:

```text
offline -> mcp-only -> byo-fabric
```

Use `full` only when quota, tenant settings, cleanup expectations, and delegated auth behavior are clear.

## First Run

Start without Azure, Fabric, tenant access, or secrets:

```bash
python3 samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

Then run the local gate:

```bash
python3 tools/doctor.py --format json
python3 tools/validate.py --profile offline --format json
bash scripts/validate-local.sh
```

For the full sequence, follow the [Execution Runbook](runbook.md).

## Success Signals

| Path | Good first signal |
| --- | --- |
| Offline replay | Inspector prints `Activity`, `References`, and `Source Data Preview`. |
| Local validation | `tools/validate.py --profile offline` returns passing JSON. |
| MCP-only | Retrieve activity or references show `microsoft_docs_search`. |
| BYO Fabric | Fabric KS is created, and live retrieve works with delegated source authorization or falls back to a clear offline explanation. |
| Full | Fabric IDs are generated, KS/KB assets are created, app loads, retrieve evidence is recorded, and cleanup completes or reports manual follow-up. |

## Official Microsoft Manuals

| Need | Official manual |
| --- | --- |
| Understand agentic retrieval | [Agentic Retrieval Overview](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview) |
| Understand Knowledge Sources | [What is a Knowledge Source?](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-overview) |
| Create MCP Server KS | [Create an MCP Server knowledge source](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-mcp-server) |
| Create Fabric Ontology KS | [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-fabric-ontology) |
| Create a Knowledge Base | [Create a Knowledge Base](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-knowledge-base) |
| Query a Knowledge Base | [Query a Knowledge Base](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-retrieve) |
| Understand Fabric Ontology | [Microsoft Fabric Ontology overview](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview) |
| Maintain this site | [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/getting-started/) |

## Safety Boundary

Do not publish tenant IDs, service URLs, API keys, bearer tokens, raw live responses, generated deployment reports, or screenshots with sensitive values. Use sanitized counts, source names, and success signals when summarizing live runs.
