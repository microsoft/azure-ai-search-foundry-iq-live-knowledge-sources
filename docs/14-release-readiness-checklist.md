# Release Readiness Checklist

Use this checklist before moving the sample from a staging branch into a broader review, workshop, blog, or official sample repository.

This checklist does not replace product review, security review, or the official Azure AI Search and Fabric documentation. It keeps the repo evidence organized so reviewers can quickly see what was validated and what remains preview-dependent.

## Required Local Checks

```bash
bash scripts/validate-local.sh
git diff --check
```

Required result:

```text
Local validation: PASS
```

The validation gate covers shell syntax, Python compile, notebook JSON parsing, Markdown local link checks, sample payload generation, offline response inspection, no-secret scan, Static Web Apps build, optional Next.js demo app build, and Bicep build when Azure CLI is available.

The GitHub Actions `Validate` workflow runs the same local validation gate on pull requests and pushes to `main`.

## Documentation Gate

```text
[ ] README explains the three modes: mcp-only, byo-fabric, full
[ ] README links official Learn manuals
[ ] README links reviewer evidence and preview limitations
[ ] docs/02-choose-a-pattern.md matches the current deployment modes
[ ] docs/10-one-command-deployment.md matches script behavior
[ ] docs/12-reviewer-evidence.md matches E2E report behavior
[ ] docs/13-public-preview-limitations.md captures current caveats
[ ] docs/17-storyline-and-safe-claims.md matches the README and demo walkthrough
[ ] docs/18-private-review-workflow.md matches the promotion and reviewer evidence flow
[ ] Markdown links resolve locally
[ ] troubleshooting includes auth, quota, GraphModel readiness, and hosting fallback notes
```

## Code And Sample Gate

```text
[ ] GitHub Actions Validate workflow passes
[ ] Dependabot configuration is present for GitHub Actions and tracked npm apps
[ ] Static Web Apps demo and optional Next.js demo app both build
[ ] REST samples keep the preview API version explicit
[ ] notebooks run in dry-run/offline mode without live tenant values
[ ] offline response samples are synthetic and safe to commit
[ ] Fictional Airline Ops data is used for semantic examples
[ ] MCP examples use remote HTTPS MCP servers
[ ] Fabric examples use Fabric Ontology KS, not Fabric MCP through generic MCP Server KS
[ ] Generated deployment reports, logs, local screenshots, and scratch notes are ignored
```

## Deployment Evidence Gate

For each deployment mode you plan to demonstrate, keep an ignored local report:

```text
deployments/<env>/test-report.md
```

Expected evidence:

| Mode | Evidence expected |
| --- | --- |
| `mcp-only` | MCP KS, MCP-only KB, retrieve activity or references, app load, cleanup. |
| `byo-fabric` | MCP KS, Fabric KS, combined KB, Fabric live retrieve when delegated token exists or clear offline fallback when absent, app load, cleanup. |
| `full` | Fabric capacity/workspace/lakehouse/ontology/GraphModel preparation, Azure deploy, KS/KB creation, app load, cleanup. |

Do not commit the report itself. Summarize only sanitized evidence in PRs or review notes.

## Security And Privacy Gate

```text
[ ] No API keys
[ ] No bearer tokens
[ ] No tenant-specific IDs
[ ] No customer data
[ ] No private endpoint details
[ ] No service URLs from private deployments
[ ] No generated deployment reports
[ ] No local screenshots with sensitive resource names
[ ] No internal planning notes
```

Use `.env.sample` only for placeholders. Keep `.env`, `.env.*`, `.deployment/`, `deployments/`, and `scratch/` ignored.

## Preview Claims Gate

Before writing a README update, blog, or presentation:

```text
[ ] Claims are aligned to the official Learn manuals
[ ] Preview API version is stated as 2026-05-01-preview where relevant
[ ] Full mode is described as quota/auth dependent
[ ] Offline replay is not described as live retrieve
[ ] Fabric live claims are backed by Fabric activity
[ ] MCP claims mention remote HTTPS MCP servers
[ ] "Production-ready" wording is avoided
```

Use [Public Preview Limitations and Caveats](13-public-preview-limitations.md) as the source for safe wording.
Use [Storyline And Safe Claims](17-storyline-and-safe-claims.md) for blog, presentation, and reviewer-summary phrasing.

## Reviewer Packet

A useful reviewer packet should include:

- commit or branch name,
- deployment mode tested,
- local validation result,
- sanitized E2E summary,
- screenshots only if they do not expose sensitive values,
- known caveats or skipped checks,
- links to `docs/12-reviewer-evidence.md` and `docs/13-public-preview-limitations.md`.

## Final Go / No-Go

```text
[ ] Local validation passes
[ ] Repository promotion guide has been reviewed
[ ] Private review workflow has been reviewed if requesting product or target-org feedback
[ ] The intended deployment mode has current evidence
[ ] The README first five minutes flow is accurate
[ ] The sample can be explained without internal context
[ ] Preview limitations are visible
[ ] No generated or sensitive files are staged
[ ] PR template checklist is complete
```

If any item is uncertain, treat the sample as review-only and avoid public or customer-facing claims until the evidence is updated.
