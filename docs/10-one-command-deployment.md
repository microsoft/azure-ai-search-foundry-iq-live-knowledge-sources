# One-Command Demo Deployment

This repo includes a one-command deployment path using Azure Developer CLI, Bicep, Fabric preprovisioning, and post-provision scripts.

The goal is to give a field engineer or customer a working platform demo with an explicit deployment mode.

## Choose A Deployment Mode

| Mode | What it creates | Fabric behavior | Recommended use |
| --- | --- | --- | --- |
| `byo-fabric` | Azure AI Search, Azure OpenAI, MCP KS/KB, Search index, demo app | Connects an existing Fabric workspace and ontology | Primary live Fabric sample path |
| `mcp-only` | Azure AI Search, Azure OpenAI, MCP KS/KB, Search index, demo app | Skips Fabric KS creation | First MCP validation or tenants without Fabric |
| `full` | Azure/Foundry/Search/MCP/app resources plus Fabric capacity/workspace/lakehouse/ontology | Creates sample Airline Ops Fabric assets, then connects Fabric Ontology KS | Greenfield end-to-end sample path |

## Prerequisites

Install or confirm:

```text
azd, az, python3, node, npm
```

Sign in before deploying:

```bash
azd auth login
az login --tenant <tenant-id>
```

For isolated external-tenant testing, create an ignored `.env.external.local` file from `.env.sample`, set `EXTERNAL_TENANT_ID` and `EXTERNAL_AZURE_CONFIG_DIR`, then run:

```bash
scripts/external-tenant-login.sh --env-file .env.external.local
```

For Fabric paths:

- `byo-fabric`: provide `FABRIC_WORKSPACE_ID` and `FABRIC_ONTOLOGY_ID`.
- `full`: confirm Fabric capacity quota and choose `--fabric-location` for a region where capacity creation is allowed.
- live Fabric retrieve: provide a raw user token only in ignored local env/app settings or transient UI input; do not commit it.

The wrapper requires a mode unless `DEPLOYMENT_MODE` is already set in the loaded env file or the selected azd environment:

```bash
bash scripts/deploy.sh --mode byo-fabric
```

Direct `azd up` remains supported for template users. The preprovision hook defaults direct `azd up` to `mcp-only` so it can run without Fabric IDs, but the recommended tutorial path is `scripts/deploy.sh` with an explicit mode.

## Wrapper Behavior

The wrapper prints an ASCII step bar, streams the underlying Azure output, and writes a local ignored log:

```text
.deployment/deploy-YYYYMMDD-HHMMSS.log
```

It does not parse `azd` or Bicep progress output. It uses command exit codes for required steps and treats version/environment displays as diagnostics, so Azure CLI or SDK output format changes should not break the deployment flow.

For `full` mode, the wrapper provisions Fabric capacity/workspace/lakehouse/ontology/GraphModel before `azd up`. This keeps long Fabric graph-loading work outside the Azure Developer CLI postprovision hook. After `azd up` finishes, the normal postprovision path creates the Azure AI Search Knowledge Sources, Knowledge Bases, Search index, and smoke-test summary.

Common options:

```bash
bash scripts/deploy.sh --mode byo-fabric --env-file .env.external.local --env-name liveks-byo --location eastus
bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus
bash scripts/deploy.sh --mode full --env-name liveks-full --location eastus --fabric-location westus3
bash scripts/deploy.sh --skip-app-build
bash scripts/deploy.sh --postprovision-only
```

For a full live rehearsal that creates resources, validates Knowledge Sources, loads the demo app, and deletes the resources afterward:

```bash
bash scripts/e2e-test.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name ext-liveks-e2e-20260616 \
  --location eastus \
  --cleanup
```

The E2E harness writes:

```text
deployments/<env>/test-report.md
```

The report is ignored by git and includes a checklist, progress bar, resource names, app URL, and pass/fail notes.
Use [Public Preview Limitations and Caveats](13-public-preview-limitations.md) before turning deployment results into customer-facing or blog claims.

The default hosting path is Azure Static Web Apps with a managed Functions API. This avoids the `Microsoft.Web/serverFarms` quota problem that can block App Service Plan creation in constrained demo subscriptions.

Static Web Apps is not available in every Azure region. The template deploys Search/OpenAI/Storage to `AZURE_LOCATION` and deploys Static Web Apps to `AZURE_STATIC_WEB_APP_LOCATION`, defaulting to `eastus2`.

If you opt into App Service hosting and the run fails while creating `Microsoft.Web/serverFarms` with `Current Limit (Total VMs): 0`, the subscription cannot create an App Service Plan in that region. Use the default Static Web Apps path, request quota for at least one App Service worker, or use a subscription with App Service quota.

## What v1 Deploys

