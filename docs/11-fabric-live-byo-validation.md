# BYO Fabric Validation

Use this profile when the Fabric workspace and ontology already exist. LiveKS creates the Azure and Foundry IQ side, connects the existing ontology, and never takes ownership of the BYO Fabric assets.

## Configure

```bash
./liveks init --profile byo-fabric --env liveks-byo
```

Edit `.liveks/liveks-byo.yaml`:

```yaml
version: 2
profile: byo-fabric
environment: liveks-byo
azure:
  location: eastus
fabric:
  workspace_id: 11111111-1111-1111-1111-111111111111
  ontology_id: 22222222-2222-2222-2222-222222222222
  user_search_token:
    env: FABRIC_USER_SEARCH_TOKEN
```

Do not put a token literal in YAML. The token reference is optional for deployment but live Fabric verification needs a raw end-user token scoped to `https://search.azure.com/.default`.

```bash
export FABRIC_USER_SEARCH_TOKEN="$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)"
```

Do not add a `Bearer` prefix.

## Plan And Deploy

```bash
./liveks doctor --env liveks-byo
./liveks plan --env liveks-byo
./liveks up --env liveks-byo
```

The BYO doctor check uses a transient Fabric API token to read the configured workspace and ontology. A missing asset or tenant permission therefore fails before `azd up`; no token is written to YAML, the lock, or `azd env`.

The generated deployment summary should identify the Fabric KS and combined KB without exposing workspace or ontology IDs publicly.

## Verify

```bash
./liveks verify --env liveks-byo
```

Required evidence:

1. the resource group and demo app are reachable,
2. MCP retrieve returns MCP activity or references,
3. Fabric retrieve returns `fabricOntology` evidence in live mode,
4. combined retrieve returns live evidence from the source or sources selected by the planner; the two preceding checks prove each path independently.

The verifier acquires a delegated Search token transiently from the active Azure CLI account. It sends the token in the request body to the managed API and does not serialize it into reports or locks.

## App And Notebook

The app's MCP tab runs immediately. Fabric and Combined tabs require delegated authorization for live retrieval; without it, the API returns clearly labeled offline replay.

The Fabric notebook reads compatible environment variables for manual exploration. Keep `RUN_LIVE_CALLS=false` until Search, Fabric, and delegated authorization are ready.

## Cleanup Boundary

```bash
./liveks down --env liveks-byo
```

Cleanup deletes the generated Azure resources only. The YAML profile and environment lock both mark the Fabric capacity, workspace, and ontology as `reuse`; Fabric deletion is not invoked.

Use `full` only when LiveKS should create and later delete the Fabric capacity and sample assets.
