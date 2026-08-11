# Document Entry-Path Audit

This maintainer record documents the evidence and decisions for the 2026-08-11 documentation transition-path review. It is excluded from the GitHub Pages build by `mkdocs.yml`; the public manual changes are limited to verified navigation gaps.

## Decision

| Change order | Decision | Evidence |
| --- | --- | --- |
| `docs/00-overview.md` | No change. | The opening explains purpose and source types, the pattern table and documentation map link to the MCP guide, and the documentation map and final safety section link to preview limitations. |
| `docs/03-mcp-server-ks.md` | Add one limitations link before the live procedure. | Prerequisites, authentication boundaries, mutating versus read-only commands, success checks, cleanup, and official guidance already exist. A direct transition to preview limitations did not. |
| `docs/13-public-preview-limitations.md` | Add one return-path sentence. | The preview and authentication boundaries already exist. Direct links back to Overview and the MCP live procedure did not. |

No command, configuration field, feature, compatibility claim, workflow permission, runtime behavior, or deployment target changed.

## Evidence Inventory

| Area | Source read in full | Verified contract |
| --- | --- | --- |
| GitHub entry surface | `README.md` | The repository Overview is manually authored in the root README and already links to the manual and preview guidance. |
| Pages entry surface | `docs/index.md`, `mkdocs.yml` | The manual starts at `docs/index.md`; all three target documents are in the Material navigation. Project-relative Markdown links are the existing convention. |
| Target documents | `docs/00-overview.md`, `docs/03-mcp-server-ks.md`, `docs/13-public-preview-limitations.md` | All three are manually authored. No generator references or writes these files. |
| Documentation build | `requirements-docs.txt`, `.github/workflows/pages.yml` | Material `9.*` builds with `mkdocs build --strict`; the static demo is built and copied to `_site/demo`. Upload and deployment run only for non-PR events in a public repository. |
| Pages permissions and concurrency | `.github/workflows/pages.yml` | Workflow permissions are `contents: read`, `pages: write`, and `id-token: write`; concurrency group is `pages` with cancellation disabled. The deploy job targets the `github-pages` environment. These settings were inspected and left unchanged. |
| Repository validation | `.github/workflows/validate.yml`, `scripts/validate-local.sh` | Validation runs with `contents: read`, Python 3.11, Node 22, local link checks, tests, secret and size checks, static-app build, and Bicep build when Azure CLI is present. No workflow concurrency is declared. |
| Static app build | `static-app/package.json`, `static-app/scripts/build.mjs`, `static-app/src/staticwebapp.config.json` | The build copies the app, canonical response fixtures, and managed API. It does not generate manual pages. SPA fallback excludes static assets and samples. |
| Azure deployment | `azure.yaml`, `scripts/deploy_static_webapp_api.py`, `infra/main.bicep` | Azure Developer CLI provisions through Bicep. Static Web Apps deploys `static-app/dist` plus the managed API with server-side app settings. |
| Authentication boundary | `config/schema.yaml`, `static-app/api/shared/search.js`, `docs/06-security-governance.md`, `docs/21-configuration.md` | Search credentials remain server-side. Fabric delegated authorization uses an environment reference and the separate query-source header; raw tokens are not persisted in the human-authored ledger or redacted lock. |
| Link validation | `scripts/check-doc-links.py` | Tracked Markdown targets are resolved from the source file directory. The added file-only relative links use the already validated repository convention. |

## Requirement Check

| Requirement | Overview | MCP Server guide | Preview limitations |
| --- | --- | --- | --- |
| Purpose is explicit | Present | Present | Present |
| Next repository path is explicit | Present | Present after this change | Present after this change |
| Prerequisites are explicit | Links to path selection and deployment guidance | Present | Mode caveats present |
| Execution and deployment boundaries are explicit | Validation loop and first-reader path present | Present | Deployment caveats present |
| Success evidence is explicit | Activity, references, and source data required | Source-specific checks present | Unsafe and preferred claims present |
| Preview boundary is reachable | Present | Added | Current page |

