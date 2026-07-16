# MCP-Only Full-Run Test Specification

This test validates the fastest deployment path for users who want to try Azure AI Search MCP Server Knowledge Source without preparing Fabric assets.

## Purpose

Prove that the repo can deploy a working MCP Server Knowledge Source, Knowledge Base, Search index, and demo app without requiring Fabric workspace or ontology inputs.

This path is the fallback and first-run validation path for tenants that are not ready for Fabric.

## Inputs

Create the ignored YAML ledger:

```bash
./liveks init --profile mcp-only --env ext-liveks-mcp-e2e
```

Add `azure.tenant_id`, `azure.subscription_id`, and `azure.cli_config_dir` to `.liveks/ext-liveks-mcp-e2e.yaml` for an external tenant. Fabric fields are neither required nor imported in this mode.

## Command

```bash
./liveks e2e \
  --env ext-liveks-mcp-e2e \
  --cleanup \
  --yes \
  --format json
```

## Expected Azure Resources

- Resource group: `rg-ext-liveks-mcp-e2e`
- Azure AI Search
- Azure OpenAI account and `gpt-5-mini` deployment
- Storage account
- Static Web App and managed Functions API

## Expected Knowledge Assets

- `microsoft-learn-mcp-ks`
- `live-knowledge-sources-mcp-kb`
- `live-knowledge-sources-kb`
- `airline-ops-regulatory-docs` Search index

No Fabric Knowledge Source is required.

## Required Checks

| Check | Expected |
| --- | --- |
| Python, Azure CLI, azd, Node.js, and npm preflight | PASS |
| Azure and azd login | PASS |
| Configured tenant match | PASS |
| Bicep build | PASS |
| Payload dry-run | PASS |
| Static app build | PASS |
| ARM preview | PASS without provisioning |
| `azd up` | PASS |
| Resource group exists | PASS |
| MCP retrieve | PASS with MCP activity or references |
| App status | HTTP 200 |
| Azure cleanup | PASS |
| Resource group absence | PASS |

## Pass Criteria

The run passes when MCP live retrieval works and Fabric behavior is explicitly skipped or offline, not silently attempted.

Required MCP evidence:

- retrieve response contains MCP activity, or
- retrieve response contains references from the MCP-backed Knowledge Base.

## Failure Conditions

Fail the run if:

- Fabric KS creation is required or blocks deployment.
- MCP retrieve has no activity or references.
- `/api/retrieve/fabric` tries live Fabric retrieval instead of returning offline replay in `mcp-only`.
- Cleanup fails or the resource group remains.

## Reporting Requirements

The run writes:

```text
deployments/ext-liveks-mcp-e2e/e2e-report.json
deployments/ext-liveks-mcp-e2e/test-report.md
```

The JSON report preserves the nested lifecycle result. The Markdown report preserves the legacy maintainer summary format and pass/fail/skip checklist.

The report must not include API keys, raw access tokens, customer data, internal tenant secrets, passwords, or connection strings.

## Static Validation Before Live Run

```bash
bash scripts/validate-local.sh --strict
git diff --check
```
