# Changelog

All notable changes to this accelerator are documented here.

## Unreleased

### Added

- Cross-platform `liveks` and `liveks.ps1` lifecycle entry points with dependency-free offline replay.
- Canonical v2 YAML schema and executable `offline`, `mcp-only`, `byo-fabric`, and `full` profiles.
- Plan-first `init`, `doctor`, `plan`, `up`, `verify`, `down`, and `e2e` commands with JSON output.
- Redacted configuration locks, explicit resource ownership, BYO-preserving cleanup, and full-capacity acknowledgement.
- GitHub Pages interactive offline replay backed by the same canonical fixtures as the CLI and managed API.
- Windows launcher CI and focused configuration, no-mutation, compatibility, and cleanup safety tests.
- BYO Fabric preflight checks that confirm the configured workspace and ontology are readable without persisting delegated tokens.
- Ignored JSON and Markdown E2E reports that preserve the existing sanitized maintainer evidence workflow.

### Changed

- YAML is now the human-managed deployment ledger; `azd env` is a generated deployment projection.
- Legacy shell and Python entry points delegate to LiveKS while retaining compatibility arguments.
- Azure Developer CLI hooks are cross-platform Python scripts.
- Bicep, postprovision, app runtime, sample env catalogs, and documentation resolve the v2 names and versions.
- The onboarding sequence is now clone, replay, bootstrap, initialize, doctor, plan, deploy, verify, and clean up.
- Live verification proves the MCP and Fabric paths independently; combined KB verification records whichever source or sources the planner selects.
- Full runs reconcile generated Fabric state, tolerate initial OneLake metadata propagation, and hand preprovisioned capacity IDs to Bicep without duplicate creation.
- Cleanup polls for Azure resource-group deletion and removes an accelerator-created residual group only when the pre-preview ownership record proves it was not pre-existing.
- Full cleanup now proves both generated resource groups are absent and the matching Fabric capacity resource count is zero, while omitting deletion claims for reused capacity.

### Compatibility

- Azure AI Search Knowledge Source API remains pinned to `2026-05-01-preview`.
- Python 3.11+, Azure Developer CLI 1.27.0+, and Node.js 22+ are required for live profiles.
- Legacy dotenv input remains supported through `--env-file` and one-time `init --from-env` migration.

## Initial Release

- Seeded MCP Server KS, Fabric Ontology KS, combined Knowledge Base routing, offline trace replay, notebooks, synthetic Airline Ops data, and one-command deployment paths.
