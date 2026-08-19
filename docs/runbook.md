# Execution Runbook

This is the shortest supported sequence from a fresh clone to verified cleanup.

To skip workstation tool installation, open [Codespaces First Live](15-codespaces-first-live.md). Its container runs only replay, bootstrap, profile listing, and offline doctor; the guarded lifecycle below remains manual.

## 0. Know What To Configure

The canonical input is an ignored `.liveks/<environment>.yaml` ledger. It is not a dotenv file and it is not `azd env`; LiveKS generates the deployment projection after validation.

| Profile | Required authored values | Runtime credential | What it creates |
| --- | --- | --- | --- |
| `mcp-only` | None beyond the generated profile and environment. | Azure CLI and Azure Developer CLI sign-in. | Azure resources, MCP Server KS, MCP-only KB, and app. |
| `byo-fabric` | `fabric.workspace_id` and `fabric.ontology_id`. | Azure sign-in plus a transient delegated Search token during Fabric calls. | Generated Azure resources and a Fabric-only validation KB; the existing Fabric assets are preserved. |
| `full` | No existing Fabric IDs; optional Fabric location and SKU overrides. | Azure and Fabric access, available quota, and `--accept-fabric-capacity`. | Generated Azure resources and a billable Fabric F2 sample stack. |

Optional external-tenant values belong under `azure`: `tenant_id`, `subscription_id`, and `cli_config_dir`. Secret fields contain an environment-variable reference, never the raw secret:

```yaml
fabric:
  user_search_token:
    env: FABRIC_USER_SEARCH_TOKEN
```

Normally, do not author that optional token field at all. `verify` and `mcp` acquire the user token transiently from Azure CLI. See [Configuration](21-configuration.md) for the complete field and precedence contract.

## 1. Replay The Contract

```bash
./liveks try --evidence-out .deployment/first-run-evidence.json
```

Expected: an answer naming Alpine Air, both `MCP Server KS` and `Fabric Ontology KS` evidence, and `Contract: PASS (4/4 assertions)`. No package install or cloud access is used.

The ignored `.deployment/first-run-evidence.json` capsule contains only the source revision, runtime, fixture digest, source identities and counts, and assertion statuses. It excludes the answer, query, raw response, and credentials. Pull requests run the same command and retain this capsule as the `first-success-evidence` workflow artifact.

