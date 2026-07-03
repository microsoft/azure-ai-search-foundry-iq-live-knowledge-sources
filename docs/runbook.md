# Execution Runbook

Use this sequence when you want to move from zero setup to a live validation path without losing the safety boundary.

## 1. Prepare Environment Files

Start by choosing the smallest profile that matches the run. Do not put real tenant IDs, workspace IDs, ontology IDs, tokens, endpoints, or keys in committed files.

For deployment, prefer the Azure Developer CLI environment as the primary configuration store. The wrapper sets common values for you from flags such as `--mode`, `--env-name`, `--location`, and `--fabric-location`, then writes them into the selected `azd` environment.

Use ignored local env files only for values that are awkward or unsafe to type repeatedly, such as BYO Fabric IDs, an external tenant profile, or optional private-demo tokens:

```bash
cp env/byo-fabric.env.example .env.external.local
```

Use `.env.sample` as the complete variable catalog for manual REST testing and notebooks. Do not copy it into a committed file.

When you want to set values directly in the selected `azd` environment, use:

```bash
azd env new liveks-mcp
azd env set DEPLOYMENT_MODE mcp-only
azd env set AZURE_LOCATION eastus
azd env get-values
```

| Mode | Required env values before deploy | Usually optional | Recommended command shape |
| --- | --- | --- | --- |
| `offline` | None | `RUN_LIVE_CALLS=false` for notebooks | No env file needed |
| `mcp-only` | None | `MCP_KNOWLEDGE_SOURCE_NAME`, `MCP_SERVER_URL`, `MCP_TOOL_NAME` if overriding defaults | `bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus` |
| `byo-fabric` | `FABRIC_WORKSPACE_ID`, `FABRIC_ONTOLOGY_ID` | `EXTERNAL_TENANT_ID`, `EXTERNAL_AZURE_CONFIG_DIR`, `FABRIC_USER_SEARCH_TOKEN` | `bash scripts/deploy.sh --mode byo-fabric --env-file .env.external.local --env-name liveks-byo --location eastus` |
| `full` | No existing Fabric IDs when creating sample assets; choose a Fabric region with quota | `FABRIC_CAPACITY_MODE=create`, `FABRIC_CAPACITY_SKU=F2`, `FABRIC_CAPACITY_ADMIN`, generated asset names | `bash scripts/deploy.sh --mode full --env-name liveks-full --location eastus --fabric-location westus3` |

For `byo-fabric`, the local env file should look like this:

```bash
DEPLOYMENT_MODE=byo-fabric
FABRIC_WORKSPACE_ID=<fabric-workspace-guid>
FABRIC_ONTOLOGY_ID=<fabric-ontology-guid>

# Optional, only for isolated external-tenant testing.
EXTERNAL_TENANT_ID=<tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext

# Optional, only for live Fabric retrieve validation.
# Keep it raw, with no "Bearer " prefix.
FABRIC_USER_SEARCH_TOKEN=<raw-user-token-for-https://search.azure.com/.default>
```

For `full`, prefer command-line flags for the mode and regions. Use `azd env set` only when you need explicit Fabric capacity settings:

```bash
azd env new liveks-full
azd env set DEPLOYMENT_MODE full
azd env set FABRIC_CAPACITY_MODE create
azd env set FABRIC_CAPACITY_SKU F2
azd env set FABRIC_CAPACITY_ADMIN <admin-upn-for-created-capacity>
azd env set FABRIC_LOCATION westus3
```

If you run the REST samples manually instead of the deployment wrapper, use `.env.sample` as the full variable catalog. Manual REST calls need live values such as `SEARCH_ENDPOINT`, `SEARCH_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_ID`, and `AZURE_OPENAI_MODEL_NAME`. The one-command deployment writes the corresponding Azure runtime values into `azd` and app settings for you.

Validate a profile before a live run:

```bash
python3 tools/validate.py --profile offline --format json
python3 tools/validate.py --profile mcp-only --format json
python3 tools/validate.py --profile byo-fabric --env-file .env.external.local --format json
```

## 2. Inspect Offline Traces

Run this first. It requires no cloud resources.

```bash
python3 samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

Check for:

- `activity` entries that identify the selected source.
- `references` entries with source-specific evidence.
- `sourceData` previews that show what the live source returned.

Next: read [Offline Replay](09-offline-replay.md) if the trace fields are unfamiliar.

## 3. Run Local Preflight

Run the agent-readable checks before deploying.

```bash
python3 tools/doctor.py --format json
python3 tools/validate.py --profile offline --format json
```

Then run the full local validation gate:

```bash
bash scripts/validate-local.sh
```

Check for a clean pass across shell syntax, Python compile checks, notebook JSON, sample payloads, offline responses, no-secret scan, Static Web Apps build, and optional Bicep validation.

Next: choose a live path in [Choose a Pattern](02-choose-a-pattern.md).

## 4. Deploy MCP-only

Use this for the fastest live validation path.

```bash
bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus
```

Check for:

- Azure AI Search and Azure OpenAI resources.
- Microsoft Learn MCP Server Knowledge Source.
- MCP-only Knowledge Base.
- Demo app URL in the generated deployment summary.
- Retrieve activity or references showing `microsoft_docs_search`.

Next: open the app URL and run the MCP tab, or inspect the REST path in [MCP Server KS](03-mcp-server-ks.md).

## 5. Connect BYO Fabric

Use this only when you already have Fabric workspace and ontology IDs.

Create an ignored local env file from the sample catalog and provide the Fabric IDs there.

```bash
bash scripts/deploy.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name liveks-byo \
  --location eastus
```

Check for:

- Fabric Ontology Knowledge Source creation.
- Combined Knowledge Base creation.
- Live Fabric retrieve with delegated source authorization, or a clear offline replay explanation when no user token is available.
- No raw tokens, tenant IDs, workspace IDs, ontology IDs, or live payloads committed to git.

Next: follow [Fabric Live BYO Validation](11-fabric-live-byo-validation.md).

## 6. Run Full Greenfield Only When Ready

Use `full` for maintainer demos or greenfield rehearsals where Fabric capacity creation is acceptable.

```bash
bash scripts/deploy.sh \
  --mode full \
  --env-name liveks-full \
  --location eastus \
  --fabric-location westus3
```

Check for:

- Fabric capacity, workspace, Lakehouse, ontology, and GraphModel readiness.
- Azure AI Search Knowledge Sources and Knowledge Bases.
- Demo app load.
- Retrieve evidence recorded in ignored deployment output.
- Cleanup evidence when the run is complete.

Next: use [One-Command Deployment](10-one-command-deployment.md) and [Public Preview Limitations](13-public-preview-limitations.md) before making public claims.

## 7. Clean Up

Clean up the selected azd environment.

```bash
bash scripts/destroy.sh --env-name liveks-mcp
```

For `full`, the cleanup wrapper attempts generated Fabric cleanup first, then calls `azd down --purge --force` even if Fabric cleanup needs manual follow-up.

Check for:

- Deleted Azure resources.
- Deleted generated Fabric assets where applicable.
- Manual follow-up clearly reported if Fabric cleanup could not complete automatically.

## Evidence Rules

Keep generated logs, reports, screenshots, and deployment summaries in ignored paths such as `.deployment/`, `deployments/`, and `scratch/`.

When summarizing a run, prefer:

- deployment mode,
- status,
- sanitized resource names,
- source names,
- trace counts,
- cleanup status.

Do not paste raw access tokens, raw live retrieve responses, tenant IDs, workspace IDs, ontology IDs, or screenshots with sensitive values into issues, docs, PRs, or public summaries.
