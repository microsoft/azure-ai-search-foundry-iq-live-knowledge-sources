# Storyline And Safe Claims

Use this page when preparing a blog draft, conference demo, customer workshop, or private review summary. It turns the repo into a short public-safe story without over-claiming preview behavior.

## One-Line Story

```text
This accelerator packages two Azure AI Search public preview live Knowledge Sources into repeatable demo paths for MCP tools, Fabric ontologies, and combined trace inspection.
```

## Short Abstract

```text
Classic retrieval samples usually begin by indexing documents. Live Knowledge Sources add another path: a Knowledge Base can reach governed semantics and remote tools at retrieve time. This sample shows three repeatable deployment paths: mcp-only for quick MCP Server KS validation, byo-fabric for existing Fabric ontology assets, and full for the greenfield platform story that creates sample Fabric assets before connecting Azure AI Search.
```

## Audience Framing

| Audience | Lead with | Avoid leading with |
| --- | --- | --- |
| Field engineers | Repeatable demo and workshop paths. | Raw REST API details before the mode selector. |
| Product reviewers | Preview API boundaries, evidence, safe claims. | Star-count or marketing-first language. |
| Customer architects | Deployment modes, auth boundaries, trace evidence. | Full greenfield before quota and tenant settings are clear. |
| Blog readers | Why live Knowledge Sources matter and how to try `mcp-only`. | Internal validation history or private tenant details. |

## Message By Mode

| Mode | Safe message | Evidence needed before saying it live |
| --- | --- | --- |
| `mcp-only` | Fastest path to validate Azure AI Search MCP Server KS with Microsoft Learn MCP. | MCP KS exists, MCP-only KB exists, retrieve returns MCP activity or Microsoft Learn references. |
| `byo-fabric` | Primary live Fabric path for users who already have a Fabric workspace and ontology. | Fabric KS exists, combined KB includes it, live retrieve shows Fabric activity or source data when delegated auth is provided. |
| `full` | Greenfield platform story that creates sample Fabric assets before connecting Azure AI Search. | Fabric capacity/workspace/lakehouse/ontology/GraphModel setup completes, Azure deploy completes, app loads, cleanup evidence exists. |

## Claims You Can Use

Use these only when the matching evidence exists:

- "The sample includes three deployment modes: `mcp-only`, `byo-fabric`, and `full`."
- "MCP-only is the fastest first-run path because it does not require Fabric setup."
- "BYO Fabric is the safest live Fabric path when a workspace and ontology already exist."
- "Full mode is the greenfield platform story and depends on Fabric quota, tenant settings, and delegated auth."
- "The demo app shows live or offline source evidence through activity, references, and source-specific data."
- "Offline replay helps explain trace shape before live Fabric auth is configured."
- "Generated deployment reports and local screenshots stay under ignored paths."

## Claims To Avoid

Do not use these in README, blogs, presentations, or customer-facing demos:

- "Production-ready reference architecture."
- "Full mode works in every tenant."
- "Offline replay proves live Fabric retrieval."
- "A successful `azd up` proves Knowledge Source retrieve behavior."
- "Screenshots alone prove source selection."
- "MCP Server KS can attach local stdio MCP servers directly."
- "Fabric delegated auth is optional for live user-specific retrieval."

Use [Public Preview Limitations and Caveats](13-public-preview-limitations.md) as the final wording boundary.

## Blog Outline

Suggested title:

```text
Grounding Foundry IQ With Live Knowledge Sources: MCP Server KS, Fabric Ontology KS, and a Reusable Demo Pattern
```

Suggested flow:

1. Problem: enterprise agents need trusted live grounding, not only indexed documents.
2. New capability: Azure AI Search public preview live Knowledge Sources.
3. First path: MCP Server KS with Microsoft Learn MCP.
4. Second path: Fabric Ontology KS for governed semantic assets.
5. Combined path: one Knowledge Base pattern with inspectable `activity`, `references`, and source data.
6. Deployment modes: `mcp-only`, `byo-fabric`, `full`.
7. Evidence: local validation, E2E reports, app trace, notebooks, offline replay.
8. Caveats: preview API, Fabric quota, delegated auth, region/model availability.
9. Call to action: start with `mcp-only`, then move to `byo-fabric` or `full`.

## Presentation Flow

Use this when you have three to five minutes:

1. Show the README mode selector.
2. Open the app and point at **Current Demo Flow**.
3. Run or show MCP retrieve evidence.
4. Run or show Fabric live or offline replay evidence.
5. Show combined trace.
6. Close with evidence and caveats: validation gate, E2E reports, preview limitations.

For the longer app sequence, use [Demo Walkthrough](16-demo-walkthrough.md).

## Reviewer Ask

When asking PM or engineering reviewers for feedback, ask for specific wording review:

```text
Please review:
- Azure AI Search Knowledge Source terminology
- MCP Server KS request/response shape and trace wording
- Fabric Ontology KS setup and delegated source authorization wording
- deployment-mode clarity: mcp-only, byo-fabric, full
- public-preview caveats and safe claims
- whether any statement reads as production guidance instead of a preview sample
```

## Final Pre-Publish Check

Before publishing a blog or external presentation:

```text
[ ] Learn manual links are current
[ ] API version is stated as 2026-05-01-preview where relevant
[ ] Fabric live claims are backed by Fabric activity or source data
[ ] Offline replay is clearly labeled
[ ] Screenshots are sanitized
[ ] No generated reports, tenant IDs, tokens, keys, or private endpoints are shared
[ ] Reviewer evidence packet exists for any deployment claim
```
