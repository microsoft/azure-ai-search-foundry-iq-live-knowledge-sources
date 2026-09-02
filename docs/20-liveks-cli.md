# LiveKS CLI

LiveKS is the plan-first lifecycle entry point for this accelerator. The same commands work through `./liveks` on macOS and Linux and `./liveks.ps1` in Windows PowerShell.

## First Use

The canonical credential-free checkout contract is:

<!-- compatibility-command-contract:start -->
```bash
./liveks try
./liveks bootstrap
./liveks profiles
./liveks doctor --profile offline --format json
bash scripts/validate-local.sh
```
<!-- compatibility-command-contract:end -->

The first command exits nonzero if the packaged known-answer, activity, reference, or source-identity contract fails. `bootstrap` installs the pinned CLI dependency into the ignored `.liveks/venv`. PowerShell uses `.\liveks.ps1` and ends with `.\scripts\validate-local.ps1`; see [API Compatibility](14-api-compatibility.md) for the generated Windows command block and evidence contract.

## Lifecycle

| Command | Cloud mutation | Purpose |
| --- | --- | --- |
| `try` | None | Print a checked-in answer and evidence trace. |
| `scenarios` | None | List, inspect, validate, or replay versioned synthetic scenario packs. |
| `init` | None | Write an ignored YAML environment ledger. |
| `doctor` | None | Check tools, versions, sign-in, providers, and required fields. |
| `plan` | None | Validate the selected profile's payload and ownership contract; preview profiles also build Bicep and the app. |
| `up` | Yes, after confirmation | Create only the selected profile's owned objects, then verify. |
| `verify` | Read/call only | Check deployed or reused objects and source evidence. |
| `mcp` | Read/call only | Discover and call `knowledge_base_retrieve` on the deployed Knowledge Base MCP endpoint. |
| `down` | Yes, after confirmation | Delete only assets owned by the environment. |
| `e2e` | Yes | Run `up` and either clean up or explicitly retain resources. |

`doctor` can issue read-only Azure CLI calls for live profiles. In `byo-fabric` and `three-source`, it also acquires a transient Fabric API token and confirms that the configured workspace and ontology are readable. The token is not serialized. `plan` writes local build and lock artifacts under ignored directories, but it does not run `azd env set`, `azd up`, or Fabric provisioning.

Scenario commands are credential-free and emit redacted machine output:

```bash
./liveks scenarios list
./liveks scenarios inspect combined --format json
./liveks scenarios validate --run-all --format json
./liveks scenarios run mcp --format json
```

See [Scenario Packs](18-scenario-packs.md). Scenario manifests select existing profiles but cannot bypass doctor, plan, ownership locks, or E2E cleanup.

For `search-index`, `mcp-search-index`, and `three-source`, `doctor` reads the existing index definition with an Azure AI Search bearer token. Their plans check payloads and generated-name collisions without Bicep, `azd`, npm, `PUT`, or `DELETE`. Direct combined profiles use GA GETs for Search Index KS and preview GETs for MCP/Fabric KS and KB names.

## Standard Run

Existing Search index, generally available lane:

```bash
./liveks init --profile search-index --env liveks-index
# Fill the existing Search values in .liveks/liveks-index.yaml.
./liveks doctor --env liveks-index
./liveks plan --env liveks-index
./liveks up --env liveks-index --query "<question>" --expect-term "<known term>"
./liveks verify --env liveks-index --query "<question>" --expect-term "<known term>"
./liveks down --env liveks-index
```

Preview MCP Server lane:

```bash
./liveks init --profile mcp-only --env liveks-mcp
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
./liveks verify --env liveks-mcp
./liveks mcp --env liveks-mcp
./liveks down --env liveks-mcp
```

Existing Search index plus preview MCP lane:

```bash
./liveks init --profile mcp-search-index --env liveks-combined
# Fill existing Search and Azure OpenAI deployment values.
./liveks doctor --env liveks-combined
./liveks plan --env liveks-combined
./liveks up --env liveks-combined --query "<index question>" --expect-term "<known term>"
./liveks verify --env liveks-combined --query "<index question>" --expect-term "<known term>"
./liveks mcp --env liveks-combined --auth bearer
./liveks down --env liveks-combined
```

Existing Search plus MCP plus native Fabric lane:

```bash
./liveks init --profile three-source --env liveks-three
# Fill existing Search, Azure OpenAI, Fabric workspace, and ontology values.
./liveks doctor --env liveks-three
./liveks plan --env liveks-three
./liveks up --env liveks-three --query "<index question>" --expect-term "<known term>" --fabric-query "<ontology question>"
./liveks verify --env liveks-three --query "<index question>" --expect-term "<known term>" --fabric-query "<ontology question>"
./liveks mcp --env liveks-three --auth bearer --expect-term "<known term>"
./liveks down --env liveks-three
```

Live commands require an environment name or a YAML path. When `--config` is omitted, LiveKS looks for `.liveks/<environment>.yaml`.

Use JSON output when cleanup evidence will be reviewed:

```bash
./liveks down --env liveks-full --yes --format json
```