The review found no basis for expanding the technical content. The only public gaps were transitions between existing documents.

## External Comparison Boundary

The supplied comparison snapshot used `open-webui/open-webui` as a read-only structural reference. On 2026-08-11, its `main` branch resolved to commit `01f4282f1ffe0d6212f58d3afbeae21fffd0c4be`; the referenced README, workflow, package, Python project, and Docker files all existed at that commit. GitHub reported 148,429 stars and 21,608 forks at inspection time.

Only the abstract pattern of connecting purpose, next action, package scripts, CI, and deployment contracts was considered. No external command, directory structure, text, source code, workflow YAML, or asset was copied. GitHub reported the external repository license as `NOASSERTION`; because no material was reused, no license notice or attribution is added to this repository.

## Traffic Baseline

The baseline was captured from GitHub's repository traffic REST endpoints on 2026-08-11. The latest returned daily bucket was 2026-08-09 UTC. [GitHub documents](https://docs.github.com/en/rest/metrics/traffic) views, clones, popular paths, and referrers as trailing 14-day data.

| Signal | Verified baseline |
| --- | --- |
| Views | 181 views and 55 unique visitors for 2026-07-27 through 2026-08-09 UTC. |
| Latest seven daily view counts | 114 views for 2026-08-03 through 2026-08-09, versus 67 in the preceding seven daily buckets, a difference of 47. Custom-window uniques cannot be derived by summing daily uniques. |
| Clones | 1,523 clones and 87 unique cloners for the 14-day API window. Of these, 1,267 clones occurred on 2026-07-30, so the total is not interpreted as adoption. |
| Repository | 14 stars and 4 forks. |
| Root Overview | 73 views and 34 unique visitors. |
| MCP guide | 6 views and 6 unique visitors. |
| Repository overview guide | 4 views and 2 unique visitors. |
| Preview limitations | 4 views and 2 unique visitors. |
| Referrers | GitHub 97/16, Google 16/12, `engage.cloud.microsoft` 6/1, ChatGPT 1/1, and Teams static content 1/1, shown as views/uniques. |
| Workflow state | The latest `Validate` and `Pages` runs for organization `main` commit `9e7ef2f993ae1d9b5a9b2b0fcdeb3acc3785522a` completed successfully. |

The supplied brief labeled 181 views as a seven-day total and stated a week-over-week increase of 104. Those labels are not reproducible from the official 14-day endpoint payload and are not used as repository claims.

## Follow-Up Measurement

After the organization merge, wait until GitHub exposes a complete 14-day UTC window beginning after the merge. Capture the same endpoints and keep each signal separate.

| Signal | Baseline window | Follow-up window | Interpretation rule |
| --- | --- | --- | --- |
| Views and unique visitors | 2026-07-27 through 2026-08-09 | First complete post-merge 14-day API window | Report direction only; do not assign causality to the links. |
| Popular paths | Same trailing 14-day snapshot | Same post-merge 14-day snapshot | Compare Overview, MCP guide, overview guide, and preview limitations independently. |
| Referrers | Same trailing 14-day snapshot | Same post-merge 14-day snapshot | Do not infer an in-repository funnel from referrer totals. |
| Clones and unique cloners | Same trailing 14-day snapshot | Same post-merge 14-day snapshot | Keep automation, repeated installs, and user clones unresolved unless additional evidence exists. |
| Stars, forks, and workflow conclusions | Point-in-time on 2026-08-11 | Point-in-time after the follow-up window | Treat as adjacent signals, not outcomes caused by this patch. |

## Validation Contract

```bash
python3 scripts/check-doc-links.py
mkdocs build --strict --site-dir _site
bash scripts/validate-local.sh --no-color
git diff --check
```

After rollout, the organization `Pages` and `Validate` workflows must pass and both new links must resolve under the deployed project base path. No live Azure or Fabric resource is needed for this documentation-only review.
