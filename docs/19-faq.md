# FAQ

Use this page when you need quick answers before choosing a deployment mode, running a workshop, or reviewing the sample for broader reuse.

## Which mode should I run first?

Run `mcp-only` first when you are learning the repository or do not already have Fabric semantic assets.

It validates Azure AI Search MCP Server Knowledge Source behavior with Microsoft Learn MCP and does not require Fabric workspace or ontology setup.

For a managed organization that already has a Fabric workspace and ontology, the representative live acceptance path is `byo-fabric`: prove one Fabric source, then call the Knowledge Base through MCP. Use `full` when you want the greenfield platform story and have checked Fabric quota, region, tenant settings, and source authorization requirements.

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

## Is the Knowledge Base MCP endpoint the same as MCP Server KS?

No. They point in opposite directions.

- The native Knowledge Base MCP endpoint lets an MCP client call `knowledge_base_retrieve`.
- MCP Server KS lets the Knowledge Base call an external HTTPS MCP tool during retrieval.

Use `./liveks verify` to prove which Knowledge Source ran, then `./liveks mcp` to prove that an MCP client can consume the Knowledge Base. The current MCP tool result does not expose the retrieve API's separate activity and references arrays.

## Why use Microsoft Learn MCP for the first sample?

Microsoft Learn MCP is public, official, and does not require tenant-specific setup for the first run.

That makes it useful for proving the MCP Server KS path before adding private APIs, custom MCP servers, or Fabric semantic assets.

## Does `knowledgeSourceParams` force the Knowledge Base to use only one source?

Treat `knowledgeSourceParams` as source-specific runtime options, not as a strict proof that only one source can ever matter in every combined scenario.

For deterministic validation, use a single-source Knowledge Base:

- MCP-only KB for MCP Server KS validation.
- Fabric-only KB for deterministic Fabric validation, then the combined KB for multi-source routing.

When presenting combined routing, inspect `activity`, `references`, and source-specific data instead of assuming source selection from the final answer text.

## Why Static Web Apps instead of App Service by default?

The default app path uses Azure Static Web Apps with managed Functions API because it avoids App Service Plan quota issues that can block sample deployments in constrained demo subscriptions.

The browser still never receives Search admin keys, Azure OpenAI keys, or long-lived Fabric user tokens. Retrieve calls stay behind the server-side API.

## What evidence should I collect before a review or demo?

At minimum:

```text
[ ] bash scripts/validate-local.sh passes
[ ] liveks doctor passes for the selected environment
[ ] liveks plan matches the expected resources and ownership
[ ] GitHub Actions Validate passes for the commit being reviewed
[ ] E2E report exists for any deployment behavior being claimed
[ ] retrieve response includes activity or references for the source being claimed
[ ] Fabric live claims are backed by Fabric activity or sourceData
[ ] generated reports stay ignored
[ ] screenshots are sanitized
[ ] cleanup evidence exists for release rehearsal runs
```

Share only summarized PASS / FAIL / SKIP counts and sanitized screenshots. Do not paste raw deployment reports into issues, PRs, docs, or presentations.

## What should not be committed?

Do not commit:

- `.env` or `.env.*`,
- `.liveks/`,
- `.azure/`,
- `.deployment/`,
- `deployments/`,
- `scratch/`,
- raw deployment summaries,
- raw E2E reports,
- tenant IDs, service endpoints, keys, tokens, or connection strings,
- screenshots from private deployments unless reviewed and sanitized.

The repo intentionally keeps generated evidence under ignored paths.

## Is YAML or azd env the source of truth?

The ignored `.liveks/<environment>.yaml` file is the v2 authoring ledger. Profiles provide defaults and the schema validates the resolved values. `liveks up` projects non-secret values into the selected `azd` environment immediately before provisioning.

The redacted lock records the resolved values, their sources, and cleanup ownership. Do not hand-maintain `azd env` as a second configuration ledger.

## Does plan create cloud resources?

No. `plan` performs read-only cloud diagnostics and local Bicep, payload, and app builds. It writes ignored local plan and lock files but does not run `azd env set`, Fabric provisioning, or `azd up`.

## Can cleanup delete my existing Fabric workspace?

Not through the supported `byo-fabric` path. BYO ownership is marked `reuse`, and Fabric deletion is skipped. For `full`, deletion is allowed only when both the resolved configuration and environment lock identify Fabric assets as generated.

## Where should I go next?

| Need | Go to |
| --- | --- |
| Pick a mode | [Choose a Pattern](02-choose-a-pattern.md) |
| Understand architecture | [Architecture](01-architecture.md) |
| Deploy the sample | [One-Command Deployment](10-one-command-deployment.md) |
| Prepare a short demo | [Guided Live Demo](16-demo-walkthrough.md) |
| Check preview caveats | [Public Preview Limitations](13-public-preview-limitations.md) |
