# Contributing

This repository is a reusable sample accelerator for Azure AI Search and Foundry IQ live Knowledge Sources.

## Principles

- Keep examples tenant-neutral.
- Do not commit secrets, bearer tokens, customer names, tenant-specific IDs, or customer data.
- Keep the scope focused on Fabric Ontology Knowledge Source and MCP Server Knowledge Source.
- Link preview API examples to the relevant Microsoft Learn documentation.
- Keep reusable docs, REST requests, Python helpers, notebooks, diagrams, and sample responses in source control.

## Before Submitting Changes

- Run `./liveks try` and confirm the answer-first replay shows both source paths.
- Run `./liveks bootstrap` once, then `./liveks doctor --profile offline --format json`.
- Run `bash scripts/validate-local.sh`.
- Run `git diff --check`.
- Wait for the GitHub Actions `Validate` workflow when opening a PR.
- Validate JSON payloads.
- Keep API versions explicit.
- Update troubleshooting notes for known failure modes.
- Confirm `.env.sample` contains safe placeholders only.
- Confirm `scripts/generate_env_examples.py --check` reports no drift from the YAML schema and profiles.
- Run `python scripts/release.py check` when changing versions, release notes, workflows, dependencies, or public artifact contents.
- For a release-affecting PR, install `requirements-release.txt` and run the credential-free artifact dry run under `.release/`.
- Keep `.liveks/` configuration and locks out of git; never put literal secrets in YAML.
- Keep generated deployment reports, screenshots, logs, and scratch notes out of git.
- Keep large videos, recordings, archives, generated builds, and dependency folders out of git. Use GitHub Releases or another artifact store for walkthrough media.
- Run `python3 scripts/check-repo-size.py` before PRs that add assets or generated outputs.
- Treat Dependabot PRs like any other PR: wait for `Validate`, inspect the diff, and confirm preview sample behavior is unchanged.
- Keep external GitHub Actions pinned to verified full commit SHAs with a major-version comment so Dependabot can update them.
- Use `docs/13-public-preview-limitations.md` when writing public-facing preview caveats.
- Maintainer-only release and promotion notes live under `docs/maintainers/`.