Every provisioned preview profile must report `resource-group-absent=pass`. Data-plane-only `search-index`, `mcp-search-index`, and `three-source` instead require `search-index-preserved=pass`; `three-source` also requires `fabric-assets-preserved=pass`. A `full` run that created capacity must additionally report `fabric-capacity-absent=pass`. A missing summary or unresolved ownership produces partial cleanup instead of a deletion claim.

For `three-source`, `byo-fabric`, and `full`, `mcp` attaches delegated source authorization by default. It records text-block and expected-term counts but never persists the endpoint, query, response content, key, or token. A call without `--expect-term` can pass protocol checks but reports `grounding-content=warn`; use a known non-sensitive fact for source-content acceptance. See [Call the Knowledge Base Through MCP](22-knowledge-base-mcp.md).

For `mcp-search-index` and `three-source`, native MCP uses the configured preview combined KB and requires `--auth bearer`. Source routing must already be proved by ordered REST checks because native MCP output has a different response envelope.

## Confirmation Rules

Interactive `up` requires this exact phrase:

```text
create <environment>
```

Interactive `down` requires:

```text
delete <environment>
```

The `full` profile additionally requires `--accept-fabric-capacity`, even when `--yes` is supplied, because it creates a billable Fabric capacity.

```bash
./liveks up --env liveks-full --accept-fabric-capacity
```

## Full Lifecycle Test

Choose exactly one cleanup behavior:

```bash
./liveks e2e --env liveks-mcp --cleanup --yes
./liveks e2e --env liveks-mcp --keep-resources --yes
```

The combined data-plane profile accepts `--query`, repeatable `--expect-term`, `--mcp-query`, and `--combined-query`. It creates only three lock-owned Search data-plane objects and cleans them up before requiring that the BYO index is still readable.

Use `--keep-resources` only while debugging. Release evidence should include successful cleanup.

The protected `mcp-search-index` canary is stricter: it is manual-only, accepts `--cleanup` only, derives a unique environment per run, serializes runs through workflow concurrency, and performs a second guarded cleanup with `always()`. Missing configuration fails before Azure login.

Every E2E run writes four ignored artifacts under `deployments/<environment>/`:

| Artifact | Purpose |
| --- | --- |
| `e2e-report.json` | Complete nested lifecycle result for local diagnosis. |
| `test-report.md` | Detailed maintainer report compatible with the evidence summarizer. |
| `evidence-capsule.json` | Allowlist-sanitized machine manifest with revision, profile, assertion statuses, proved source types, and source-report digest. |
| `evidence-capsule.md` | Human-readable view of the same sanitized assertion set. |

The capsules omit the environment name, check messages, resource identifiers, endpoints, raw responses, and credentials. Review them before sharing because the detailed reports beside them remain local-only.

The protected workflow uploads a separate `canary-evidence.json` allowlist capsule only. It adds retry categories/counts, source evidence counts, generated/BYO ownership classes, cost-sensitive classes, cleanup status, and a digest of the non-uploaded detailed report.

## Machine-Readable Output

Configuration and lifecycle commands accept `--format json` and use stable status envelopes:

```bash
./liveks doctor --env liveks-mcp --format json
./liveks plan --env liveks-mcp --format json
```

| Exit code | Meaning |
| --- | --- |
| `0` | Pass or warning-only result. |
| `1` | Runtime, deployment, or verification failure. |
| `2` | Invalid configuration or command usage. |
| `3` | Required confirmation was not provided. |
| `4` | Cleanup was partial and needs follow-up. |

JSON output and lock files redact secret values. Commands executed with delegated tokens do not print request bodies.

## Compatibility Entry Points

The v1 shell commands remain thin POSIX wrappers:

| Compatibility command | v2 target |
| --- | --- |
| `scripts/deploy.sh` | `liveks up` |
| `scripts/e2e-test.sh` | `liveks e2e` |
| `scripts/destroy.sh` | `liveks down` |
| `tools/doctor.py` | `liveks doctor` |
| `tools/validate.py` | `liveks plan` |

Legacy `--mode`, `--env-name`, `--location`, `--fabric-location`, and `--env-file` arguments are translated into the v2 configuration model. The deploy wrapper also preserves `--skip-app-build`, `--skip-dry-run`, and `--postprovision-only`. New automation should use the public v2 arguments.

## Tool Compatibility

The generated [compatibility matrix](14-api-compatibility.md#continuously-checked-compatibility) separates enforced minimums, exact CI combinations, dev container pins, and unverified combinations. `config/compatibility.yaml` is the machine-readable authority; this page does not maintain a second version table.

## Generated Artifacts

| Path | Contents |
| --- | --- |
| `.liveks/<env>.yaml` | Authored environment ledger. |
| `.liveks/<env>.lock.json` | Redacted resolved values, sources, ownership, and last lifecycle state. |
| `.deployment/<env>/` | Local Bicep and plan output. |
| `deployments/<env>/` | Deployment and verification reports. |

All of these paths are ignored. Do not move raw evidence into tracked documentation.
