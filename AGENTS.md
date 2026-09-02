# Agent Runbook

This public accelerator demonstrates Foundry IQ composition across Azure AI Search MCP Server and Fabric Ontology Knowledge Sources. Use this file as the operational contract when an agent is asked to inspect, run, deploy, verify, clean up, or modify the repository.

## Safe Default

Follow this progression unless the user explicitly requests another profile:

```text
offline -> search-index -> mcp-search-index -> mcp-only -> byo-fabric
```

`full` is a greenfield demo profile. It creates a billable Fabric F2 capacity and generated Fabric assets, so it requires explicit user intent and `--accept-fabric-capacity`.

## First Commands

From a fresh clone:

<!-- compatibility-command-contract:start -->
```bash
./liveks try
./liveks bootstrap
./liveks profiles
./liveks doctor --profile offline --format json
bash scripts/validate-local.sh
```
<!-- compatibility-command-contract:end -->

On Windows PowerShell, replace `./liveks` with `./liveks.ps1` and run `.\scripts\validate-local.ps1` for the final gate.

Do not create cloud resources merely because credentials are available. `try`, `doctor`, and `plan` are the inspection path. `up`, `down`, and `e2e` mutate cloud state.

## Configuration Authority

- `config/schema.yaml` defines supported fields, validation, azd projection, secrets, and legacy mappings.
- `config/compatibility.yaml` defines supported runtime and tool requirements, CI-exercised combinations, API pins, and the documentation command contract.
- `profiles/offline.yaml`, `search-index.yaml`, `mcp-search-index.yaml`, `mcp-only.yaml`, `byo-fabric.yaml`, and `full.yaml` define executable defaults, resources, cost, and success criteria.
- `.liveks/<environment>.yaml` is the ignored human-authored ledger.
- `.liveks/<environment>.lock.json` is the ignored redacted resolution and ownership record.
- `azd env` is generated deployment state, not the v2 authoring source.
- `.env.sample` and `env/*.env.example` are generated compatibility catalogs for REST/notebook users.

Unknown YAML fields fail closed. Secret fields must use `{env: VARIABLE_NAME}` and must never contain raw values.

## Live Lifecycle

Stable existing-index lane:

```bash
./liveks init --profile search-index --env liveks-index
# Fill the existing endpoint, index, semantic configuration, and optional field lists.
./liveks doctor --env liveks-index
./liveks plan --env liveks-index
./liveks up --env liveks-index --query "<question>" --expect-term "<known term>"
./liveks verify --env liveks-index --query "<question>" --expect-term "<known term>"
./liveks down --env liveks-index
```

Preview deployment lane:

```bash
./liveks init --profile mcp-only --env liveks-mcp
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
./liveks verify --env liveks-mcp
./liveks mcp --env liveks-mcp
./liveks down --env liveks-mcp
```

Existing-index plus MCP composition lane:

```bash
./liveks init --profile mcp-search-index --env liveks-combined
# Fill the existing Search index and Azure OpenAI deployment values.
./liveks doctor --env liveks-combined
./liveks plan --env liveks-combined
./liveks up --env liveks-combined --query "<index question>" --expect-term "<known term>"
./liveks verify --env liveks-combined --query "<index question>" --expect-term "<known term>"
./liveks down --env liveks-combined
```

Rules:

- Never bypass a failed doctor or plan.
- Review the resource and cost list before `up`.
- Do not use `--yes` unless the user requested controlled automation.
- Require the separate full-capacity acknowledgement even with `--yes`.
- Use exactly one of `--cleanup` or `--keep-resources` for E2E.
- Prefer `--cleanup`; if resources are retained, identify the cleanup owner.
- Protected lifecycle canaries are manual `workflow_dispatch` runs on `main`, require the `mcp-search-index-live` GitHub Environment, and always use `--cleanup`.
- Never run the protected canary from a fork, pull request, untrusted ref, or ordinary repository validation.

## Ownership Rules

