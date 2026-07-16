# BYO Fabric Full-Run Test Specification

This test validates the primary deployment path for users who already have a Microsoft Fabric workspace and ontology. The run creates the Azure AI Search, Azure OpenAI, MCP Knowledge Source, Fabric Ontology Knowledge Source, Knowledge Bases, Search index, and demo app resources, then validates live retrieval behavior.

## Purpose

Prove that an existing Fabric ontology can be connected to a newly deployed Foundry IQ/Azure AI Search environment and used from the demo app.

This is the validated public sample path.

## Inputs

Create the ignored YAML ledger:

```bash
./liveks init --profile byo-fabric --env ext-liveks-byo-e2e
```

Set the existing IDs and, for an external tenant, the Azure context in `.liveks/ext-liveks-byo-e2e.yaml`:

```yaml
fabric:
  workspace_id: <fabric-workspace-guid>
  ontology_id: <fabric-ontology-guid>
```

Doctor reads both Fabric assets with a transient Fabric API token. Verify obtains a transient delegated Search token; neither token is serialized.

## Command

```bash
./liveks e2e \
  --env ext-liveks-byo-e2e \
  --cleanup \
  --yes \
  --format json
```

## Expected Azure Resources

- Resource group: `rg-ext-liveks-byo-e2e`
- Azure AI Search
- Azure OpenAI account and `gpt-5-mini` deployment
- Storage account
- Static Web App and managed Functions API
- Search managed identity with Azure OpenAI access

## Expected Knowledge Assets

- `microsoft-learn-mcp-ks`
- `fabric-ontology-ks`
- `live-knowledge-sources-mcp-kb`
- `live-knowledge-sources-kb`
- `airline-ops-regulatory-docs` Search index with sample docs

## Required Checks

| Check | Expected |
| --- | --- |
| Tool and login preflight | PASS |
| Configured tenant match | PASS |
| Fabric workspace and ontology readability | PASS |
| Bicep build | PASS |
| Payload dry-run | PASS |
| Static app build | PASS |
| ARM preview | PASS without provisioning |
| `azd up` | PASS |
| Resource group exists | PASS |
| MCP retrieve | PASS with MCP activity or references |
| Fabric live retrieve | PASS with `fabricOntology` evidence |
| Combined retrieve | PASS with recognized planner-selected live evidence |
| App status | HTTP 200 |
| BYO Fabric cleanup | PASS without deleting Fabric assets |
| Azure cleanup and resource group absence | PASS |

## Pass Criteria

The run passes when all required checks pass and Fabric-specific behavior is clear:

- The dedicated MCP and Fabric checks prove each source independently.
- The combined check records one or both source types selected by the Knowledge Base planner.
- The existing Fabric workspace and ontology remain readable after cleanup.
- Cleanup confirms the resource group no longer exists.

## Failure Conditions

Fail the run if:

- `FABRIC_WORKSPACE_ID` or `FABRIC_ONTOLOGY_ID` is missing.
- `fabric-ontology-ks` is not created.
- `live-knowledge-sources-kb` does not include the Fabric Knowledge Source.
- Live Fabric retrieve with a token does not show `fabricOntology` activity.
- Cleanup fails or the resource group remains.

## Reporting Requirements

The run writes:

```text
deployments/ext-liveks-byo-e2e/e2e-report.json
deployments/ext-liveks-byo-e2e/test-report.md
```

The JSON report preserves the nested lifecycle result. The Markdown report preserves the legacy maintainer summary format and pass/fail/skip checklist.

The report must not include API keys, raw access tokens, customer data, internal tenant secrets, passwords, or connection strings.

## Static Validation Before Live Run

```bash
bash scripts/validate-local.sh --strict
git diff --check
```
