# MCP-Only Full-Run Test Specification

This test validates the fastest deployment path for users who want to try Azure AI Search MCP Server Knowledge Source without preparing Fabric assets.

## Purpose

Prove that the repo can deploy a working MCP Server Knowledge Source, Knowledge Base, Search index, and demo app without requiring Fabric workspace or ontology inputs.

This path is the fallback and first-run validation path for tenants that are not ready for Fabric.

## Inputs

Use an ignored local env file, such as `.env.external.local`:

```bash
DEPLOYMENT_MODE=mcp-only
EXTERNAL_TENANT_ID=<tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext
```

Fabric values are ignored in this mode.

## Command

```bash
bash scripts/e2e-test.sh \
  --mode mcp-only \
  --env-file .env.external.local \
  --env-name ext-liveks-mcp-e2e \
  --location eastus \
  --cleanup
```

## Expected Azure Resources

- Resource group: `rg-ext-liveks-mcp-e2e`
- Azure AI Search
- Azure OpenAI account and `gpt-4o-mini` deployment
- Storage account
- Static Web App and managed Functions API

## Expected Knowledge Assets

- `microsoft-learn-mcp-ks`
- `live-knowledge-sources-mcp-kb`
- `live-knowledge-sources-kb`
- `airline-ops-regulatory-docs` Search index

No Fabric Knowledge Source is required.

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
| Fabric KS check | SKIP with reason `Deployment mode is mcp-only` |
| MCP-only KB exists | PASS |
| Combined KB exists | PASS |
| Airline Ops index has docs | PASS |
| MCP retrieve | PASS with MCP activity or references |
| Fabric live retrieve | SKIP |
| App root HTTP 200 | PASS |
| `/api/status` | PASS and shows `deploymentMode=mcp-only` |
| `/api/retrieve/mcp` | PASS |
| `/api/retrieve/fabric` | PASS offline replay with mcp-only reason |
| `/api/retrieve/combined` | PASS offline replay with mcp-only reason |
| Cleanup | PASS |
| Resource group deleted | PASS |

## Pass Criteria

The run passes when MCP live retrieval works and Fabric behavior is explicitly skipped or offline, not silently attempted.

Required MCP evidence:

- retrieve response contains MCP activity, or
- retrieve response contains references from the MCP-backed Knowledge Base.

## Failure Conditions

Fail the run if:

- Fabric KS creation is required or blocks deployment.
- MCP retrieve has no activity or references.
- `/api/retrieve/fabric` tries live Fabric retrieval instead of returning offline replay in `mcp-only`.
- Cleanup fails or the resource group remains.

## Reporting Requirements

The run must write:

```text
deployments/ext-liveks-mcp-e2e/test-report.md
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
