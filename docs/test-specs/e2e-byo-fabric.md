# BYO Fabric Full-Run Test Specification

This test validates the primary deployment path for users who already have a Microsoft Fabric workspace and ontology. The run creates the Azure AI Search, Azure OpenAI, MCP Knowledge Source, Fabric Ontology Knowledge Source, Knowledge Bases, Search index, and demo app resources, then validates live retrieval behavior.

## Purpose

Prove that an existing Fabric ontology can be connected to a newly deployed Foundry IQ/Azure AI Search environment and used from the demo app.

This is the validated public sample path.

## Inputs

Use an ignored local env file, such as `.env.external.local`:

```bash
DEPLOYMENT_MODE=byo-fabric
EXTERNAL_TENANT_ID=<tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext

FABRIC_WORKSPACE_ID=<fabric-workspace-guid>
FABRIC_ONTOLOGY_ID=<fabric-ontology-guid>
```

Optional for live Fabric retrieve:

```bash
FABRIC_USER_SEARCH_TOKEN=<raw delegated token for https://search.azure.com/.default>
```

Do not prefix the token with `Bearer`.

## Command

```bash
bash scripts/e2e-test.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name ext-liveks-byo-e2e \
  --location eastus \
  --cleanup
```

## Expected Azure Resources

- Resource group: `rg-ext-liveks-byo-e2e`
- Azure AI Search
- Azure OpenAI account and `gpt-4o-mini` deployment
- Storage account
- Static Web App and managed Functions API
- Search managed identity with Azure OpenAI access

## Expected Knowledge Assets

- `microsoft-learn-mcp-ks`
- `fabric-ontology-ks`
- `live-knowledge-sources-mcp-kb`
- `live-knowledge-sources-kb`
- `airline-ops-regulatory-docs` Search index with sample docs

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
| Deployment summary exists | PASS |
| MCP KS exists | PASS |
| Fabric KS exists | PASS |
| MCP-only KB exists | PASS |
| Combined KB exists | PASS |
| Airline Ops index has docs | PASS |
| MCP retrieve | PASS with MCP activity or references |
| Fabric live retrieve | PASS if token is provided; SKIP if token is absent |
| App root HTTP 200 | PASS |
| `/api/status` | PASS and no secrets exposed |
| `/api/retrieve/mcp` | PASS |
| `/api/retrieve/fabric` | PASS live if token provided; offline replay if token absent |
| `/api/retrieve/combined` | PASS live if token provided; offline replay if token absent |
| Cleanup | PASS |
| Resource group deleted | PASS |

## Pass Criteria

The run passes when all required checks pass and Fabric-specific behavior is clear:

- With `FABRIC_USER_SEARCH_TOKEN`, retrieve responses contain `fabricOntology` activity and do not return `No relevant content was found`.
- Without `FABRIC_USER_SEARCH_TOKEN`, Fabric app routes return offline replay with a clear reason.
- Cleanup confirms the resource group no longer exists.

## Failure Conditions

Fail the run if:

- `FABRIC_WORKSPACE_ID` or `FABRIC_ONTOLOGY_ID` is missing.
- `fabric-ontology-ks` is not created.
- `live-knowledge-sources-kb` does not include the Fabric Knowledge Source.
- Live Fabric retrieve with a token does not show `fabricOntology` activity.
- Cleanup fails or the resource group remains.

## Reporting Requirements

The run must write:

```text
deployments/ext-liveks-byo-e2e/test-report.md
```

The report must include deployment mode, location, cleanup status, resource group, hosting mode, app URL, Search endpoint, progress bar, and pass/fail/skip checklist.

The report must not include API keys, raw access tokens, customer data, internal tenant secrets, passwords, or connection strings.

## Static Validation Before Live Run

```bash
bash -n scripts/deploy.sh scripts/e2e-test.sh scripts/destroy.sh scripts/ensure-azd-defaults.sh scripts/postprovision.sh scripts/deploy-static-webapp-api.sh
python3 -m py_compile scripts/postprovision.py
az bicep build --file infra/main.bicep --outfile .deployment/main.bicep.validate.json
npm --prefix static-app run build
git diff --check
```
