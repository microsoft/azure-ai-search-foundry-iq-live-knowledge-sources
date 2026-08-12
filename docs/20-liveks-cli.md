# LiveKS CLI

LiveKS is the plan-first lifecycle entry point for this accelerator. The same commands work through `./liveks` on macOS and Linux and `./liveks.ps1` in Windows PowerShell.

## First Use

Offline replay has no package installation step:

```bash
./liveks try
./liveks try --sample mcp --details
```

Install the pinned CLI dependency into the ignored `.liveks/venv` before using the remaining commands:

```bash
./liveks bootstrap
./liveks profiles
```

PowerShell equivalents replace `./liveks` with `./liveks.ps1`.

## Lifecycle

| Command | Cloud mutation | Purpose |
| --- | --- | --- |
| `try` | None | Print a checked-in answer and evidence trace. |
| `init` | None | Write an ignored YAML environment ledger. |
| `doctor` | None | Check tools, versions, sign-in, providers, and required fields. |
| `plan` | None | Run doctor, build Bicep, dry-run payloads, build the app, and write a redacted lock. |
| `up` | Yes, after confirmation | Sync the selected `azd` environment, preview ARM changes, provision, deploy, and verify. |
| `verify` | Read/call only | Check the resource group, app API, and source evidence. |
| `mcp` | Read/call only | Discover and call `knowledge_base_retrieve` on the deployed Knowledge Base MCP endpoint. |
| `down` | Yes, after confirmation | Delete only assets owned by the environment. |
| `e2e` | Yes | Run `up` and either clean up or explicitly retain resources. |

`doctor` can issue read-only Azure CLI calls for live profiles. In `byo-fabric`, it also acquires a transient Fabric API token and confirms that the configured workspace and ontology are readable. The token is not serialized. `plan` writes local build and lock artifacts under ignored directories, but it does not run `azd env set`, `azd up`, or Fabric provisioning.

## Standard Run

```bash
./liveks init --profile mcp-only --env liveks-mcp
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
./liveks verify --env liveks-mcp
./liveks mcp --env liveks-mcp
./liveks down --env liveks-mcp
```

Live commands require an environment name or a YAML path. When `--config` is omitted, LiveKS looks for `.liveks/<environment>.yaml`.

Use JSON output when cleanup evidence will be reviewed:

```bash
./liveks down --env liveks-full --yes --format json
```

Every live profile must report `resource-group-absent=pass`. A `full` run that created capacity must additionally report `fabric-capacity-absent=pass`. It must also report `fabric-capacity-resource-group-absent=pass` when the same run created that dedicated group, or `fabric-capacity-resource-group-preserved=pass` when the group predated the run. A missing summary or unresolved ownership produces partial cleanup instead of a deletion claim.

For `byo-fabric` and `full`, `mcp` attaches delegated source authorization by default. It records text-block and expected-term counts but never persists the endpoint, query, response content, key, or token. A call without `--expect-term` can pass protocol checks but reports `grounding-content=warn`; use a known non-sensitive fact for source-content acceptance. See [Call the Knowledge Base Through MCP](22-knowledge-base-mcp.md).

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

Use `--keep-resources` only while debugging. Release evidence should include successful cleanup.

Every E2E run writes ignored `deployments/<environment>/e2e-report.json` and `test-report.md` artifacts. The JSON preserves the nested lifecycle result; the Markdown format remains compatible with the maintainer evidence summarizer.

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

| Tool | Minimum | Validated v2 baseline |
| --- | --- | --- |
| Python | 3.11 | 3.11 and 3.14 |
| Azure Developer CLI | 1.27.0 | 1.27.0 |
| Azure CLI | Required | 2.86.0 |
| Node.js | 22 | 22 |
| npm | Bundled with Node.js | Node 22 distribution |

The Windows launcher and configuration contracts run in GitHub Actions on `windows-latest`. The complete local gate and Bicep build run on Ubuntu; live E2E evidence is tenant-specific and stays outside git.

## Generated Artifacts

| Path | Contents |
| --- | --- |
| `.liveks/<env>.yaml` | Authored environment ledger. |
| `.liveks/<env>.lock.json` | Redacted resolved values, sources, ownership, and last lifecycle state. |
| `.deployment/<env>/` | Local Bicep and plan output. |
| `deployments/<env>/` | Deployment and verification reports. |

All of these paths are ignored. Do not move raw evidence into tracked documentation.
