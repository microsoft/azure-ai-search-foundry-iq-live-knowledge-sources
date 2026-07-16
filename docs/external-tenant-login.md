# External Tenant Login

Use an isolated Azure CLI cache when the target Fabric and Azure resources are in a tenant different from your normal CLI profile.

## Configure The Ledger

```bash
./liveks init --profile byo-fabric --env external-liveks-byo
```

Add the target identity and isolated cache path:

```yaml
version: 2
profile: byo-fabric
environment: external-liveks-byo
azure:
  tenant_id: 33333333-3333-3333-3333-333333333333
  subscription_id: 44444444-4444-4444-4444-444444444444
  cli_config_dir: ~/.azure-liveks-external
  location: eastus
fabric:
  workspace_id: 11111111-1111-1111-1111-111111111111
  ontology_id: 22222222-2222-2222-2222-222222222222
```

The file is under ignored `.liveks/`. LiveKS passes `AZURE_CONFIG_DIR` only to its child Azure CLI processes.

## Sign In

For the interactive shell that performs login, use the same isolated cache:

```bash
export AZURE_CONFIG_DIR="$HOME/.azure-liveks-external"
az login --tenant 33333333-3333-3333-3333-333333333333
az account set --subscription 44444444-4444-4444-4444-444444444444
azd auth login
```

MFA and Conditional Access still require user interaction. Azure CLI and Azure Developer CLI maintain separate authentication contexts.

## Check Alignment

```bash
./liveks doctor --env external-liveks-byo
```

The doctor checks that the active Azure CLI tenant and subscription match the YAML before any plan or deployment proceeds.

## Delegated Search Token

For live Fabric retrieve:

```bash
export FABRIC_USER_SEARCH_TOKEN="$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)"
```

The token is passed raw as source authorization. Do not add `Bearer`, put it in YAML, save it in `azd env`, or paste it into reports.

## Legacy Helper

`scripts/external-tenant-login.sh --env-file <ignored-dotenv>` remains available for existing v1 workflows. New deployments should keep tenant, subscription, and cache-path settings in the LiveKS YAML ledger.
