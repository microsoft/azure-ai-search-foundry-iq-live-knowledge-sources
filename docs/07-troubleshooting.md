# Troubleshooting

Start by confirming which deployment mode you are running:

| Mode | Fabric expectation |
| --- | --- |
| `mcp-only` | Fabric is skipped. Fabric and combined Fabric live checks should return offline replay. |
| `byo-fabric` | `fabric.workspace_id` and `fabric.ontology_id` must be provided in the ignored YAML ledger. |
| `full` | LiveKS creates Fabric sample assets before `azd up`, then connects the generated IDs to Azure AI Search. |

Generated diagnostics are written under ignored paths:

```text
.deployment/
.liveks/<env>.lock.json
deployments/<env>/deployment-summary.md
deployments/<env>/test-report.md
deployments/<env>/e2e-report.json
```

Start with machine-readable diagnostics:

```bash
./liveks doctor --env <environment> --format json
./liveks plan --env <environment> --format json
```

## Configuration Or Plan Fails

- Confirm the YAML has `version: 2` and matching `profile` and `deployment.mode` values.
- Remove unknown fields or use the canonical names in `config/schema.yaml`.
- Keep raw secrets out of YAML; use `user_search_token: {env: FABRIC_USER_SEARCH_TOKEN}`.
- `byo-fabric` requires both GUIDs. `full` rejects both GUIDs.
- Azure Developer CLI must be 1.27.0 or newer and Node.js must be 22 or newer.
- `plan` can create ignored local build artifacts, but a cloud-state change indicates a bug and should be reported.

## Knowledge Source Creation Fails

- Confirm `SEARCH_API_VERSION` is `2026-05-01-preview` or later when required by the preview.
- Confirm the source kind is supported in your search service region.
- Confirm API key or RBAC permissions are valid.
- Confirm GUID fields are valid GUIDs.

## MCP Server KS Fails

- Confirm the MCP server is reachable over HTTPS by Azure AI Search.
- Confirm the tool name in the knowledge source matches the remote MCP server.
- Confirm output parsing is compatible with the tool response.
- Increase `maxRuntimeInSeconds` if the tool is slow.
- Use query-time header passthrough for per-user credentials.

## Fabric Ontology KS Fails

- Confirm the Fabric workspace ID and ontology ID.
- Confirm the user can access the Fabric workspace and ontology.
- Confirm `x-ms-query-source-authorization` is present in retrieve calls.
- Confirm the end-user access token is scoped for Azure AI Search: `https://search.azure.com/.default`.
- Use `includeReferenceSourceData` during validation.

## Fabric Greenfield Fails

- Confirm the subscription has Fabric capacity quota in `FABRIC_LOCATION`.
- If F2 capacity creation fails, choose another `fabric.location` in the YAML after confirming quota, or use `byo-fabric`.
- Confirm the capacity admin value is a valid user principal for the target tenant.
- Confirm the Lakehouse CSV load completed before ontology and GraphModel validation.
- A newly created Lakehouse can briefly report that OneLake details are unavailable. LiveKS retries this propagation window automatically; if it still fails, retain the report, run `down`, and start a fresh `up` rather than copying generated IDs into YAML.
- A fresh full run clears generated Fabric IDs from the selected `azd` environment and resolves assets by their derived names. YAML remains the ownership ledger; generated IDs are transient deployment state.
- If retrieve fails with `GraphIsNotLoaded`, `GraphNotRefreshable`, or natural-language processing errors, wait for GraphModel readiness or rerun the full path after cleanup.
- Full mode provisions Fabric before `azd up` so long GraphModel readiness does not break the Azure Developer CLI postprovision hook.

## Fabric Retrieve Returns Offline Replay

- In `mcp-only`, this is expected.
- In `byo-fabric` or `full`, live retrieve requires both Fabric IDs and an end-user Search access token for source authorization.
- Provide `FABRIC_USER_SEARCH_TOKEN` server-side only for private demos, or paste a transient raw end-user token in the app.
- The token must be scoped to `https://search.azure.com/.default` and must not include a `Bearer` prefix.
- If the token expires, MCP live can still work while Fabric and combined views fall back to replay.

## Static Web Apps Or App Hosting Fails

- The default path uses Azure Static Web Apps with managed Functions API to avoid App Service Plan quota issues.
- If Static Web Apps is unavailable in your Azure region, set `AZURE_STATIC_WEB_APP_LOCATION` to a supported region such as `eastus2`.
- If you opt into the optional App Service path and hit `Microsoft.Web/serverFarms` quota errors, use Static Web Apps or request App Service quota.
- Browser code must never receive Search admin keys, Azure OpenAI keys, or long-lived user tokens. Keep retrieve calls behind the server-side API.

## E2E Report Shows FAIL Or SKIP

- `FAIL` means the required behavior for the selected mode did not complete.
- `SKIP` is acceptable only when the selected mode explicitly does not require that path, such as Fabric checks in `mcp-only`.
- For `byo-fabric`, missing Fabric IDs should fail during configuration resolution, before deployment starts.
- For `full`, missing Fabric IDs are acceptable only if the greenfield Fabric provisioning step produced generated IDs.
- Separate MCP and Fabric checks prove both live paths. A combined KB check passes with recognized live evidence from one or both because the Knowledge Base planner chooses which attached source to call for each query.
- Cleanup must pass for release rehearsal runs. Use `--keep-resources` only while debugging.

## Cleanup Reports Partial

- Read the ownership check in the `down` output and the redacted `.liveks/<env>.lock.json`.
- BYO Fabric assets must remain untouched even when Azure cleanup fails.
- For full mode, Azure cleanup continues after a Fabric cleanup warning.
- Every live cleanup must pass `resource-group-absent`. A full run that created capacity must also pass `fabric-capacity-resource-group-absent` and `fabric-capacity-absent`.
- If an absence check is still pending, wait for ARM deletion propagation and rerun `liveks down --env <environment> --yes --format json` before deleting anything manually.
- Before manually deleting a Fabric capacity resource group, list its contents and verify in Fabric that no shared workspace is assigned.
- Return code `4` means cleanup needs explicit follow-up; do not report the rehearsal as complete.
