# Full Greenfield Full-Run Test Specification

This test validates the greenfield path for users who have neither Azure AI Search/Foundry resources nor Fabric sample assets.

## Purpose

Prove that `--mode full` can create the Azure side, create the Fabric sample side, connect the generated Fabric ontology to Azure AI Search, run live retrieve, load the demo app, and clean up generated resources.

## Inputs

Use an ignored local env file, such as `.env.external.local`:

```bash
DEPLOYMENT_MODE=full
EXTERNAL_TENANT_ID=<tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext

FABRIC_CAPACITY_MODE=create
FABRIC_LOCATION=<fabric-region-with-quota>
FABRIC_CAPACITY_SKU=F2
FABRIC_CAPACITY_ADMIN=<admin-upn>
```

Optional values if an existing Fabric ontology should be connected instead of creating new Fabric assets:

```bash
FABRIC_WORKSPACE_ID=<fabric-workspace-guid>
FABRIC_ONTOLOGY_ID=<fabric-ontology-guid>
FABRIC_USER_SEARCH_TOKEN=<optional raw delegated token>
```

## Command

Greenfield run:

```bash
bash scripts/e2e-test.sh \
  --mode full \
  --env-file .env.external.local \
  --env-name ext-liveks-full-e2e \
  --location eastus \
  --fabric-location westus3 \
  --cleanup
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
- Azure OpenAI account and `gpt-4o-mini` deployment
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
deployments/ext-liveks-full-e2e/test-report.md
```

All generated files must be git ignored and must not contain secrets.

## Expected Knowledge Assets

- `microsoft-learn-mcp-ks`
- `fabric-ontology-ks`
- `live-knowledge-sources-mcp-kb`
- `live-knowledge-sources-kb`
- `airline-ops-regulatory-docs` Search index

## Required Checks

| Check | Expected |
| --- | --- |
| External tenant login | PASS |
| Subscription and tenant match | PASS |
| Tool preflight | PASS |
| Bicep build | PASS |
| postprovision dry-run | PASS |
| Static app build | PASS |
| `azd up` | PASS |
| Resource group exists | PASS |
| Azure resources exist | PASS |
| Fabric capacity active | PASS when capacity is created or BYO capacity is found |
| Fabric workspace created | PASS |
| Lakehouse tables loaded | PASS |
| Ontology definition readable | PASS |
| Ontology-backed GraphModel queryable | PASS |
| Deployment summary exists | PASS |
| Fabric summary exists | PASS |
| MCP KS exists | PASS |
| Fabric KS exists | PASS |
| MCP-only KB exists | PASS |
| Combined KB exists | PASS |
| Airline Ops index has docs | PASS |
| MCP retrieve | PASS |
| Fabric live retrieve | PASS when delegated token is available; SKIP only if token minting fails |
| App root HTTP 200 | PASS |
| `/api/status` | PASS and shows `deploymentMode=full` |
| `/api/retrieve/mcp` | PASS |
| `/api/retrieve/fabric` | PASS live with token; offline only when token is absent |
| `/api/retrieve/combined` | PASS live with token; offline only when token is absent |
| Cleanup | PASS |
| Azure resource group deleted | PASS |
| Generated Fabric workspace deleted | PASS |

## Pass Criteria

The run passes when:

- Azure resources are created.
- Fabric capacity/workspace/lakehouse/ontology are created or explicitly reused before Azure AI Search retrieve validation.
- The ontology-backed GraphModel is queryable before Azure AI Search retrieve is tested.
- `fabric-provision.py` writes Fabric IDs into `azd env`.
- Azure AI Search creates `fabric-ontology-ks`.
- Combined KB includes both MCP and Fabric sources.
- Cleanup removes Azure resources and generated Fabric workspace/items.

If the region has no Fabric capacity quota, the run must fail clearly with the ARM quota error and the report must recommend using a region with quota or `byo-fabric`.
