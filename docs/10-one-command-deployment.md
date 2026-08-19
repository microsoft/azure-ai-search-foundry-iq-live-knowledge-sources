# One-Command Deployment

`liveks up` is one lifecycle command only **after** `doctor` and `plan` pass. It does not bypass ARM preview, cost context, exact confirmation, source verification, or cleanup ownership.

For the shortest reproducible environment setup, start with [Codespaces First Live](15-codespaces-first-live.md).

After an environment is initialized and planned, `liveks up` is the single command that previews, confirms, provisions, deploys, and verifies the accelerator.

## Prerequisites

| Tool or access | Requirement |
| --- | --- |
| Python | 3.11 or newer |
| Azure Developer CLI | 1.27.0 or newer |
| Azure CLI | Installed and signed into the target subscription |
| Node.js | 22 or newer, with npm |
| Azure | Permission to create the profile's resources |
| Fabric BYO | Existing workspace and ontology access |
| Fabric full | F2 quota, capacity permission, and supported tenant settings |

```bash
az login --tenant <tenant-guid>
azd auth login
./liveks bootstrap
```

Run `./liveks doctor --env <environment>` before planning. It checks versions, both authentication contexts, configured tenant/subscription alignment, provider registration, and profile requirements.

## Initialize

```bash
./liveks init --profile mcp-only --env liveks-mcp
./liveks init --profile byo-fabric --env liveks-byo
./liveks init --profile full --env liveks-full
```

Each command writes `.liveks/<environment>.yaml`. Add overrides there and keep the file untracked. See [Configuration](21-configuration.md).

## Plan

```bash
./liveks plan --env liveks-mcp
```

The plan compiles Bicep, dry-runs Search payload generation, builds the Static Web Apps frontend/API bundle, reports expected resources and cost, and writes a redacted lock. It performs no cloud mutation.

## Up

```bash
./liveks up --env liveks-mcp
```

Execution order:

1. repeat the complete plan,
2. select or create the named `azd` environment,
3. project resolved non-secret YAML values into `azd env`,
4. run `azd provision --preview`,
5. require exact confirmation,
6. preprovision generated Fabric assets for `full`,
7. run `azd up`, including cross-platform Python hooks,
8. verify the app and retrieve evidence,
9. write a redacted lifecycle lock and ignored reports.

Automation can use `--yes`. Full mode still requires the separate cost acknowledgement:

```bash
./liveks up --env liveks-full --yes --accept-fabric-capacity
```

## Profile Behavior

| Profile | Azure resources | Fabric behavior |
| --- | --- | --- |
| `mcp-only` | Search, OpenAI, Storage, app, MCP KS, MCP-only KB, sample index | Skipped |
| `byo-fabric` | Same Azure assets plus Fabric KS, Fabric-only KB, and combined KB | Existing workspace/ontology reused |
| `full` | Same Azure assets plus generated Fabric KS, Fabric-only KB, and combined KB | F2 capacity, workspace, Lakehouse, ontology, and GraphModel created |

The Search managed identity receives Azure OpenAI access for answer synthesis. The default frontend is Azure Static Web Apps with a managed Node.js API, which keeps Search and OpenAI credentials out of browser code.

## Fabric Full Details

Full mode creates the Fabric stack before `azd up` so long Lakehouse and GraphModel readiness work does not run inside the Azure postprovision timeout. Generated IDs are projected into the selected `azd` environment, then postprovision creates the Fabric Ontology KS, Fabric-only KB, and combined KB.

Each fresh run clears stale generated IDs, resolves the assets created for the environment by name, and waits through the initial OneLake metadata propagation window. During Azure deployment, Bicep consumes the preprovisioned capacity as an existing asset; the YAML ledger remains `fabric.mode: create` so cleanup ownership stays explicit.

The profile defaults to:

```yaml
fabric:
  mode: create
  location: westus3
  capacity_sku: F2
```

Change `fabric.location` only after confirming quota. Full mode rejects existing workspace and ontology IDs to keep creation and cleanup ownership unambiguous.

## Verify

`up` verifies automatically. Rerun without provisioning:

```bash
./liveks verify --env liveks-mcp
```

The verifier checks:

- resource group existence,
- app status endpoint,
- live MCP retrieve evidence,
- live Fabric and combined evidence for Fabric profiles,
- response source types rather than final answer text alone.

The single-source KB checks prove the MCP and Fabric paths independently. The combined KB planner may select one or both attached sources for a query, so verification records the recognized live source types instead of requiring both on every call.

Reports under `deployments/<environment>/` are ignored and must remain private unless sanitized.

### Verify Through The Demo App

`up` and `verify` provide automated evidence. Also test the interface that a workshop participant will use:

1. Open the **App URL** in `deployments/<environment>/deployment-summary.md`.
2. Select **Deployment** and then **Re-check** to confirm live Search reachability.
3. Select **MCP Live** and then **Run retrieve**. Require a `live` badge and MCP activity or references.
4. For a Fabric profile, select **Fabric**, enter a raw delegated Search token, and run retrieve. Require a `live` badge and Fabric evidence.
5. Select **Combined Trace** only after the single-source paths pass, then describe the planner selection visible in activity and references.

