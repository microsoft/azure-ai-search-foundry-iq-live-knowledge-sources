# Changelog

All notable changes to this accelerator are documented here.

## Unreleased

### Added

- A generally available `search-index` profile for existing agentic-ready Azure AI Search indexes, with keyless doctor checks, stable payload planning, extractive retrieve verification, expected-term assertions, collision protection, lock-proved KS/KB ownership, and preserved-index cleanup evidence.
- A source-backed Search Index execution manual that records the required YAML inputs, success and failure messages, stable API boundary, and official Microsoft Learn contracts.
- A Codespaces and Dev Container first-live path with pinned Python, Node.js, Azure CLI, Bicep, and Azure Developer CLI tooling, plus a validation rule that prevents automatic cloud mutation during container creation.
- A source-backed, identifier-free MCP-only live evidence sample and visual that distinguish a controlled live E2E pass from the canonical offline replay.
- A stable-versus-preview API compatibility matrix covering source kinds, retrieve inputs, reasoning behavior, authentication, source authorization, and supported profiles.
- Executable offline first-success assertions and revision-bound evidence capsules for the documented `liveks try` path, plus allowlist-sanitized JSON and Markdown capsules for live E2E runs.
- Pull-request retention of the exact no-cloud first-success capsule as a short-lived `first-success-evidence` Actions artifact.
- Fabric capacity and dedicated resource-group ownership journaling, environment tags, and cleanup tests for partial provisioning, failed capacity creation, shared resource groups, missing summaries, and pre-existing capacities.
- Weekly Dependabot coverage for the root Python requirements files.
- Outcome-first clone-to-grounded-proof hero for the README and manual landing page, backed by the actual LiveKS profile, lifecycle, evidence, and cleanup contracts.
- MCP Server KS first-live-success procedure and an architecture-to-code traceability map that connect each public claim to checked-in configuration, implementation, CLI, and CI boundaries.
- Managed-organization GitHub Pages manual that leads operators from profile configuration through one Live Knowledge Source, Foundry IQ grounding evidence, native Knowledge Base MCP invocation, and known limitations, with official Microsoft Learn references.
- Native `liveks mcp` client for JSON and SSE transports, tool discovery and calls, delegated Fabric source authorization, known-fact assertions, redacted reports, and reproducible expected-failure evidence.
- Dedicated Fabric-only Knowledge Base configuration through `FABRIC_ONLY_KNOWLEDGE_BASE_NAME` so Fabric Ontology grounding can be verified independently of combined planner routing.
- Traceable Langflow benchmark adaptation record that separates observable README and workflow patterns from out-of-scope implementation details and documents independent implementation and license handling.
- Cross-platform `liveks` and `liveks.ps1` lifecycle entry points with dependency-free offline replay.
- Canonical v2 YAML schema and executable `offline`, `mcp-only`, `byo-fabric`, and `full` profiles.
- Plan-first `init`, `doctor`, `plan`, `up`, `verify`, `down`, and `e2e` commands with JSON output.
- Redacted configuration locks, explicit resource ownership, BYO-preserving cleanup, and full-capacity acknowledgement.
- GitHub Pages interactive offline replay backed by the same canonical fixtures as the CLI and managed API.
- Windows launcher CI and focused configuration, no-mutation, compatibility, and cleanup safety tests.
- BYO Fabric preflight checks that confirm the configured workspace and ontology are readable without persisting delegated tokens.
- Ignored JSON and Markdown E2E reports that preserve the existing sanitized maintainer evidence workflow.

### Changed

