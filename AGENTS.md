# Agent Runbook

This public accelerator demonstrates Foundry IQ composition across Azure AI Search MCP Server and Fabric Ontology Knowledge Sources. Use this file as the operational contract when an agent is asked to inspect, run, deploy, verify, clean up, or modify the repository.

## Safe Default

Follow this progression unless the user explicitly requests another profile:

```text
offline -> mcp-only -> byo-fabric
```

`full` is a greenfield demo profile. It creates a billable Fabric F2 capacity and generated Fabric assets, so it requires explicit user intent and `--accept-fabric-capacity`.

## First Commands

From a fresh clone:

```bash
./liveks try
./liveks bootstrap
./liveks profiles
./liveks doctor --profile offline --format json
bash scripts/validate-local.sh
```

On Windows PowerShell, replace `./liveks` with `./liveks.ps1`.

Do not create cloud resources merely because credentials are available. `try`, `doctor`, and `plan` are the inspection path. `up`, `down`, and `e2e` mutate cloud state.

## Configuration Authority

- `config/schema.yaml` defines supported fields, validation, azd projection, secrets, and legacy mappings.
- `profiles/offline.yaml`, `mcp-only.yaml`, `byo-fabric.yaml`, and `full.yaml` define executable defaults, resources, cost, and success criteria.
- `.liveks/<environment>.yaml` is the ignored human-authored ledger.
- `.liveks/<environment>.lock.json` is the ignored redacted resolution and ownership record.
- `azd env` is generated deployment state, not the v2 authoring source.
- `.env.sample` and `env/*.env.example` are generated compatibility catalogs for REST/notebook users.

Unknown YAML fields fail closed. Secret fields must use `{env: VARIABLE_NAME}` and must never contain raw values.

## Live Lifecycle

```bash
./liveks init --profile mcp-only --env liveks-mcp
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
./liveks verify --env liveks-mcp
./liveks mcp --env liveks-mcp
./liveks down --env liveks-mcp
```

Rules:

- Never bypass a failed doctor or plan.
- Review the resource and cost list before `up`.
- Do not use `--yes` unless the user requested controlled automation.
- Require the separate full-capacity acknowledgement even with `--yes`.
- Use exactly one of `--cleanup` or `--keep-resources` for E2E.
- Prefer `--cleanup`; if resources are retained, identify the cleanup owner.

## Ownership Rules

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
| Deployment is ready | Passing `liveks doctor` and `liveks plan` |
| MCP path is live | MCP activity or references from `liveks verify` |
| Fabric path is live | `fabricOntology` evidence in live mode with delegated authorization |
| Combined routing worked | Recognized live evidence from the source or sources selected by the combined KB planner |
| Knowledge Base MCP is callable | `liveks mcp` passes `tools/list` and `tools/call` |
| Knowledge Base MCP returned expected grounding | `liveks mcp --expect-term <known-fact>` passes `grounding-content`; pair it with source-specific `verify` evidence before naming the source that ran |
| Fabric-only rehearsal is complete | `scripts/fabric-e2e-test.sh --cleanup` ends with `fabric_release=PASS`; generated workspace and, for create mode, capacity resource group and ARM capacity are absent |
| Full rehearsal is complete | Create and retrieve checks pass; deployment RG, generated capacity RG, and generated capacity absence checks pass |

Final answer text alone is not routing evidence. Inspect `activity`, `references`, and `sourceData`, and use the single-source KB checks to prove MCP and Fabric independently.

## Public Boundary

Do not publish or commit:

- customer data or real tenant, subscription, workspace, or ontology IDs,
- keys, bearer tokens, connection strings, or raw delegated tokens,
- raw live retrieve responses or unsanitized screenshots,
- `.liveks/`, `.azure/`, `.deployment/`, `deployments/`, local dotenv files, or generated builds,
- internal/private-preview Fabric setup, tenant allowlisting, or unpublished endpoints,
- Fabric MCP through MCP Server KS as the recommended Fabric path.

The supported Fabric pattern is native Fabric Ontology Knowledge Source. The checked-in Airline Ops data is synthetic and the ontology contract is supporting sample documentation, not the accelerator's main feature.

## Source Of Truth

Azure AI Search Knowledge Source APIs are public preview and pinned here to `2026-05-01-preview`. Keep the official Microsoft Learn articles for MCP Server KS, Fabric Ontology KS, Knowledge Base creation, and retrieve behavior as the API source of truth.

When live behavior differs from replay, state that replay demonstrates response shape only. Summarize live evidence using sanitized status, source names, counts, and cleanup outcome.
