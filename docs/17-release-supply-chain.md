# Release and Supply-Chain Contract

`config/release.json` is the product release authority. It owns the accelerator version, expected tag, release status, changelog and note bindings, artifact names, archive allowlist, SPDX validator, and workflow policy. `src/liveks/__init__.py` reads the product version from this file. The private `package.json` versions remain independent component metadata.

Version `2.0.0` is based on the existing LiveKS v2 and azd template history. The existing [`walkthrough-v1`](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/releases/tag/walkthrough-v1) release remains media/documentation only.

Read the candidate [v2.0.0 release notes](releases/v2.0.0.md).

## Credential-Free Dry Run

Install the release-only validator, then build twice and compare every byte:

```bash
python -m pip install --disable-pip-version-check --no-input -r requirements-release.txt
python scripts/release.py check
python scripts/release.py dry-run --output-dir .release/dry-run
```

The dry run requires a clean tracked worktree, invokes the existing no-secret scan, builds the archive twice, compares every output byte, inspects normalized archive metadata and contents, verifies SHA-256 checksums, and validates the SPDX 2.3 JSON with `pyspdxtools`.

Expected outputs for the current candidate:

| File | Purpose |
| --- | --- |
| `azure-ai-search-foundry-iq-live-knowledge-sources-v2.0.0.tar.gz` | Deterministic allowlisted source archive. |
| `azure-ai-search-foundry-iq-live-knowledge-sources-v2.0.0-manifest.json` | Product, source revision, file-level digests, archive digest, compatibility digest, and non-publication status. |
| `azure-ai-search-foundry-iq-live-knowledge-sources-v2.0.0-sbom.spdx.json` | SPDX 2.3 package SBOM validated by the official SPDX Python tools. |
| `azure-ai-search-foundry-iq-live-knowledge-sources-v2.0.0-SHA256SUMS.txt` | SHA-256 entries for the archive, manifest, and SBOM. |

## Archive Boundary

Only tracked files matching the explicit allowlist are considered. The archive excludes local or generated `.liveks/`, `.azure/`, `.deployment/`, `.release/`, `deployments/`, dotenv catalogs, dependency folders, site/build output, maintainer-only records, the protected-canary workflow, and walkthrough media sources. Checked-in `samples/responses/*.sample.json` files are synthetic replay fixtures, not raw tenant responses.

The dry run never uploads an artifact. Pull requests retain the dry-run bundle for seven days as CI evidence only.

## Workflow Baseline

- Every external action uses a verified full commit SHA with its major tag in a comment.
- Every workflow declares top-level permissions and concurrency.
- Pages build inherits only `contents: read`; only the deploy job receives `pages: write` and `id-token: write`.
- Azure OIDC remains only in the protected canary job.
- Protected canary concurrency remains fixed and non-cancelling so cleanup is not interrupted.
- Release publication can run only for a `v*` tag push in `microsoft/azure-ai-search-foundry-iq-live-knowledge-sources`.
- The tag guard requires the configured tag, checked-out commit, `GITHUB_SHA`, and a commit reachable from `origin/main` to agree.
- Production publication uses the short-lived `GITHUB_TOKEN`; GitHub artifact attestation uses job-scoped OIDC.

The current authority is `unreleased`, so a tag publication attempt fails until maintainers set a release date and status `ready` in the same reviewed change.

## Evidence Boundary

Pull-request CI proves policy shape, deterministic artifact construction, checksums, and SPDX validation. It does not prove a tag was pushed, a GitHub Release was created, a production attestation was issued, or any Azure/Fabric path ran.

**Tag publication: NOT RUN. GitHub Release publication: NOT RUN. Production attestation: NOT RUN. Azure live validation: NOT RUN. Fabric live validation: NOT RUN.**