- README and runbook profile selection now place the stable existing-index lane between offline replay and preview MCP/Fabric deployment, while keeping the two API contracts fail-closed and separate.
- README and manual home now lead with `30-second replay -> stable existing-index live -> preview MCP-only -> Fabric expansion`; replay status and fixture badges explicitly say that no Azure call occurred.
- `search.api_version` and direct postprovision validation now fail closed on anything except the repository's tested `2026-05-01-preview` contract.
- Local and Windows validation now execute the documented first-success command; a damaged known-answer, activity, reference, or source-identity fixture fails the same entry point shown to users.
- The MCP Server guide now uses one payload-to-cleanup execution contract that distinguishes representative JSON, the resolved deployment dry-run, live retrieve evidence, and native Knowledge Base MCP content proof.
- Full create mode now rejects an existing capacity unless the same environment summary or exact tagged Bicep output proves ownership, records ARM ownership before readiness polling, and redacts administrator and generated IDs from provisioning settings output.
- Fabric cleanup deletes a capacity resource group only when this run created the group and no unrelated resources are present; otherwise it deletes only the owned capacity and verifies preservation of a pre-existing group. Missing, conflicting, or unresolved full-mode ownership now reports partial cleanup instead of a false pass.
- MCP Server and public-preview guidance now provide a reciprocal reader path, backed by a maintainer audit of the repository's documentation, CI, deployment, authentication, and traffic evidence.
- README and manual onboarding now reserve the hero for the user journey and leave Knowledge Base topology to the detailed Architecture section.
- The overview reader path now starts with dependency-free offline replay, then moves through profile selection, guarded planning, live evidence, and repository validation.
- The interactive trace demo now keeps persistent return links to the execution manual and Microsoft GitHub repository on desktop and mobile.
- README and manual onboarding now start with the repository's user, input, and result contract; profile-specific required settings; one representative first-success path; sanitized evidence; and only then advanced deployment and protocol paths.
- Live verification now distinguishes MCP protocol success from grounding-content proof. BYO Fabric operators must provide a known, non-sensitive ontology fact instead of treating a fluent response as source evidence.
- GitHub Pages CI always builds the manual, but uploads and deploys only for non-PR events in public repositories so private mirrors validate cleanly without attempting unsupported Pages publication.
- YAML is now the human-managed deployment ledger; `azd env` is a generated deployment projection.
- Legacy shell and Python entry points delegate to LiveKS while retaining compatibility arguments.
- Azure Developer CLI hooks are cross-platform Python scripts.
- Bicep, postprovision, app runtime, sample env catalogs, and documentation resolve the v2 names and versions.
- The onboarding sequence is now clone, replay, bootstrap, initialize, doctor, plan, deploy, verify, and clean up.
- Live verification proves the MCP and Fabric paths independently; combined KB verification records whichever source or sources the planner selects.
- Full runs reconcile generated Fabric state, tolerate initial OneLake metadata propagation, and hand preprovisioned capacity IDs to Bicep without duplicate creation.
- Cleanup polls for Azure resource-group deletion and removes an accelerator-created residual group only when the pre-preview ownership record proves it was not pre-existing.
- Full cleanup now proves both generated resource groups are absent and the matching Fabric capacity resource count is zero, while omitting deletion claims for reused capacity.
- Fabric-only E2E cleanup now waits for deletion and ends with a mandatory release check that proves generated workspaces and create-mode capacities are absent while preserving BYO capacity.

### Compatibility

- Search Index KS uses generally available `2026-04-01`, `intents`, and minimal extractive retrieval; MCP Server and Fabric Ontology profiles remain on `2026-05-01-preview` with `messages` and answer synthesis.
- The Knowledge Base MCP tool accepts its documented `queries` input only; retrieve-only source-forcing parameters are not sent through MCP, so independent source proof uses the corresponding single-source Knowledge Base.
- The checked-in Airline Ops terms are synthetic sample evidence and are not assumed to exist in an arbitrary BYO Fabric ontology; live assertions must match the connected ontology's own sanitized facts.
- MCP Server and Fabric Ontology Knowledge Source APIs remain pinned to `2026-05-01-preview`; the Search Index profile is pinned separately to stable `2026-04-01`.
- Python 3.11+, Azure Developer CLI 1.27.0+, and Node.js 22+ are required for live profiles.
- Legacy dotenv input remains supported through `--env-file` and one-time `init --from-env` migration.

## Initial Release

- Seeded MCP Server KS, Fabric Ontology KS, combined Knowledge Base routing, offline trace replay, notebooks, synthetic Airline Ops data, and one-command deployment paths.
