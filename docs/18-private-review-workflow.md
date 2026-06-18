# Private Review Workflow

Use this workflow when you are preparing the sample for a private review in a target organization repository, a product-team review, a workshop dry run, or a blog terminology review.

The goal is to share enough evidence for reviewers to be effective without copying local deployment reports, tenant-specific values, private endpoints, screenshots with resource names, or scratch notes into tracked files.

## Review Sequence

```text
Clean source branch
  -> local validation
    -> optional E2E run
      -> local review packet
        -> sanitized PR / message
          -> reviewer feedback
```

## 1. Confirm The Source Branch

Run:

```bash
git status -sb
git remote -v
git rev-parse --short HEAD
```

Confirm:

```text
[ ] You are on the intended source branch
[ ] The worktree has no tracked changes
[ ] Generated reports are not staged
[ ] The target organization remote is explicit and correct
```

Do not push to a target organization remote until the target URL and branch are confirmed.

## 2. Run Local Validation

Run:

```bash
bash scripts/validate-local.sh
git diff --check
```

Expected result:

```text
Local validation: PASS
```

This proves the source shape: shell scripts parse, Python files compile, notebooks parse, Markdown links resolve, sample payloads generate, offline responses inspect, no-secret scan passes, web apps build, and Bicep compiles when Azure CLI is available.

## 3. Add E2E Evidence When Needed

Run E2E only when the review claims deployment behavior.

```bash
bash scripts/e2e-test.sh \
  --mode mcp-only \
  --env-name ext-liveks-mcp-e2e \
  --location eastus \
  --cleanup
```

```bash
bash scripts/e2e-test.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name ext-liveks-byo-e2e \
  --location eastus \
  --cleanup
```

```bash
bash scripts/e2e-test.sh \
  --mode full \
  --env-file .env.external.local \
  --env-name ext-liveks-full-e2e \
  --location eastus \
  --fabric-location westus3 \
  --cleanup
```

The E2E report stays local and ignored:

```text
deployments/<env>/test-report.md
```

Summarize the result. Do not paste the raw report unless it has been reviewed and redacted.

For a safer reviewer artifact, generate a sanitized summary:

```bash
python3 scripts/summarize-e2e-evidence.py \
  deployments/<mcp-env>/test-report.md \
  deployments/<byo-fabric-env>/test-report.md \
  deployments/<full-env>/test-report.md
```

This writes an ignored file under `scratch/review-packets/` and copies only safe fields plus checklist status/check names. It intentionally omits raw notes, app URLs, Search endpoints, resource group names, subscription IDs, tenant IDs, keys, and tokens.

## 4. Generate A Local Review Packet

Use:

```bash
bash scripts/create-review-packet.sh \
  --mode mcp-only \
  --intent "private review" \
  --run-local-validation
```

With an E2E report:

```bash
bash scripts/create-review-packet.sh \
  --mode byo-fabric \
  --intent "private review" \
  --run-local-validation \
  --e2e-report deployments/<env>/test-report.md
```

The generated packet stays ignored:

```text
scratch/review-packets/*.local.md
```

The packet records source commit, remote names, local validation result, GitHub Actions status when available, optional local E2E report path, caveats, and reviewer asks. It does not copy raw deployment report contents.

## 5. Send A Sanitized Review Request

Use this as a starting point:

```text
Hi team,

I have a private-review candidate for the Azure AI Search Foundry IQ Live Knowledge Sources sample accelerator.

Scope:
- Two public preview Knowledge Source paths: MCP Server KS and Fabric Ontology KS
- Three deployment modes: mcp-only, byo-fabric, full
- Demo app, notebooks, REST samples, synthetic Airline Ops data, offline replay, and validation workflow

Current evidence:
- Commit: <commit>
- Local validation: PASS
- GitHub Actions Validate: PASS
- Deployment mode reviewed: <mcp-only | byo-fabric | full>
- E2E summary: <PASS / SKIP / not run, with reason>

Reviewer asks:
- Azure AI Search Knowledge Source terminology and REST shape
- MCP Server KS request/response shape and trace wording
- Fabric Ontology KS setup and delegated source authorization wording
- Deployment-mode clarity
- Public-preview caveats and safe claims
- Security posture for generated outputs and tokens

Notes:
- No customer data or tenant-specific values are included in tracked files.
- Generated deployment reports, local env files, and screenshots remain ignored.
- This is review-only and not a public release request.
```

## 6. What To Attach Or Link

Safe to link:

- target branch or PR,
- [Reviewer Evidence Guide](12-reviewer-evidence.md),
- [Public Preview Limitations and Caveats](13-public-preview-limitations.md),
- [Storyline And Safe Claims](17-storyline-and-safe-claims.md),
- sanitized screenshots if they do not expose resource names or private endpoints.

Do not attach:

- `.env` or `.env.*`,
- `deployments/<env>/deployment-summary.md`,
- `deployments/<env>/test-report.md`,
- `.deployment/*.log`,
- raw live retrieve responses from private tenants,
- screenshots containing tenant IDs, tokens, keys, private endpoints, or resource names.

## 7. Review Triage

Sort feedback into:

| Bucket | Action |
| --- | --- |
| Blocking product terminology | Fix before broader review. |
| Preview caveat wording | Fix before blog, workshop, or external presentation. |
| Security / generated-output issue | Fix immediately and rerun no-secret scan. |
| Deployment behavior issue | Reproduce with the matching E2E mode. |
| Nice-to-have docs polish | Batch into the next docs pass. |

After changes, rerun:

```bash
bash scripts/validate-local.sh
git diff --check
```

Then regenerate the local review packet.

## Final Pre-Review Checklist

```text
[ ] Worktree clean
[ ] Local validation PASS
[ ] GitHub Actions Validate PASS
[ ] Generated reports remain ignored
[ ] Sanitized E2E evidence summary generated when deployment claims are included
[ ] Review packet generated under scratch/
[ ] Review request includes only sanitized facts
[ ] Preview caveats are linked
[ ] Public release is not implied
```
