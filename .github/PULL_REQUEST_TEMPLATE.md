## Summary

<!-- Describe what changed and why. Keep customer, tenant, and internal planning details out of the PR. -->

## Change Type

- [ ] Documentation
- [ ] REST sample / payload shape
- [ ] Notebook
- [ ] Script or deployment automation
- [ ] Demo app
- [ ] Test or validation evidence
- [ ] Other

## Deployment Mode Impact

- [ ] `mcp-only`
- [ ] `byo-fabric`
- [ ] `full`
- [ ] No deployment-mode impact

## Validation

- [ ] `bash scripts/validate-local.sh`
- [ ] `git diff --check`
- [ ] E2E report reviewed when deployment behavior changed
- [ ] Not applicable; docs-only or metadata-only change

If E2E was run, summarize the ignored report path and result:

```text
deployments/<env>/test-report.md
Result: PASS / FAIL / SKIP summary
```

Do not paste raw tokens, tenant IDs, service URLs, customer data, or generated deployment reports into this PR.

## Preview And Security Checklist

- [ ] API version remains explicit where preview APIs are used.
- [ ] No secrets, bearer tokens, API keys, tenant-specific IDs, customer data, or private endpoint details were added.
- [ ] Generated files remain under ignored paths such as `.deployment/`, `deployments/`, or `scratch/`.
- [ ] Fabric live claims are backed by live Fabric activity or clearly described as offline replay.
- [ ] MCP examples use remote HTTPS MCP servers, not local stdio servers.
- [ ] Public-facing claims follow `docs/13-public-preview-limitations.md`.
- [ ] Broader review or release candidates follow `docs/14-release-readiness-checklist.md`.

## Reviewer Notes

<!-- Link or summarize any specific evidence a reviewer should inspect. -->
