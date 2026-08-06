# Full Greenfield Full-Run Test Specification

This test validates the greenfield path for users who have neither Azure AI Search/Foundry resources nor Fabric sample assets.

## Purpose

Prove that the `full` profile can create the Azure side, create the Fabric sample side, connect the generated Fabric ontology to Azure AI Search, run live retrieve, load the demo app, and clean up generated resources.

## Inputs

Create the ignored YAML ledger:

```bash
./liveks init --profile full --env ext-liveks-full-e2e
```

Set `fabric.location` to a region with quota and add the external Azure context when needed. `full` rejects existing workspace and ontology IDs; use `byo-fabric` for those assets.

The F2 capacity is billable until cleanup. The command requires the explicit capacity acknowledgement even with non-interactive confirmation.

## Command

Greenfield run:

```bash
./liveks e2e \
  --env ext-liveks-full-e2e \
  --cleanup \
  --yes \
  --accept-fabric-capacity \
  --format json
```

Fabric-only rehearsal:

```bash
bash scripts/fabric-e2e-test.sh \
  --env-file .env.external.local \
  --env-name ext-liveks-fabric-e2e \
  --fabric-location westus3 \
  --cleanup
```

## Expected Azure And Fabric Resources

- Resource group: `rg-ext-liveks-full-e2e`
- Azure AI Search
- Azure OpenAI account and `gpt-5-mini` deployment
- Storage account
- Static Web App and managed Functions API
- F2 Microsoft Fabric capacity when `FABRIC_CAPACITY_MODE=create`
- Fabric workspace
- Airline Ops Lakehouse with generated Delta tables
- Airline Ops Ontology
- Ontology-backed GraphModel with a passing probe query

## Expected Generated Files

```text
deployments/ext-liveks-full-e2e/deployment-summary.md
deployments/ext-liveks-full-e2e/fabric-summary.md
deployments/ext-liveks-full-e2e/fabric.env
deployments/ext-liveks-full-e2e/fabric-summary.json
deployments/ext-liveks-full-e2e/e2e-report.json
deployments/ext-liveks-full-e2e/test-report.md
```

All generated files must be git ignored and must not contain secrets.

## Expected Knowledge Assets

- `microsoft-learn-mcp-ks`
- `fabric-ontology-ks`
- `live-knowledge-sources-mcp-kb`
- `live-knowledge-sources-fabric-kb`
- `live-knowledge-sources-kb`
- `airline-ops-regulatory-docs` Search index

## Required Checks

| Check | Expected |
| --- | --- |
| Tool, login, tenant, and provider preflight | PASS |
| Bicep build | PASS |
| Payload dry-run | PASS |
| Static app build | PASS |
| ARM preview | PASS without provisioning |
| Fabric preprovision | PASS |
| `azd up` | PASS |
| Resource group exists | PASS |
| Fabric capacity active | PASS when the generated capacity is created |
| Fabric workspace created | PASS |
| Lakehouse tables loaded | PASS |
| Ontology definition readable | PASS |
| Ontology-backed GraphModel queryable | PASS |
| MCP retrieve | PASS with MCP evidence |
| Fabric live retrieve | PASS with `fabricOntology` evidence |
| Native Fabric KB MCP | PASS with `grounding-content` matching the generated Airline Ops fact |
| Combined retrieve | PASS with recognized planner-selected live evidence |
| App status | HTTP 200 |
| Generated Fabric cleanup | PASS |
| Azure cleanup | PASS |
| Azure resource group deleted | PASS |
| Generated Fabric capacity and workspace absent | PASS |

## Pass Criteria

The run passes when:

- Azure resources are created.
- Fabric capacity/workspace/lakehouse/ontology are created before Azure AI Search retrieve validation.
- The ontology-backed GraphModel is queryable before Azure AI Search retrieve is tested.
- `fabric-provision.py` writes Fabric IDs into `azd env`.
- Azure AI Search creates `fabric-ontology-ks`.
- The dedicated checks prove MCP and Fabric independently, while the combined KB returns live evidence from one or both planner-selected sources.
- Cleanup removes Azure resources and generated Fabric workspace/items.

If the region has no Fabric capacity quota, the run must fail clearly with the ARM quota error and the report must recommend using a region with quota or `byo-fabric`.
