# Contributing

This repository is a reusable sample accelerator for Azure AI Search and Foundry IQ live Knowledge Sources.

## Principles

- Keep examples tenant-neutral.
- Do not commit secrets, bearer tokens, customer names, tenant-specific IDs, or customer data.
- Keep the scope focused on Fabric Ontology Knowledge Source and MCP Server Knowledge Source.
- Link preview API examples to the relevant Microsoft Learn documentation.
- Keep reusable docs, REST requests, Python helpers, notebooks, diagrams, and sample responses in source control.

## Before Submitting Changes

- Run `bash scripts/validate-local.sh`.
- Run `git diff --check`.
- Wait for the GitHub Actions `Validate` workflow when opening a PR.
- Validate JSON payloads.
- Keep API versions explicit.
- Update troubleshooting notes for known failure modes.
- Confirm `.env.sample` contains safe placeholders only.
- Keep generated deployment reports, screenshots, logs, and scratch notes out of git.
- Treat Dependabot PRs like any other PR: wait for `Validate`, inspect the diff, and confirm preview sample behavior is unchanged.
- Use `docs/13-public-preview-limitations.md` when writing public-facing preview caveats.
- Maintainer-only release and promotion notes live under `docs/maintainers/`.