The answer text is not the acceptance criterion. An offline fixture can return the same useful answer, so require a `live` response mode plus the expected source trace.

Continue with [Guided Live Demo Walkthrough](16-demo-walkthrough.md) for every click and presenter cue, or [Post-Deployment Tests](08-test-queries.md) for additional queries and expected trace fields.

## Demo App

The build has two hosting contexts:

- GitHub Pages: canonical offline replay only, labeled `offline-replay`.
- Azure Static Web Apps: managed API first, with canonical replay used when a source is intentionally unavailable.

The same response fixtures drive CLI replay, Pages, and API fallback. The managed API uses Node.js 22 and keeps Search admin keys server-side.

## Down

```bash
./liveks down --env liveks-mcp
```

Cleanup order:

1. select the exact named `azd` environment,
2. compare resolved ownership with the redacted lock,
3. delete Fabric only when both identify it as generated,
4. run `azd down --purge --force`,
5. verify the generated deployment resource group is absent,
6. when this run created a Fabric capacity, verify the matching ARM capacity is absent,
7. when this run also created the dedicated capacity resource group, verify that group is absent.

For `byo-fabric`, Fabric cleanup is always skipped. For `full`, a Fabric cleanup failure, missing or invalid lock, or missing ownership summary is reported as partial but Azure cleanup continues. Create mode refuses to adopt an existing capacity unless the same environment's prior summary proves ownership. The direct `azd` compatibility path can instead prove the exact Bicep-created ARM ID with matching environment, solution, and manager tags.

Successful `down --format json` output contains these checks:

| Check | Applies to | Required result |
| --- | --- | --- |
| `resource-group-absent` | Every live profile | `pass` |
| `fabric-capacity-resource-group-absent` | `full` when the run created the dedicated capacity group | `pass` |
| `fabric-capacity-resource-group-preserved` | `full` when the capacity was created in a pre-existing group | `pass` |
| `fabric-capacity-absent` | `full` when the run created capacity | `pass` |

For an independent Azure CLI confirmation, take the generated values from the ignored Fabric summary. Expect the deployment group to be absent and the exact capacity lookup to return `ResourceNotFound`. Expect the capacity group to be absent when `capacityResourceGroupCreated` is true, present when it is false, and manually reviewed when the field is missing:

```bash
az group exists --name <deployment-resource-group>
az group exists --name <fabric-capacity-resource-group>
az resource show --ids <fabric-capacity-arm-id> --only-show-errors
```

Do not apply the Fabric absence checks to `byo-fabric`: preserving its existing capacity, workspace, and ontology is the required result.

## Full Lifecycle Evidence

```bash
./liveks e2e --env liveks-mcp --cleanup --yes
```

Full mode:

```bash
./liveks e2e \
  --env liveks-full \
  --cleanup \
  --yes \
  --accept-fabric-capacity
```

Choose exactly one of `--cleanup` or `--keep-resources`. Use the latter only for active debugging with an assigned cleanup owner.

The lifecycle writes detailed ignored `e2e-report.json` and `test-report.md` files, plus allowlist-sanitized `evidence-capsule.json` and `evidence-capsule.md` views. The capsules retain revision, profile, assertion status, proved source types, and a detailed-report digest while omitting messages and environment-specific identifiers.

## Residual Fabric Capacity

If full cleanup reports a residual capacity:

1. inspect `deployments/<environment>/fabric-summary.json`,
2. confirm `capacityCreated` is true for this exact environment,
3. check `capacityResourceGroupCreated` before treating the whole group as owned,
4. list every resource in its Azure resource group,
5. confirm no shared workspace is assigned in Fabric,
6. delete only the generated capacity or its owned, otherwise empty resource group.

```bash
az resource list --resource-group <fabric-capacity-resource-group> -o table
# Use only when capacityResourceGroupCreated is true and the inventory is otherwise empty:
az group delete --name <fabric-capacity-resource-group> --yes --no-wait
# Otherwise delete the proven generated capacity and preserve the group:
az resource delete --ids <fabric-capacity-arm-id>
```

Do not delete a group that contains non-sample resources, a BYO capacity, or an asset whose ownership cannot be proven. New full runs tag generated capacity resources with the environment and solution, but tags support the ownership record rather than replacing it. Inspect both Azure and the Fabric admin portal before manual cleanup.

## Direct azd Compatibility

Direct `azd up` remains available for template users after prerequisites are installed. Cross-platform Python hooks supply safe MCP-only defaults, configure postprovision assets, and deploy the managed API. It does not provide the YAML plan, ownership lock, explicit full-capacity acknowledgement, or integrated verification of the LiveKS path, so the documented workflow is `liveks up`.

The old shell wrappers remain compatibility shims and delegate to LiveKS. New scripts should call `./liveks` or `./liveks.ps1` directly.
