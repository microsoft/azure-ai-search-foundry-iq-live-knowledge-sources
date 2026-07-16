# Foundry IQ Live Knowledge Sources

Deploy and inspect MCP Server and Fabric Ontology Knowledge Sources through one Foundry IQ Knowledge Base, with evidence showing which source answered.

[Open the combined trace demo](https://microsoft.github.io/azure-ai-search-foundry-iq-live-knowledge-sources/demo/?demo=combined){ .md-button .md-button--primary }
[Start the runbook](runbook.md){ .md-button }

## First Run

No Azure subscription, tenant, Fabric workspace, or key is required:

```bash
git clone --depth 1 https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources.git
cd azure-ai-search-foundry-iq-live-knowledge-sources
./liveks try
```

The command prints the combined answer first and then identifies the MCP and Fabric evidence. Use `./liveks try --details` for the full `activity`, `references`, and `sourceData` trace.

## From Replay To Live

```bash
./liveks bootstrap
./liveks init --profile mcp-only --env liveks-mcp
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
```

The YAML ledger is written to ignored `.liveks/liveks-mcp.yaml`. `plan` performs local and read-only cloud checks; `up` previews changes and asks for explicit confirmation before provisioning.

| Profile | Reader state | First success signal |
| --- | --- | --- |
| `offline` | I want to understand the evidence contract now. | Answer plus MCP and Fabric source badges. |
| `mcp-only` | I want the fastest live Knowledge Source validation. | Retrieve evidence names `microsoft_docs_search`. |
| `byo-fabric` | I have a Fabric workspace and ontology. | Separate checks prove Fabric and MCP; the combined KB returns planner-selected evidence. |
| `full` | I need a greenfield platform demo. | Generated Fabric GraphModel, both KS paths, app, and cleanup pass. |

The safe default progression is `offline -> mcp-only -> byo-fabric`. Use `full` only after checking Fabric quota, cost, tenant settings, and cleanup expectations.

## Composition Model

![Live Knowledge Sources Architecture](assets/live-knowledge-sources-architecture.svg)

One question is routed through a Foundry IQ Knowledge Base to several live Knowledge Sources. The final answer is accompanied by:

- `activity`: which source and tool ran,
- `references`: what evidence was returned,
- `sourceData`: source-specific evidence for audit and citation handling.

The app and CLI replay use the same canonical response fixtures as the serverless API. Pages runs in clearly labeled offline replay mode; an Azure deployment switches the same interface to live retrieval.

## Manual Map

| Task | Page |
| --- | --- |
| Run the complete lifecycle | [Execution Runbook](runbook.md) |
| Choose a profile | [Choose a Pattern](02-choose-a-pattern.md) |
| Understand commands and exit codes | [LiveKS CLI](20-liveks-cli.md) |
| Manage YAML and secrets | [Configuration](21-configuration.md) |
| Deploy and clean up | [One-Command Deployment](10-one-command-deployment.md) |
| Connect existing Fabric | [BYO Fabric Validation](11-fabric-live-byo-validation.md) |
| Diagnose failures | [Troubleshooting](07-troubleshooting.md) |
| Review safety boundaries | [Security and Governance](06-security-governance.md) |

!!! note "Public preview"
    Azure AI Search Knowledge Source APIs are pinned to `2026-05-01-preview`. Use Microsoft Learn as the source of truth when preview behavior changes. This accelerator packages runnable configuration, deployment, samples, notebooks, and evidence around those APIs.

## Official Microsoft Manuals

| Need | Manual |
| --- | --- |
| Agentic retrieval | [Agentic Retrieval Overview](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview) |
| Knowledge Sources | [Knowledge Source Overview](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-overview) |
| MCP Server KS | [Create an MCP Server knowledge source](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-mcp-server) |
| Fabric Ontology KS | [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-fabric-ontology) |
| Knowledge Base | [Create a Knowledge Base](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-knowledge-base) |
| Retrieve | [Query a Knowledge Base](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-retrieve) |

Do not publish tenant IDs, keys, tokens, raw live responses, generated reports, or private screenshots. Share sanitized source names, counts, statuses, and cleanup evidence.