- `search-index`: Search service and index are reused and must be preserved; only a matching lock can authorize deletion of the generated KS and KB.
- `mcp-search-index`: Search service, index, and Azure OpenAI deployment are reused; only a matching lock can authorize deletion of the generated combined KB and its two KS objects.
- `mcp-only`: generated Azure assets may be deleted; no Fabric assets are owned.
- `byo-fabric`: generated Azure assets may be deleted; Fabric capacity, workspace, and ontology must be preserved.
- `full`: generated Azure and Fabric assets may be deleted.
- Fabric deletion is allowed only when resolved configuration and the environment lock both identify the asset as generated.
- If ownership is uncertain or records disagree, preserve the Fabric asset and report manual follow-up.

Never delete a resource group until its contents and ownership are verified. Continue Azure cleanup when generated Fabric cleanup is partial, then report the residual explicitly.

## Evidence Standard

Use the evidence that matches the claim:

| Claim | Required evidence |
| --- | --- |
| Repository is internally consistent | `bash scripts/validate-local.sh` |
| Offline response shape | `./liveks try --details` |
| Stable Search Index path is live | `liveks verify` reports `search-index-retrieve=pass`; use `--expect-term` for content acceptance |
| Existing Search index survived cleanup | `liveks down` reports `search-index-preserved=pass` |
| MCP + Search Index path is live | Independent `search-index-retrieve` and `mcp-retrieve` checks pass before `combined-retrieve`; the combined check reports only activity, references, or sourceData evidence |
| Protected lifecycle canary is live | An approved manual run completes guarded E2E cleanup and uploads only `canary-evidence.json`; repository tests prove contract shape, not live execution |
| Deployment is ready | Passing `liveks doctor` and `liveks plan` |
| MCP path is live | MCP activity or references from `liveks verify` |
| Fabric path is live | `fabricOntology` evidence in live mode with delegated authorization |
| Combined routing worked | Recognized live evidence from the source or sources selected by the combined KB planner |
| Knowledge Base MCP is callable | `liveks mcp` passes `tools/list` and `tools/call` |
| Knowledge Base MCP returned expected grounding | `liveks mcp --expect-term <known-fact>` passes `grounding-content`; pair it with source-specific `verify` evidence before naming the source that ran |
| Fabric-only rehearsal is complete | `scripts/fabric-e2e-test.sh --cleanup` ends with `fabric_release=PASS`; generated workspace and, for create mode, ARM capacity are absent, while the capacity group is deleted or preserved according to its ownership record |
| Full rehearsal is complete | Create and retrieve checks pass; deployment RG and generated capacity absence checks pass, with capacity-group deletion or preservation matching its ownership record |

Final answer text alone is not routing evidence. Inspect `activity`, `references`, and `sourceData`, and use the single-source KB checks to prove MCP and Fabric independently.

## Public Boundary

Do not publish or commit:

- customer data or real tenant, subscription, workspace, or ontology IDs,
- keys, bearer tokens, connection strings, or raw delegated tokens,
- raw live retrieve responses or unsanitized screenshots,
- protected canary detailed reports or step inputs; upload only the allowlist-sanitized capsule,
- `.liveks/`, `.azure/`, `.deployment/`, `deployments/`, local dotenv files, or generated builds,
- internal/private-preview Fabric setup, tenant allowlisting, or unpublished endpoints,
- Fabric MCP through MCP Server KS as the recommended Fabric path.

The supported Fabric pattern is native Fabric Ontology Knowledge Source. The checked-in Airline Ops data is synthetic and the ontology contract is supporting sample documentation, not the accelerator's main feature.

## Source Of Truth

The Search Index KS contract is generally available and pinned to `2026-04-01`. MCP Server KS, combined KB, and Fabric Ontology contracts are public preview and pinned to `2026-05-01-preview`. The `mcp-search-index` profile carries both versions explicitly and never substitutes one for the other. Keep the official Microsoft Learn articles for Search Index KS, MCP Server KS, Fabric Ontology KS, Knowledge Base creation, and retrieve behavior as the API source of truth.

When live behavior differs from replay, state that replay demonstrates response shape only. Summarize live evidence using sanitized status, source names, counts, and cleanup outcome.
