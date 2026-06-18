# FAQ

Use this page when you need quick answers before choosing a deployment mode, running a workshop, or reviewing the sample for broader reuse.

## Which mode should I run first?

Run `mcp-only` first.

It validates Azure AI Search MCP Server Knowledge Source behavior with Microsoft Learn MCP and does not require Fabric workspace or ontology setup.

Move to `byo-fabric` when you already have Fabric workspace and ontology IDs. Use `full` when you want the greenfield platform story and have checked Fabric quota, region, tenant settings, and source authorization requirements.

## Why does the repo have three modes?

The modes match three different reader states:

| Mode | Reader state |
| --- | --- |
| `mcp-only` | "I want to validate the new MCP Server KS quickly." |
| `byo-fabric` | "I already have Fabric semantic assets and want to connect Azure AI Search." |
| `full` | "I want a zero-to-demo platform run that creates sample Fabric assets first." |

One mode would either hide Fabric complexity or force every reader into Fabric setup before they can see a live Knowledge Source.

## Is `full` the default path?

No. `full` is the strongest platform story, but it is not the fastest first run.

Use `full` when:

- Fabric capacity quota is available in the selected region,
- tenant settings allow the required Fabric operations,
- the demo owner understands Fabric source authorization,
- the audience needs the end-to-end platform story.

Use `mcp-only` for the first run and `byo-fabric` for the safest live Fabric customer path.

## What does offline replay prove?

Offline replay proves trace shape and teaching flow.

It does not prove live MCP or live Fabric retrieval. Use offline replay to understand:

- what `activity` looks like,
- how `references` are structured,
- where source-specific data appears,
- how the app labels live versus offline behavior.

Use E2E reports and live retrieve traces when you need proof that a live path worked.

## Why does Fabric live retrieve need source authorization?

Fabric Ontology KS enforces permissions at query time. The retrieve call still needs standard Azure AI Search authentication, and Fabric live retrieval also needs an end-user source authorization token passed separately in `x-ms-query-source-authorization`.

The token must be scoped for Azure AI Search:

```text
https://search.azure.com/.default
```

Do not put raw tokens in tracked files.

## Can I use a local stdio MCP server?

Not directly.

Azure AI Search MCP Server KS needs a remote MCP-compatible HTTPS endpoint that Azure AI Search can reach. Local stdio MCP servers are useful for local agent workflows, but they are not directly attachable as Azure AI Search MCP Server Knowledge Sources.

## Why use Microsoft Learn MCP for the first sample?

Microsoft Learn MCP is public, official, and does not require tenant-specific setup for the first run.

That makes it useful for proving the MCP Server KS path before adding private APIs, custom MCP servers, or Fabric semantic assets.

## Does `knowledgeSourceParams` force the Knowledge Base to use only one source?

Treat `knowledgeSourceParams` as source-specific runtime options, not as a strict proof that only one source can ever matter in every combined scenario.

For deterministic validation, use a single-source Knowledge Base:

- MCP-only KB for MCP Server KS validation.
- Fabric or combined KB for Fabric and multi-source validation.

When presenting combined routing, inspect `activity`, `references`, and source-specific data instead of assuming source selection from the final answer text.

## Why Static Web Apps instead of App Service by default?

The default app path uses Azure Static Web Apps with managed Functions API because it avoids App Service Plan quota issues that can block sample deployments in constrained demo subscriptions.

The browser still never receives Search admin keys, Azure OpenAI keys, or long-lived Fabric user tokens. Retrieve calls stay behind the server-side API.

`demo-app/` remains as an optional Next.js/App Service reference path for environments that prefer App Service and have quota.

## What evidence should I collect before a review or demo?

At minimum:

```text
[ ] bash scripts/validate-local.sh passes
[ ] GitHub Actions Validate passes for the commit being reviewed
[ ] E2E report exists for any deployment behavior being claimed
[ ] retrieve response includes activity or references for the source being claimed
[ ] Fabric live claims are backed by Fabric activity or sourceData
[ ] generated reports stay ignored
[ ] screenshots are sanitized
[ ] cleanup evidence exists for release rehearsal runs
```

For private review, generate a sanitized evidence summary instead of pasting raw deployment reports.

## What should not be committed?

Do not commit:

- `.env` or `.env.*`,
- `.deployment/`,
- `deployments/`,
- `scratch/`,
- raw deployment summaries,
- raw E2E reports,
- tenant IDs, service endpoints, keys, tokens, or connection strings,
- screenshots from private deployments unless reviewed and sanitized.

The repo intentionally keeps generated evidence under ignored paths.

## Where should I go next?

| Need | Go to |
| --- | --- |
| Pick a mode | [Choose a Pattern](02-choose-a-pattern.md) |
| Understand architecture | [Architecture](01-architecture.md) |
| Deploy the sample | [One-Command Deployment](10-one-command-deployment.md) |
| Validate evidence | [Reviewer Evidence Guide](12-reviewer-evidence.md) |
| Prepare a short demo | [Demo Walkthrough](16-demo-walkthrough.md) |
| Check safe claims | [Public Preview Limitations](13-public-preview-limitations.md) |
