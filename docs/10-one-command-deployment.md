# One-Command Demo Deployment

This repo includes a one-command deployment path using Azure Developer CLI, Bicep, Fabric preprovisioning, and post-provision scripts.

The goal is to give a field engineer or customer a working platform demo with an explicit deployment mode.

## Choose A Deployment Mode

| Mode | What it creates | Fabric behavior | Recommended use |
| --- | --- | --- | --- |
| `byo-fabric` | Azure AI Search, Azure OpenAI, MCP KS/KB, Search index, demo app | Connects an existing Fabric workspace and ontology | Default public sample path |
| `mcp-only` | Azure AI Search, Azure OpenAI, MCP KS/KB, Search index, demo app | Skips Fabric KS creation | First MCP validation or tenants without Fabric |
| `full` | Azure/Foundry/Search/MCP/app resources plus Fabric capacity/workspace/lakehouse/ontology | Creates sample Airline Ops Fabric assets, then connects Fabric Ontology KS | Greenfield end-to-end sample path |

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

Full-run test specs:

- `docs/test-specs/e2e-byo-fabric.md`
- `docs/test-specs/e2e-mcp-only.md`
- `docs/test-specs/e2e-fabric-greenfield.md`
- `docs/test-specs/e2e-full-greenfield.md`

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
- Fabric live retrieval requires delegated user context. The demo app uses offline replay unless `FABRIC_USER_SEARCH_TOKEN` or a transient user token is provided.
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

`demo-app/` remains as an optional Next.js/App Service reference path for environments that prefer App Service and have `Microsoft.Web/serverFarms` quota available.

Required API routes:

| Route | Purpose |
| --- | --- |
| `GET /api/status` | Show runtime configuration without secrets. |
| `GET /api/deployment-summary` | Show generated/deployed resource metadata. |
| `POST /api/retrieve/mcp` | Run MCP-only retrieve or offline replay fallback. |
| `POST /api/retrieve/fabric` | Run Fabric retrieve when delegated token exists; otherwise offline replay. |
| `POST /api/retrieve/combined` | Run combined retrieve when Fabric live config exists; otherwise offline replay. |

All live retrieve calls go through server-side API routes.

The Knowledge Base model configuration uses Azure OpenAI through Search managed identity RBAC by default. If you run the REST samples manually, `AZURE_OPENAI_API_KEY` remains available as an optional local testing path, but the one-command deployment does not require it.

## Local Validation

Before deploying:

```bash
bash -n scripts/deploy.sh scripts/e2e-test.sh scripts/destroy.sh scripts/postprovision.sh scripts/deploy-static-webapp-api.sh
python3 -m py_compile scripts/postprovision.py scripts/fabric-provision.py scripts/fabric-destroy.py
az bicep build --file infra/main.bicep --outfile .deployment/main.bicep.validate.json
python3 scripts/postprovision.py --dry-run
python3 samples/python/build_payloads.py
python3 samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
bash scripts/no-secret-scan.sh
```

For the default Static Web Apps path:

```bash
cd static-app
npm install
npm run build
```

Before pushing to a Microsoft org repo, run the no-secret scan from the repo root:

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

The cleanup wrapper calls `azd down --purge --force` after confirmation and writes an ignored log under `.deployment/`.

## Fabric Live Mode

To test Fabric live mode in the demo app, configure one of these:

- server-side app setting `FABRIC_USER_SEARCH_TOKEN`, for a private demo only,
- or paste a transient raw delegated token in the Fabric tab.

The token must be scoped to:

```text
https://search.azure.com/.default
```

Do not prefix the token with `Bearer`.

## Phase 2 Candidates

- Fabric ontology authoring automation if public APIs and PM guidance are stable.
- Microsoft Graph upload for SharePoint-hosted policy PDFs.
- OBO delegated auth for user-specific Fabric live retrieval.
- Optional Search Index Knowledge Source path for indexed regulation documents.
