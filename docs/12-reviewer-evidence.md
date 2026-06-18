# Reviewer Evidence Guide

Use this guide when you are reviewing the repo before a Microsoft org push, private review, customer workshop, or blog draft.

The important point: do not judge the sample only by final answer text. A good run proves which Knowledge Source was selected, what live source was called, whether references were returned, and whether cleanup completed.

## Evidence Sources

| Evidence | Where it lives | Commit to git? | What it proves |
| --- | --- | --- | --- |
| Local validation gate | Terminal output from `bash scripts/validate-local.sh` | No | The repo builds, notebooks parse, payloads generate, offline traces inspect, no-secret scan passes, and Bicep compiles when Azure CLI is available. |
| Deployment summary | `deployments/<env>/deployment-summary.md` | No | The deployed app URL, resource names, endpoints, Knowledge Source names, Knowledge Base names, and smoke-test status. |
| E2E test report | `deployments/<env>/test-report.md` | No | Create-call-load-delete checks with PASS, FAIL, or SKIP per deployment mode. |
| Offline replay samples | `samples/responses/*.json` | Yes | Expected retrieve trace shape without live tenant dependencies. |
| Test specifications | `docs/test-specs/*.md` | Yes | The expected checks and pass criteria for each full-run path. |
| Demo app screens | Running app or local screenshots under ignored `scratch/` | No | The user-facing explanation of MCP, Fabric, combined trace, and deployment status. |

Generated deployment reports, local screenshots, logs, and scratch notes stay ignored. Do not copy tokens, tenant IDs, service URLs, or customer data from local reports into tracked docs.

## Reviewer Path

### Five minutes

1. Read [README.md](../README.md) through **First Five Minutes**.
2. Open [Choose a Pattern](02-choose-a-pattern.md).
3. Check that the three modes are understandable:
   - `mcp-only`: fastest MCP Server KS validation.
   - `byo-fabric`: connect an existing Fabric workspace and ontology.
   - `full`: create sample Fabric assets, then deploy the Azure side.
4. Run:

   ```bash
   bash scripts/validate-local.sh
   ```

5. Confirm the final line is `Local validation: PASS`.

### Fifteen minutes

1. Inspect the REST flow:
   - `samples/rest/01-create-mcp-server-ks.http`
   - `samples/rest/02-create-mcp-only-kb.http`
   - `samples/rest/03-retrieve-mcp.http`
   - `samples/rest/04-create-fabric-ontology-ks.http`
   - `samples/rest/05-create-combined-kb.http`
   - `samples/rest/06-retrieve-fabric-ontology.http`
2. Review the guided notebooks:
   - `notebooks/01-mcp-server-ks-quickstart.ipynb`
   - `notebooks/02-fabric-ontology-ks-airline-ops.ipynb`
3. Inspect offline traces:

   ```bash
   python samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
   python samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
   python samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
   ```

### Full run

Use the deployment mode that matches the review goal.

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

Each run writes:

```text
deployments/<env>/test-report.md
```

The report is intentionally ignored by git.

## Evidence By Mode

| Mode | Required evidence | Expected result |
| --- | --- | --- |
| `mcp-only` | MCP KS exists, MCP-only KB exists, MCP retrieve returns activity or references, app loads, cleanup completes | PASS without Fabric IDs. |
| `byo-fabric` | MCP KS exists, Fabric KS exists, combined KB exists, Fabric retrieve is live when a delegated token is provided or clearly offline when absent, app loads, cleanup completes | PASS when Fabric IDs are present. |
| `full` | Fabric capacity/workspace/lakehouse/ontology setup completes, Azure resources deploy, Fabric KS connects, MCP/Fabric/combined app routes respond, cleanup completes | PASS when region quota and delegated auth expectations are met. |

## What Good Looks Like

A useful evidence packet answers these questions:

- Which deployment mode was used?
- Did local validation pass before live deployment?
- Was the Knowledge Source created with the expected kind?
- Was the Knowledge Base created with the expected source list?
- Did retrieve output include `activity` and `references`?
- For MCP, did the trace show MCP Server activity or Microsoft Learn references?
- For Fabric, did the trace show Fabric Ontology activity or a clear offline replay reason?
- Did the app server return status without exposing secrets?
- Did cleanup delete the resource group?

## Reviewer Packet Template

Use this shape in a private review PR, Teams/Loop note, or reviewer email. Keep the generated reports ignored and paste only sanitized facts.

```text
Review scope:
- Repo/branch:
- Commit:
- Deployment mode reviewed: mcp-only | byo-fabric | full
- Review intent: private review | workshop rehearsal | blog validation | official sample preparation

Validation:
- Local validation: PASS / FAIL / not run
- GitHub Actions Validate: PASS / FAIL / not run
- E2E report path, local only: deployments/<env>/test-report.md
- Cleanup: PASS / FAIL / skipped, with reason

Evidence summary:
- MCP KS:
- Fabric KS:
- Knowledge Base:
- Retrieve evidence:
- App load:
- Offline replay used: yes/no, with reason

Known caveats:
- Preview API:
- Fabric quota or tenant settings:
- Delegated auth/token:
- Region/model availability:

Reviewer asks:
- Azure AI Search KS terminology and REST shape
- Fabric Ontology KS setup and delegated source authorization wording
- Deployment-mode clarity: mcp-only, byo-fabric, full
- Public-preview caveats and safe claims
- Security posture for generated outputs and tokens
```

Do not paste raw test reports into the packet. If a reviewer needs the report, share a redacted excerpt or screen-share it from the local ignored path.

## Mode-Specific Proof Points

Use these proof points to decide whether a run supports a claim.

| Claim | Minimum evidence |
| --- | --- |
| MCP Server KS works | `microsoft-learn-mcp-ks` exists, MCP-only KB exists, retrieve returns MCP activity or Microsoft Learn references. |
| Fabric Ontology KS works | Fabric KS exists, combined KB includes it, live retrieve with delegated source authorization returns Fabric activity or Fabric source data. |
| Combined routing works | Combined KB includes both source names and retrieve output includes activity or references from the expected sources for the query. |
| Demo app works | App root returns HTTP 200, `/api/status` exposes no secrets, and retrieve routes return live evidence or clearly marked offline replay. |
| Full greenfield path works | Fabric sample assets are created, generated Fabric IDs are consumed by Azure AI Search KS creation, app loads, and cleanup completes. |
| Blog or public claim is safe | Evidence above exists and wording follows [Public Preview Limitations and Caveats](13-public-preview-limitations.md). |

## What Is Not Enough

Avoid treating these as complete proof:

- A screenshot of only the final answer.
- A successful `azd up` without post-provision KS/KB checks.
- A retrieve answer with no source activity or references.
- A Fabric offline replay path described as live Fabric retrieval.
- A local report copied into tracked docs.

## Safe Sharing

For private review, summarize results in prose and attach sanitized screenshots if needed. Do not share raw deployment reports unless you have reviewed them for tenant-specific values and service URLs.
