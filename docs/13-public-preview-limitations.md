# Public Preview Limitations and Caveats

Use this page when you need a single, reviewer-friendly map of what is stable in the sample, what is preview-dependent, and what should be validated before a customer workshop or public blog.

The official manuals remain the source of truth:

- [Create an MCP Server knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
- [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology)

## Preview API Boundary

This sample uses Azure AI Search Knowledge Source APIs in `2026-05-01-preview`.

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
| `mcp-only` | Fabric is intentionally skipped. | This proves MCP Server KS, app hosting, Search/OpenAI deployment, and trace inspection. |
| `byo-fabric` | Requires existing Fabric workspace and ontology IDs. | This is the safest customer-facing live Fabric path when semantic assets already exist. |
| `full` | Requires Fabric capacity quota, Fabric API readiness, GraphModel readiness, and delegated auth for live retrieve. | This is the platform story and greenfield demo path, not the fastest first run. |

For release rehearsals, all modes should prove create-call-load-delete behavior through `scripts/e2e-test.sh --cleanup`.

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

The recommended mitigation is simple: start with `mcp-only`, move to `byo-fabric` when Fabric IDs are known, and use `full` only when quota and auth expectations are clear.

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

Prefer these claims:

- "Reusable accelerator scaffold."
- "Public preview sample."
- "Validated deployment paths with explicit evidence."
- "MCP-only is the fastest first run."
- "BYO Fabric is the safest live Fabric customer path."
- "Full mode is the greenfield platform story and depends on quota, tenant settings, and delegated auth."

## Reviewer Checklist

Before sharing outside the working team:

```text
[ ] README mode selector is current
[ ] docs/12-reviewer-evidence.md matches test behavior
[ ] scripts/validate-local.sh passes
[ ] no-secret scan passes
[ ] E2E report exists for the mode being shown
[ ] generated reports stay ignored
[ ] screenshots do not expose tenant IDs, endpoints, tokens, or customer data
[ ] live Fabric claims are backed by Fabric activity, not offline replay
[ ] Learn manual links and preview API version are current
```

For evidence guidance, see [Reviewer Evidence Guide](12-reviewer-evidence.md).
For blog and presentation wording, see [Storyline And Safe Claims](17-storyline-and-safe-claims.md).
