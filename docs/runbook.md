# Execution Runbook

This is the shortest supported sequence from a fresh clone to verified cleanup.

## 1. Replay The Contract

```bash
./liveks try
```

Expected: an answer naming Alpine Air, followed by both `MCP Server KS` and `Fabric Ontology KS` evidence. No package install or cloud access is used.

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

Run verification again without redeploying:

```bash
./liveks verify --env liveks-mcp
```

Sanitized reports are written under ignored `deployments/<environment>/`.

## 8. Clean Up

```bash
./liveks down --env liveks-mcp
```

Type `delete liveks-mcp`. The command verifies the generated resource group is absent afterward.

- `mcp-only` deletes generated Azure resources.
- `byo-fabric` deletes generated Azure resources and preserves the existing Fabric workspace and ontology.
- `full` deletes generated Fabric assets first, continues with Azure cleanup if Fabric reports a partial failure, and returns a nonzero partial-cleanup status.

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

Keep `.liveks/`, `.deployment/`, `deployments/`, raw responses, tokens, and private screenshots out of git. Public summaries should include only profile, status, sanitized resource/source names, evidence counts, and cleanup result.
