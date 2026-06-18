# Overview

This accelerator focuses on two live, query-time Knowledge Source patterns for Azure AI Search and Foundry IQ:

- **MCP Server Knowledge Source** for remote HTTPS MCP tools.
- **Fabric Ontology Knowledge Source** for governed business semantics in Microsoft Fabric.

Classic retrieval samples often begin by indexing content. This repo shows another pattern: a Knowledge Base can call live sources during retrieval, return answer text, and expose trace evidence through `activity`, `references`, and source-specific data.

## What This Repo Is

```text
Reusable sample accelerator
  -> deployment modes
  -> REST samples
  -> notebooks
  -> demo app
  -> offline replay
  -> reviewer evidence and safe-claim guidance
```

The repo is designed for field demos, customer workshops, private product review, blog preparation, and official-sample readiness work. It is not a production reference architecture.

## The Two Knowledge Source Patterns

| Pattern | What it does | First place to look |
| --- | --- | --- |
| MCP Server KS | Calls explicitly allowed tools on a remote HTTPS MCP server at retrieve time. | [MCP Server Knowledge Source](03-mcp-server-ks.md) |
| Fabric Ontology KS | Grounds retrieval in Fabric ontology entities, relationships, and governed semantic definitions. | [Fabric Ontology Knowledge Source](04-fabric-ontology-ks.md) |
| Combined KB | Shows how one Knowledge Base can route across both live source types. | [Combined Knowledge Base Routing](05-combined-kb-routing.md) |

## Deployment Modes

Start with `mcp-only` unless you already have Fabric workspace and ontology IDs.

| Mode | Purpose | Best for |
| --- | --- | --- |
| `mcp-only` | Deploy Azure AI Search, Azure OpenAI, Microsoft Learn MCP Server KS, MCP-only KB, Search index, and demo app. | First run and low-friction validation. |
| `byo-fabric` | Deploy the Azure side and connect an existing Fabric workspace and ontology. | Customer or field demos with existing Fabric semantic assets. |
| `full` | Create sample Fabric assets, then deploy Azure AI Search, both Knowledge Source paths, and the demo app. | Greenfield platform story when quota and tenant settings are ready. |

For command examples, see [Choose a Pattern](02-choose-a-pattern.md) and [One-Command Demo Deployment](10-one-command-deployment.md).

## Documentation Map

Use this map when you are reviewing the repo or deciding what to read next.

| Need | Read |
| --- | --- |
| Understand the architecture | [Architecture](01-architecture.md) |
| Pick the right path | [Choose a Pattern](02-choose-a-pattern.md) |
| Learn MCP Server KS | [MCP Server Knowledge Source](03-mcp-server-ks.md) |
| Learn Fabric Ontology KS | [Fabric Ontology Knowledge Source](04-fabric-ontology-ks.md) |
| Understand combined routing | [Combined Knowledge Base Routing](05-combined-kb-routing.md) |
| Review security posture | [Security and Governance](06-security-governance.md) |
| Debug a run | [Troubleshooting](07-troubleshooting.md) |
| Pick test questions | [Test Queries And Expected Traces](08-test-queries.md) |
| Inspect traces without live resources | [Offline Replay](09-offline-replay.md) |
| Deploy the app and resources | [One-Command Demo Deployment](10-one-command-deployment.md) |
| Connect existing Fabric assets | [Fabric Live BYO Validation](11-fabric-live-byo-validation.md) |
| Prove a run for reviewers | [Reviewer Evidence Guide](12-reviewer-evidence.md) |
| Avoid unsafe preview claims | [Public Preview Limitations and Caveats](13-public-preview-limitations.md) |
| Prepare for broader review | [Release Readiness Checklist](14-release-readiness-checklist.md) |
| Promote to another repository | [Repository Promotion Guide](15-repository-promotion.md) |
| Run a short demo | [Demo Walkthrough](16-demo-walkthrough.md) |
| Prepare blog or presentation wording | [Storyline And Safe Claims](17-storyline-and-safe-claims.md) |

## Validation Loop

Every path in this repo should be reviewed through the same loop:

```text
Create Knowledge Source
  -> attach it to a Knowledge Base
    -> retrieve with a test question
      -> inspect activity, references, and sourceData
        -> record sanitized evidence
```

The final answer alone is not enough. Good evidence shows which source was selected, what live source was called, and whether cleanup completed when deployment behavior is being claimed.

## First-Time Reader Path

1. Read the mode selector in [README.md](../README.md).
2. Run:

   ```bash
   bash scripts/validate-local.sh
   ```

3. Start with `mcp-only`.
4. Open the demo app and inspect source trace evidence.
5. Move to `byo-fabric` when Fabric workspace and ontology IDs are ready.
6. Use `full` only when Fabric quota, tenant settings, region, and delegated auth expectations are clear.

## Evidence And Safety

Generated outputs stay under ignored paths:

```text
.deployment/
deployments/
scratch/
```

Do not commit tenant IDs, tokens, keys, generated reports, private service URLs, local screenshots, or internal planning notes.

Before sharing claims in a blog, presentation, or customer-facing demo, review:

- [Reviewer Evidence Guide](12-reviewer-evidence.md)
- [Public Preview Limitations and Caveats](13-public-preview-limitations.md)
- [Storyline And Safe Claims](17-storyline-and-safe-claims.md)