Open the same response visually in the [interactive trace demo](https://microsoft.github.io/azure-ai-search-foundry-iq-live-knowledge-sources/demo/?demo=combined).

## 2. Bootstrap And Validate

```bash
./liveks bootstrap
./liveks profiles
./liveks doctor --profile offline
bash scripts/validate-local.sh
```

Expected: profile metadata prints, offline doctor passes, and the repository gate completes without failures.

## 3. Create The YAML Ledger

Choose the smallest live profile that matches the tenant:

```bash
./liveks init --profile mcp-only --env liveks-mcp
```

Other choices:

```bash
./liveks init --profile byo-fabric --env liveks-byo
./liveks init --profile full --env liveks-full
```

Review `.liveks/<environment>.yaml`. For `byo-fabric`, replace the blank Fabric workspace and ontology IDs. For external tenants, add `azure.tenant_id`, `azure.subscription_id`, and `azure.cli_config_dir`. See [Configuration](21-configuration.md).

## 4. Sign In

```bash
az login --tenant <tenant-guid>
azd auth login
```

Use the same target tenant and subscription for both tools. `doctor` fails on a configured tenant or subscription mismatch.

## 5. Doctor

```bash
./liveks doctor --env liveks-mcp
```

Resolve all failures. Warnings about Search preview availability or unknown Fabric quota require human review but do not claim that a deployment will fail.

Minimum versions are Python 3.11, Azure Developer CLI 1.27.0, and Node.js 22. Azure CLI is also required.

## 6. Plan Without Provisioning

```bash
./liveks plan --env liveks-mcp
```

The plan:

1. reruns doctor,
2. compiles Bicep,
3. dry-runs Knowledge Source and Knowledge Base payload generation,
4. installs and builds the demo app,
5. writes a redacted ownership lock.

It does not set `azd` values, create Fabric assets, or run `azd up`.

## 7. Deploy And Verify

```bash
./liveks up --env liveks-mcp
```

Review the ARM preview and cost statement, then type `create liveks-mcp`. LiveKS provisions, deploys, and runs verification in the same lifecycle.

For full greenfield:

```bash
./liveks up --env liveks-full --accept-fabric-capacity
```

Expected evidence:

| Profile | Required evidence |
| --- | --- |
| `mcp-only` | Resource group and app exist; MCP retrieve includes MCP activity or references. |
| `byo-fabric` | MCP evidence plus live Fabric and combined evidence using delegated Search authorization. |
| `full` | Generated Fabric GraphModel is ready, separate checks prove both sources, and all Azure assets pass. |

### Run The Manual Acceptance Test

Do not stop at a successful deployment message. Open the **App URL** from:

```text
deployments/<environment>/deployment-summary.md
```

Then run this minimum screen check:

1. On **Overview**, confirm the top status pill says `<deployment-mode> live`.
2. Open **Deployment**, select **Re-check**, and confirm `reachabilityStatus: live` and `reachable: true`.
3. Open **MCP Live**, select **Run retrieve**, and require a `live` answer with **MCP Server KS** activity or references.
4. For `byo-fabric` or `full`, open **Fabric**, enter a raw delegated Search token without a `Bearer` prefix, select **Run retrieve**, and require a `live` answer with **Fabric Ontology KS** evidence.
5. After both single-source checks pass, open **Combined Trace**, select **Run retrieve**, and describe the source selection shown in activity. Do not assume every combined query calls both sources.

Use [Guided Live Demo Walkthrough](16-demo-walkthrough.md) for the exact click sequence, packaged questions, expected answers, presenter notes, and failure handling. Use [Post-Deployment Tests](08-test-queries.md) for trace-level pass/fail criteria and additional queries.

Run verification again without redeploying:

```bash
./liveks verify --env liveks-mcp
```

The manual app test proves the user-facing experience. `verify` independently repeats the applicable source checks and records sanitized evidence under the ignored `deployments/<environment>/` directory.

Sanitized reports are written under ignored `deployments/<environment>/`.

## 8. Call The Knowledge Base Through MCP

The source-specific retrieve checks above prove which Knowledge Source ran. Now call the same single-source Knowledge Base through its native MCP endpoint:

```bash
./liveks mcp --env liveks-mcp
```

For an Airline Ops `byo-fabric` or `full` environment:

```bash
./liveks mcp \
  --env liveks-byo \
  --query "Which airlines have the highest customer-care exposure this month?" \
  --expect-term "Alpine Air"
```

Expected: `tools/list` publishes `knowledge_base_retrieve`, `tools/call` returns at least one text block, and `grounding-content` matches every expected term. The command keeps raw MCP content in memory and records only sanitized counts. Without `--expect-term`, protocol checks can pass but grounding remains a warning.

Use [Call the Knowledge Base Through MCP](22-knowledge-base-mcp.md) for bearer authentication, a controlled missing-authorization failure, and the complete acceptance contract.

## 9. Clean Up

```bash
./liveks down --env liveks-mcp
```

Type `delete liveks-mcp`. The command verifies the generated deployment resource group is absent afterward. For a generated `full` capacity, it also confirms that the exact ARM capacity is absent. When the run created the dedicated capacity resource group, it waits for that group to disappear as well.

- `mcp-only` deletes generated Azure resources.
- `byo-fabric` deletes generated Azure resources and preserves the existing Fabric workspace and ontology.
- `full` deletes generated Fabric assets first, continues with Azure cleanup if Fabric reports a partial failure, and returns a nonzero partial-cleanup status.

Do not close a rehearsal until `resource-group-absent` passes. For generated `full`, also require `fabric-capacity-absent`; require `fabric-capacity-resource-group-absent` for a generated group or `fabric-capacity-resource-group-preserved` for a pre-existing group. Treat a missing summary or unresolved create-mode ownership as partial cleanup.

The YAML and redacted lock must both identify Fabric assets as generated before Fabric deletion is allowed.

## Automated Rehearsal

For CI or a controlled test tenant:

```bash
./liveks e2e --env liveks-mcp --cleanup --yes
```

For full:

```bash
./liveks e2e \
  --env liveks-full \
  --cleanup \
  --yes \
  --accept-fabric-capacity
```

Never use `--keep-resources` for a release rehearsal without recording who owns the follow-up cleanup.

## Evidence Boundary

Keep `.liveks/`, `.deployment/`, `deployments/`, raw responses, tokens, and private screenshots out of git. Every `e2e` run writes allowlist-sanitized `evidence-capsule.json` and `evidence-capsule.md` files beside the detailed local reports. Review even sanitized capsules before sharing; public summaries should include only profile, revision, status, source types, assertion names, evidence counts, report digest, and cleanup result.
