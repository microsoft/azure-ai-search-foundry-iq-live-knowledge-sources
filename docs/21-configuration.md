# Configuration

LiveKS v2 uses one ignored YAML file as the human-managed deployment ledger. Profile defaults, schema validation, Bicep parameters, scripts, and generated dotenv examples all resolve from the same configuration contract.

## Create A Ledger

```bash
./liveks init --profile search-index --env liveks-index
./liveks init --profile mcp-search-index --env liveks-combined
./liveks init --profile mcp-only --env liveks-mcp
./liveks init --profile byo-fabric --env liveks-byo
./liveks init --profile full --env liveks-full
```

The default location is `.liveks/<environment>.yaml`. The directory is ignored by git and files are written with owner-only permissions where the operating system supports them.

## Search Index Example

```yaml
version: 2
profile: search-index
environment: liveks-index
search:
  endpoint: https://<search-service>.search.windows.net
  index_name: <existing-index-name>
  semantic_configuration_name: <semantic-configuration-name>
  search_fields:
    - content
  source_data_fields:
    - id
    - title
```

This stable lane uses Microsoft Entra bearer authentication from Azure CLI. It reuses the Search service and index, derives unique KS and KB names from the environment, and never stores an API key. Field lists are optional, but any supplied values must exist and satisfy the required searchable or retrievable capability.

## MCP + Search Index Example

```yaml
version: 2
profile: mcp-search-index
environment: liveks-combined
search:
  endpoint: https://<search-service>.search.windows.net
  index_name: <existing-index-name>
  semantic_configuration_name: <semantic-configuration-name>
  search_fields:
    - content
  source_data_fields:
    - id
    - title
    - content
openai:
  endpoint: https://<azure-openai-resource>.openai.azure.com
  deployment_name: <existing-chat-deployment>
  model_name: <model-name>
```

This profile reuses the Search service, index, and Azure OpenAI deployment. Its defaults pin `search.index_api_version` to GA `2026-04-01` and `search.preview_api_version` to `2026-05-01-preview`. The generated Search Index KS, MCP KS, and combined KB names are derived from the environment unless explicitly overridden.

## MCP-only Example

```yaml
version: 2
profile: mcp-only
environment: liveks-mcp
azure:
  location: eastus
```

Profile defaults supply Search, OpenAI, MCP, hosting, and naming values. Add only intentional overrides.

## BYO Fabric Example

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

Set the optional delegated token only in the process environment:

```bash
export FABRIC_USER_SEARCH_TOKEN="$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)"
```

The YAML stores the environment variable name, never the token. LiveKS does not project this secret into `azd env` or serialize it into the lock.

## Full Example

```yaml
version: 2
profile: full
environment: liveks-full
azure:
  location: eastus
fabric:
  mode: create
  location: westus3
  capacity_sku: F2
```

`full` rejects `fabric.workspace_id` and `fabric.ontology_id`. Use `byo-fabric` to reuse existing assets.

## External Tenant Example

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

`azure.cli_config_dir` becomes `AZURE_CONFIG_DIR` only for child processes. `doctor` confirms that the active Azure CLI tenant and subscription match the authored values before planning.

## Field Groups

The complete machine-readable contract is [`config/schema.yaml`](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/config/schema.yaml). Common groups are:

| Group | Examples |
| --- | --- |
| `deployment` | `mode` |
| `azure` | location, subscription, tenant, resource group, hosting mode |
| `search` | Single-lane API version or separate index/preview versions, endpoint, SKU, index and semantic configuration, optional field lists, KS, and KB names |
| `mcp` | HTTPS server URL and allowed tool name |
| `openai` | endpoint, deployment, model name/version, capacity |
| `fabric` | create/BYO mode, location, capacity, workspace, ontology, secret reference |
| `runtime` | telemetry and optional live-call behavior |

Unknown fields fail validation. GUIDs, HTTPS URLs, enumerations, integer bounds, booleans, required BYO values, and profile/mode agreement are checked before cloud mutation.

## Resolution Order

Lowest to highest precedence:

1. Executable profile defaults in `profiles/<profile>.yaml`.
2. Optional legacy dotenv values supplied with `--env-file`.
3. Authored YAML values.
4. Hidden v1 compatibility flags such as `--location`.
5. Derived resource group, name salt, Search Index KS/KB names, combined profile KS/KB names, and generated Fabric names when absent.

The final redacted result and the source of each value are written to `.liveks/<environment>.lock.json` by `plan` and later lifecycle commands.

`azd env` is a deployment projection, not the authored source of truth. Preview deployment profiles select or create the named `azd` environment and write resolved non-secret values immediately before preview and provisioning. The stable `search-index` profile is data-plane-only and does not create or read an `azd` environment.

`search.api_version` fails closed by single-lane profile: `search-index` requires generally available `2026-04-01`, while `mcp-only`, `byo-fabric`, and `full` require `2026-05-01-preview`. `mcp-search-index` omits that ambiguous field and requires both `search.index_api_version=2026-04-01` and `search.preview_api_version=2026-05-01-preview`. Source kinds and retrieve shapes cannot be substituted across those contracts. See [API Compatibility](14-api-compatibility.md).

## Legacy Dotenv Migration

Existing ignored dotenv files can be imported without shell evaluation:

```bash
./liveks init \
  --profile byo-fabric \
  --env liveks-byo \
  --from-env .env.external.local
```

The parser accepts dotenv-style assignments but does not execute command substitutions or shell syntax. Secret values become environment references. Review the generated YAML, then stop using the dotenv file for the deployment path.

Generated `.env.sample` and `env/*.env.example` files remain for REST, notebook, and v1 compatibility. They are produced from the YAML schema and profiles by `scripts/generate_env_examples.py`; they are not the v2 configuration authority.

## Native MCP Client Inputs

`./liveks mcp --env <environment>` derives the Search endpoint, API version, Knowledge Base name, resource group, and service name from the selected deployment. Do not duplicate them in a dotenv file.

Authentication is acquired at call time:

- `--auth admin-key` reads the sample deployment's Search key through Azure CLI and keeps it in memory only.
- `--auth bearer` acquires an Azure AI Search bearer token for an identity with **Search Index Data Reader**.
- Fabric profiles acquire a separate user token and send its raw value in `x-ms-query-source-authorization`.

The generated MCP report contains counts and normalized statuses only. It does not contain the endpoint, query, expected terms, response content, key, or token.

`--query` and repeatable `--expect-term` values are runtime acceptance inputs, not deployment configuration. Supply a known non-sensitive fact when validating Fabric-backed MCP content. Without an expected term, the command validates protocol execution and reports grounding as unverified.

The same runtime inputs are accepted by `liveks verify` for `search-index` and `mcp-search-index`. The combined profile also accepts `--mcp-query` and `--combined-query`; its expected terms are matched only against Search Index reference `sourceData`. Reports record only match counts, source types, and normalized status, not questions, terms, answers, source data, or endpoints.

## Safe Review

```bash
./liveks doctor --env liveks-byo --format json
./liveks plan --env liveks-byo --format json
```

Do not commit `.liveks/`, `.azure/`, dotenv files, deployment reports, or token-bearing shell history. Use placeholders in tracked examples and sanitized names/counts in review evidence.
