# Fabric Live BYO Validation

This is the fastest way to prove the Fabric Ontology Knowledge Source path after the one-command Azure deployment is working.

## What Happens In Two Minutes

```text
1. Put Fabric workspace + ontology IDs in a local env file.
2. Run the deployment wrapper with `--mode byo-fabric`.
3. postprovision creates the Fabric Ontology Knowledge Source.
4. The combined Knowledge Base references MCP + Fabric.
5. Open the demo app.
6. Paste a transient end-user Search access token only when you want live Fabric retrieve.
```

The repo never commits tenant IDs, tokens, or generated deployment summaries.

## Local Env Values

Copy `.env.sample` to `.env.external.local` or another ignored file:

```bash
DEPLOYMENT_MODE=byo-fabric
EXTERNAL_TENANT_ID=<external-tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext

FABRIC_WORKSPACE_ID=<fabric-workspace-guid>
FABRIC_ONTOLOGY_ID=<fabric-ontology-guid>
FABRIC_USER_SEARCH_TOKEN=<optional-raw-delegated-token>
```

Do not commit this file.

## Run

```bash
bash scripts/deploy.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name liveks-fabric-byo \
  --location eastus
```

The generated `deployments/<env>/deployment-summary.md` should show:

- Fabric workspace configured: `yes`
- Fabric KS: `fabric-ontology-ks`
- Combined KB: `live-knowledge-sources-kb`

For full create-call-load-delete validation:

```bash
bash scripts/e2e-test.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name ext-liveks-e2e-20260616 \
  --location eastus \
  --cleanup
```

The E2E report includes a Fabric KS check when the Fabric IDs are configured. If `FABRIC_USER_SEARCH_TOKEN` is present in the process environment, the report also requires live Fabric retrieve evidence instead of offline replay.

## App Validation

Open the app URL from the deployment summary:

- **MCP Live** runs immediately against Microsoft Learn MCP.
- **Fabric Ontology** uses offline replay until an end-user Search access token is provided.
- **Combined Trace** shows the same user experience path that will call both sources when Fabric live auth is configured.

For Fabric live retrieve, paste a raw end-user access token for:

```text
https://search.azure.com/.default
```

Do not prefix it with `Bearer`. The app sends the token once to the server-side API and does not store it.

## Notebook Validation

Open `notebooks/02-fabric-ontology-ks-airline-ops.ipynb`.

The notebook reads the same local env values:

```bash
FABRIC_WORKSPACE_ID
FABRIC_ONTOLOGY_ID
FABRIC_USER_SEARCH_TOKEN
```

Run it in dry-run/offline mode first, then set `RUN_LIVE_CALLS=true` only when your tenant, ontology, Search endpoint, and end-user Search token are ready.

## Boundary

This BYO path does not create Fabric workspace, capacity, lakehouse, or ontology items. It proves the public-preview Azure AI Search binding and the application experience around an existing Fabric semantic asset.

Use `--mode full` when you want the greenfield sample to create Fabric capacity, workspace, Lakehouse tables, ontology, GraphModel readiness, Azure AI Search resources, Knowledge Sources, Knowledge Bases, and the demo app in one flow.
