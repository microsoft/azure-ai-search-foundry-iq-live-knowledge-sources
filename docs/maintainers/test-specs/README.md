# Full-Run Test Specifications

Use these specifications when you need evidence for create-call-load-delete behavior before a private review, workshop, blog draft, or target-org promotion.

The specs describe expected resources, Knowledge Source assets, app checks, retrieve checks, pass criteria, failure conditions, and cleanup behavior. They do not replace the live reports generated under ignored `deployments/<env>/` paths.

## Which Spec To Use

| Spec | Use when | Command family |
| --- | --- | --- |
| [MCP-only](e2e-mcp-only.md) | You need the fastest live validation path without Fabric. | `scripts/e2e-test.sh --mode mcp-only` |
| [BYO Fabric](e2e-byo-fabric.md) | You already have Fabric workspace and ontology IDs and want to connect Azure AI Search. | `scripts/e2e-test.sh --mode byo-fabric` |
| [Fabric greenfield](e2e-fabric-greenfield.md) | You want to validate only Fabric capacity, workspace, Lakehouse, ontology, GraphModel readiness, and cleanup before connecting Search. | `scripts/fabric-e2e-test.sh` |
| [Full greenfield](e2e-full-greenfield.md) | You want the complete platform story: Fabric sample assets plus Azure AI Search, Knowledge Sources, Knowledge Bases, app, retrieve, and cleanup. | `scripts/e2e-test.sh --mode full` |

## Shared Reporting Rules

Every live full-run should write ignored evidence:

```text
deployments/<env>/test-report.md
deployments/<env>/deployment-summary.md
```

Fabric-only runs may also write:

```text
deployments/<env>/fabric-test-report.md
deployments/<env>/fabric-summary.json
deployments/<env>/fabric-summary.md
deployments/<env>/fabric.env
```

Do not commit these reports. Generate sanitized summaries before sharing evidence:

```bash
python3 scripts/maintainers/summarize-e2e-evidence.py \
  deployments/<mcp-env>/test-report.md \
  deployments/<byo-fabric-env>/test-report.md \
  deployments/<full-env>/test-report.md
```

The sanitized summary is written under ignored `scratch/review-packets/` and includes only safe status fields, checklist names, and PASS / FAIL / SKIP counts.

## Review Sequence

Use this order for release rehearsal:

1. Run `mcp-only` to prove the low-friction MCP Server KS path.
2. Run `byo-fabric` when Fabric workspace and ontology IDs are ready.
3. Run `fabric-greenfield` when you need to isolate Fabric provisioning or capacity issues.
4. Run `full` when you need the complete greenfield platform evidence.
5. Generate a sanitized E2E summary.
6. Generate a local review packet and promotion note.
7. Run promotion readiness with review artifact paths.

```bash
bash scripts/maintainers/check-promotion-readiness.sh \
  --target-remote microsoft \
  --run-validation \
  --review-packet scratch/review-packets/<packet>.local.md \
  --promotion-note scratch/review-packets/<promotion-note>.local.md
```

## Boundaries

- Offline replay helps reviewers understand trace shape, but it does not prove live retrieve.
- Screenshots help explain the experience, but they do not prove source selection.
- `full` mode depends on Fabric quota, tenant settings, region availability, GraphModel readiness, and delegated source authorization.
- Raw deployment reports can contain service URLs and tenant-specific values, so keep them local and ignored.
