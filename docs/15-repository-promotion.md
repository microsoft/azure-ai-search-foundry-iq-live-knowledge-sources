# Repository Promotion Guide

Use this guide when moving the sample from a personal or team staging repository into a target organization repository for broader private review or official sample preparation.

The goal is not to copy every local artifact. The goal is to promote only reusable, public-safe source files plus clear validation evidence.

## Promotion Principles

- Promote from a clean branch.
- Keep generated deployment outputs ignored.
- Keep local env files ignored.
- Keep scratch notes ignored.
- Push only after local validation and CI validation are green.
- Treat the target organization repository as review-ready source, not a workbench.
- Keep public-preview claims aligned to the Learn manuals and `docs/13-public-preview-limitations.md`.

## What Moves

These files are expected to move:

- `README.md`
- `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`
- `.github/` templates and validation workflow
- `docs/`
- `infra/`
- `scripts/`
- `static-app/`
- `samples/`
- `notebooks/`
- `src/`
- `assets/`
- `evals/`
- `.env.sample`
- `azure.yaml`

These files must not move:

- `.env`
- `.env.*`
- `.deployment/`
- `deployments/`
- `scratch/`
- local screenshots with tenant/resource identifiers
- generated logs
- generated E2E reports
- raw live retrieve responses from private tenants
- internal planning notes

## Pre-Promotion Checks

Run these from the staging repository:

```bash
git status -sb
bash scripts/validate-local.sh
git diff --check
```

Or run the non-pushing promotion preflight:

```bash
bash scripts/check-promotion-readiness.sh \
  --target-remote microsoft \
  --run-validation \
  --review-packet scratch/review-packets/review-packet-<timestamp>.local.md \
  --promotion-note scratch/review-packets/promotion-note-<timestamp>.local.md
```

The preflight checks the current branch, clean tracked worktree state, untracked non-ignored files, ignored generated-output paths, optional local review artifacts, local validation, no-secret scan, whitespace, target remote configuration, and the latest GitHub Actions `Validate` result for the current commit. When review artifact paths are provided, it confirms that they are ignored by git and reference the current source commit. It prints manual push commands but never pushes.

To prepare a local human-readable handoff note before the target-org push, generate an ignored promotion note:

```bash
bash scripts/create-promotion-note.sh \
  --target-remote microsoft \
  --review-packet scratch/review-packets/review-packet-<timestamp>.local.md \
  --e2e-summary scratch/review-packets/e2e-evidence-summary-<timestamp>.local.md
```

The note records the source commit, target remote, safe local evidence paths, required preflight command, manual review-branch push command, and reviewer message draft. It never pushes and never copies raw deployment report contents.

Optional but recommended:

```bash
bash scripts/no-secret-scan.sh
python3 scripts/check-doc-links.py
```

Confirm:

```text
[ ] worktree is clean
[ ] local validation passes
[ ] GitHub Actions Validate workflow passes on the staging repo
[ ] review packet and promotion note reference the current commit
[ ] no generated reports are staged
[ ] no local env files are staged
[ ] no scratch notes are staged
[ ] release readiness checklist is reviewed
```

## Remote Setup

Use explicit remote names so the staging and target organization repositories cannot be confused.

Example:

```bash
git remote -v
git remote add target https://github.com/<org>/<repo>.git
git fetch target
```

Before pushing, verify:

```bash
git remote get-url origin
git remote get-url target
git branch --show-current
git rev-parse --short HEAD
```

Do not push to a Microsoft or official organization remote until the source branch is clean and the intended target is confirmed.

## Promotion Branch

Prefer a review branch in the target repository first:

```bash
git switch main
git pull --ff-only origin main
git switch -c review/live-knowledge-sources
git push -u target review/live-knowledge-sources
```

If the target repository is intentionally seeded from the staging repo, confirm with the maintainers whether direct `main` push is expected. For official sample preparation, a review branch plus PR is usually easier to audit.

## Target PR Checklist

The PR should include:

- what changed,
- which deployment modes are included,
- local validation result,
- GitHub Actions result,
- sanitized E2E evidence summary if deployment behavior is being claimed,
- known preview caveats,
- reviewer asks.

Use the template in [Reviewer Evidence Guide](12-reviewer-evidence.md#reviewer-packet-template) for the PR body, Teams note, or reviewer email.
Use [Private Review Workflow](18-private-review-workflow.md) for the end-to-end sequence from clean source branch to sanitized review request.

Do not paste generated reports, tokens, tenant IDs, service URLs, or private screenshots into the PR.

## Suggested Reviewer Ask

```text
Please review this sample accelerator for:

- Azure AI Search Knowledge Source terminology
- MCP Server KS request/response shape
- Fabric Ontology KS setup and delegated source authorization wording
- deployment-mode clarity: mcp-only, byo-fabric, full
- public-preview caveats and safe claims
- security posture for generated outputs and tokens
```

## After Promotion

Once the target organization PR or branch exists:

```text
[ ] Confirm GitHub Actions Validate passes in the target repository
[ ] Confirm links render correctly in the target repository
[ ] Confirm issue and PR templates render correctly
[ ] Confirm generated-output paths are still ignored
[ ] Confirm reviewer evidence and preview limitation docs are visible
[ ] Confirm the README first five minutes flow still makes sense in the target repository
```

If the target repository uses a different default branch or stricter branch protection, update the workflow trigger and PR guidance before requesting review.

## Public Release Boundary

Promotion to a target organization repository does not imply public release.

Before public release:

- complete product and security review as required by the owning team,
- validate preview API wording with product owners,
- verify all sample data is synthetic or approved for release,
- confirm license and contribution guidance,
- confirm support expectations,
- remove or archive stale workbench branches.

Use [Release Readiness Checklist](14-release-readiness-checklist.md) as the final source-level gate.
