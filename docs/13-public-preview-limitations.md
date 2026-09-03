# Public Preview Limitations and Caveats

Use this page when you need a single, reviewer-friendly map of what is stable in the sample, what is preview-dependent, and what should be validated before a customer workshop or public blog.

The official manuals remain the source of truth:

- [Create an MCP Server knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
- [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology)

Return to [Overview](00-overview.md) to choose a repository path, or continue with [MCP Server Knowledge Source](03-mcp-server-ks.md) for the `mcp-only` live procedure.

## Preview API Boundary

This sample uses Azure AI Search Knowledge Source APIs in `2026-05-01-preview`.

LiveKS and the direct postprovision path reject other versions before cloud calls because the current MCP Server, Fabric Ontology, message-input, answer-synthesis, and reasoning payloads are a single preview contract. The `search-index` profile implements Azure AI Search `2026-04-01` for generally available minimal extractive retrieval. The `mcp-search-index` and `three-source` profiles keep Search Index KS on that stable contract while pinning MCP KS, native Fabric KS, combined KB, and retrieve to `2026-05-01-preview`. See [API Compatibility](14-api-compatibility.md).

The machine-readable `config/compatibility.yaml` contract checks these pins across schema, profiles, generated examples, CLI behavior, infrastructure, samples, documentation, and CI. Ordinary compatibility validation is credential-free and records Azure and Fabric live execution as **NOT RUN**.

Treat these as preview-sensitive:

- request and response schemas,
- SDK model names,
- supported regions,
- retrieve behavior,
- activity and reference payload shape,
- Knowledge Source creation and update semantics.

Keep the API version explicit in samples, notebooks, scripts, and docs. Do not silently float to a newer preview in a workshop branch.

## MCP Server KS Caveats

MCP Server KS is the lowest-friction first path in this repo, but it still has important boundaries:

- The MCP server must be reachable by Azure AI Search over HTTPS.
- Local stdio MCP servers cannot be attached directly.
- Allowed tool names must be explicitly listed in the Knowledge Source definition.
- Tool output parsing should be selected intentionally: `auto`, `json`, `split`, or `none`.
- Tool calls can take longer than normal search queries; use `maxRuntimeInSeconds` when needed.
- `minimal` retrieval reasoning effort is not supported for MCP Server KS. Use `low` or `medium`.
- `alwaysQuerySource` is not supported on retrieve requests that reference an MCP Server Knowledge Source.
- Stored headers are for static service credentials, not user-specific or rotating credentials.
- Query-time header passthrough is the safer pattern for per-user or short-lived credentials.

This repo uses Microsoft Learn MCP as the default remote MCP server because it is public, official, and does not require tenant-specific setup for a first run.

## Knowledge Base MCP Endpoint Caveats

The northbound Knowledge Base MCP endpoint has a different evidence shape from the retrieve API:

- `tools/list` exposes `knowledge_base_retrieve`.
- `tools/call` returns MCP `result.content[]` text blocks.
- The current MCP result does not return separate `activity` and `references` arrays.
- The current tool input schema accepts one `queries` array and rejects additional properties. Retrieve-only `knowledgeSourceParams`, including `alwaysQuerySource`, cannot be passed through the MCP tool call.
- A successful text result proves protocol execution, not source execution. Source-specific REST activity and a known-fact MCP match are required for a grounded-source claim.
- Admin-key authentication is supported for this sample but grants broad Search access. Prefer bearer authentication and **Search Index Data Reader** for managed clients.
- Fabric-backed calls still require delegated source authorization in addition to Search service authentication.

Use `./liveks mcp --expect-term <known-non-sensitive-fact>` for count-only content evidence and normalized failures; do not publish raw MCP content. A run without `--expect-term` intentionally reports grounding as unverified.

The independent Python consumer requires the expected term and rejects a missing value before network access. Current Microsoft Learn guidance also describes a newer preview MCP API version, but this repository remains pinned to its continuously checked `2026-05-01-preview` deployment contract until a separate migration validates payload and live-service parity.

## Fabric Ontology KS Caveats

Fabric Ontology KS is the strongest semantic-grounding path, but it has more setup requirements:

- The Azure AI Search service and Fabric workspace must be in the same Microsoft Entra ID tenant.
- The Fabric workspace must have ontology support enabled and contain an ontology item.
- The Knowledge Source definition needs `workspaceId` and `ontologyId`.
- Live retrieve requires an end-user access token in `x-ms-query-source-authorization`.
- The token must be scoped to `https://search.azure.com/.default`.
- Standard Azure AI Search authentication is still required; the source authorization token does not replace Search authentication.
- Use `includeReferenceSourceData` during validation when you need `sourceData.fabricAnswer` and `sourceData.fabricRawData`.
- `minimal` retrieval reasoning effort is not supported for Fabric Ontology KS. Use `low` or `medium`.

If the app has Fabric IDs but no delegated token, it should show offline replay or a clear missing-token state. Do not describe that state as live Fabric retrieval.

## Deployment Mode Caveats

| Mode | Caveat | Safe interpretation |
| --- | --- | --- |
| `search-index` | Uses only the GA Search Index KS and extractive retrieve contract. | Lowest-risk existing-index proof without MCP. |
| `mcp-search-index` | Reuses Search and Azure OpenAI assets but creates preview MCP/KB objects. | Protected canary target; no Fabric assets are created or deleted. |
| `three-source` | Reuses Search/index, Azure OpenAI, Fabric workspace, and native ontology; creates only three KS objects and one KB. | No protected canary exists; delegated Fabric authorization and all three independent proofs are required. |
| `mcp-only` | Fabric is intentionally skipped. | This proves MCP Server KS, app hosting, Search/OpenAI deployment, and trace inspection. |
| `byo-fabric` | Requires existing Fabric workspace and ontology IDs. | This is the safest customer-facing live Fabric path when semantic assets already exist. |
| `full` | Requires Fabric capacity quota, Fabric API readiness, GraphModel readiness, and delegated auth for live retrieve. | This is the platform story and greenfield demo path, not the fastest first run. |

For release rehearsals, all live profiles should prove create-call-load-delete behavior through `./liveks e2e --env <environment> --cleanup --yes`.

## Full Greenfield Fabric Caveats

The `full` path is intentionally more ambitious:

1. create or reuse Fabric capacity,
2. create a Fabric workspace,
3. create an Airline Ops Lakehouse,
4. load synthetic CSV data,
5. create the ontology definition,
6. prepare the ontology-backed GraphModel,
7. wait for GraphModel readiness,
8. deploy Azure resources,
9. create the Azure AI Search Fabric Ontology Knowledge Source.

Common failure causes:

- no Fabric capacity quota in the selected region,
- tenant settings do not allow ontology or API operations,
- capacity admin is not valid for the tenant,
- Lakehouse table loading did not finish,
- GraphModel is not loaded or not refreshable yet,
- delegated source authorization token is missing or expired.

The recommended mitigation is simple: start with stable `search-index` when an agentic-ready index exists, add `mcp-search-index` only when the reused Azure OpenAI grant is ready, use `three-source` only when existing native Fabric assets and delegated authorization are ready, use `mcp-only` when infrastructure must be provisioned, move to `byo-fabric` for a provisioned Azure stack over existing Fabric, and use `full` only when quota and auth expectations are clear.

## App And Token Caveats

The default app path is Azure Static Web Apps with managed Functions API.

Security defaults:

- Browser code must not receive Search admin keys.
- Browser code must not receive Azure OpenAI keys.
- Long-lived Fabric user tokens should not be stored in browser state.
- Private demos can set `FABRIC_USER_SEARCH_TOKEN` server-side.
- Public or reusable flows should move toward real user sign-in and OBO token acquisition.

The app can still be useful without Fabric live auth because the offline traces show the expected activity, references, and sourceData shape.

## Claims To Avoid

Avoid these claims in README, blogs, and presentations:

- "Production-ready reference architecture."
- "Fabric ontology creation is guaranteed in every tenant."
- "Offline replay proves live Fabric retrieval."
- "MCP Server KS can attach local stdio MCP servers directly."
- "Knowledge Source parameters are a strict source allow-list."
- "Static screenshots prove the live path."
- "A successful `azd up` proves KS/KB retrieve behavior."
- "Repository tests prove the protected canary ran live."

Prefer these claims:

- "Reusable accelerator scaffold."
- "Public preview sample."
- "Validated deployment paths with explicit evidence."
- "Credential-free tests validate the protected canary contract; an approved manual run supplies live evidence."
- "MCP-only is the fastest first run."
- "BYO Fabric is the safest live Fabric customer path."
- "Full mode is the greenfield platform story and depends on quota, tenant settings, and delegated auth."

## Reviewer Checklist

Before sharing outside the working team:

```text
[ ] README mode selector is current
[ ] scripts/validate-local.sh passes
[ ] no-secret scan passes
[ ] E2E report exists for the mode being shown
[ ] generated reports stay ignored
[ ] screenshots do not expose tenant IDs, endpoints, tokens, or customer data
[ ] live Fabric claims are backed by Fabric activity, not offline replay
[ ] Learn manual links and preview API version are current
```

For setup and test guidance, see [One-Command Demo Deployment](10-one-command-deployment.md), [Post-Deployment Tests](08-test-queries.md), and [Troubleshooting](07-troubleshooting.md).