- Azure AI Search
- Azure OpenAI account and chat model deployment
- Search managed identity with `Cognitive Services User` access to Azure OpenAI for Knowledge Base answer synthesis
- Storage account for generated/sample assets
- Azure Static Web Apps demo frontend
- Managed Azure Functions API for server-side retrieve calls
- Microsoft Learn MCP Server Knowledge Source
- MCP-only Knowledge Base
- Combined Knowledge Base skeleton
- Search index for Airline Ops regulation-style sample documents
- Optional F2 Microsoft Fabric capacity for `full` mode
- Fabric workspace, Airline Ops Lakehouse tables, and Airline Ops ontology for `full` mode
- Ontology-backed GraphModel definition and readiness probe for `full` mode
- Generated local deployment summary markdown

## Fabric Automation Status

Fabric deployment is mode-dependent:

- `byo-fabric` requires `FABRIC_WORKSPACE_ID` and `FABRIC_ONTOLOGY_ID` and creates the Azure AI Search Fabric Ontology Knowledge Source.
- `mcp-only` ignores Fabric IDs and creates only the MCP path.
- `full` creates or reuses a Fabric capacity before `azd up`, creates a Fabric workspace, creates a Lakehouse, uploads the Airline Ops CSV files, loads Delta tables, creates an ontology definition, updates the ontology-backed GraphModel definition, waits for a passing GraphModel probe, writes generated Fabric IDs into `azd env`, and then creates the Azure AI Search Fabric Ontology Knowledge Source.
- If your subscription has no Fabric quota in the chosen region, set `--fabric-location` to a region with quota or use `byo-fabric`.
- Fabric live retrieval requires an end-user Search access token for source authorization. The demo app uses offline replay unless `FABRIC_USER_SEARCH_TOKEN` or a transient raw user token is provided.
- SharePoint PDF upload is not automated. Use the local synthetic regulatory documents for v1. Add Microsoft Graph upload later when tenant/admin consent and content governance are clear.

## Generated Summary

`scripts/postprovision.py` writes:

```text
deployments/<env>/deployment-summary.md
```

The file is ignored by git. It contains:

- App URL
- deployment mode
- hosting mode and Static Web Apps region
- Search endpoint
- OpenAI endpoint
- resource names
- Knowledge Source and Knowledge Base names
- notebook environment values
- MCP smoke-test trace summary

It does not include API keys, tokens, or customer data.

## Demo App

The default demo app is under `static-app/`. It deploys as Azure Static Web Apps plus managed Functions API, so browser code never receives Search admin keys or OpenAI keys.

Required API routes:

| Route | Purpose |
| --- | --- |
| `GET /api/status` | Show runtime configuration without secrets. |
| `GET /api/deployment-summary` | Show generated/deployed resource metadata. |
| `POST /api/retrieve/mcp` | Run MCP-only retrieve or offline replay fallback. |
| `POST /api/retrieve/fabric` | Run Fabric retrieve when source authorization exists; otherwise offline replay. |
| `POST /api/retrieve/combined` | Run combined retrieve when Fabric live config exists; otherwise offline replay. |

All live retrieve calls go through server-side API routes.

The Knowledge Base model configuration uses Azure OpenAI through Search managed identity RBAC by default. If you run the REST samples manually, `AZURE_OPENAI_API_KEY` remains available as an optional local testing path, but the one-command deployment does not require it.

## Local Validation

Before deploying or pushing to a Microsoft org repo, run the local validation gate:

```bash
bash scripts/validate-local.sh
```

Use strict mode when you want missing optional tools, such as Azure CLI for Bicep validation, to fail instead of skip:

```bash
bash scripts/validate-local.sh --strict
```

The validation script runs:

- shell syntax checks
- Python compile checks
- notebook JSON validation
- sample payload generation
- offline response inspection
- no-secret scan
- Static Web Apps demo build
- Bicep build when Azure CLI is available

You can also run the no-secret scan directly:

```bash
bash scripts/no-secret-scan.sh
```

The scan checks tracked and unignored local files for known tenant values, raw JWT-shaped tokens, and API-key-like env values. Keep real tenant IDs, tokens, keys, deployment logs, generated reports, and local screenshots in ignored files only.

After deploying:

```bash
azd env get-values
python3 scripts/postprovision.py
```

Cleanup:

```bash
bash scripts/destroy.sh --env-name liveks-dev
```

The cleanup wrapper first attempts generated Fabric cleanup, then calls `azd down --purge --force` even if Fabric cleanup needs manual follow-up. Fabric provisioning writes non-secret partial summaries under `deployments/<env>/` so `fabric-destroy.py` can find generated capacity/workspace assets after a failed `full` run.

## Fabric Live Mode

To test Fabric live mode in the demo app, configure one of these:

- server-side app setting `FABRIC_USER_SEARCH_TOKEN`, for a private demo only,
- or paste a transient raw end-user Search token in the Fabric tab.

The token must be scoped to:

```text
https://search.azure.com/.default
```

Do not prefix the token with `Bearer`.

## Phase 2 Candidates

- Production-grade Fabric ontology authoring refinements if public APIs and PM guidance evolve beyond the current sample automation.
- Microsoft Graph upload for SharePoint-hosted policy PDFs.
- Production app token acquisition and OBO plumbing for user-specific Fabric live retrieval.
- Optional Search Index Knowledge Source path for indexed regulation documents.
