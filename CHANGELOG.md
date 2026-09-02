# Changelog

All notable changes to this accelerator are documented here.

## [Unreleased]

## [2.0.0] - Unreleased

### Added

- A data-plane-only `three-source` profile that combines GA Search Index KS with preview MCP Server KS, native Fabric Ontology KS, and one preview Knowledge Base; verifies each source independently with delegated Fabric authorization; and deletes only four lock/ETag-owned Search objects while preserving every BYO asset. Credential-free tests and synthetic replay cover contract shape; Azure/Fabric live execution is **NOT RUN**.
- Strict versioned synthetic scenario packs for domain-neutral MCP guidance and the Airline Ops Fabric/combined examples, with legacy replay aliases, profile/API/ownership/cleanup validation, fixture and ontology/data drift detection, redacted evidence capsules, deterministic list/inspect/validate/run commands, and a generated manual catalog. Azure, Fabric, and protected scenario live execution remain **NOT RUN**.
- A single product release authority, deterministic allowlisted source archive, SHA-256 manifest, SPDX 2.3 SBOM validation, guarded tag workflow, full-commit-SHA Action pins, and least-privilege workflow policy checks. No tag, GitHub Release, registry package, installer, or production attestation was published.
- A machine-readable compatibility authority with generated public runtime/API/command matrices, executable POSIX and PowerShell first-path contracts, actionable cross-surface drift checks, and focused positive/negative tests. Ordinary CI remains credential-free; Azure and Fabric live validation are explicitly **NOT RUN**.
- A manual, GitHub Environment-gated `mcp-search-index` lifecycle canary with generated per-run environments, fixed concurrency, finite timeouts, explicit secret-name preflight, real `e2e --cleanup` execution, always-run guarded cleanup, and allowlist-only uploaded evidence.
- Bounded retry classification for network timeouts and HTTP `408`, `429`, `500`, `502`, `503`, and `504`, including capped `Retry-After`, exponential backoff, deterministic failure boundaries, conditional-write idempotency checks, and sanitized retry telemetry. See the official [Azure AI Search HTTP status codes](https://learn.microsoft.com/rest/api/searchservice/http-status-codes).
- A data-plane-only `mcp-search-index` profile that reuses an agentic-ready Search index and Azure OpenAI deployment, creates a GA Search Index KS plus preview MCP Server KS and combined KB, and proves each source independently before combined routing.
- Version-aware collision protection, ETag-conditional three-object lock ownership, ambiguous PUT reconciliation, redacted plan payloads, sourceData-based index assertions, dependency-ordered cleanup, and an opt-in OIDC protected live contract for the combined profile.
- The [MCP + Search Index execution manual](https://microsoft.github.io/azure-ai-search-foundry-iq-live-knowledge-sources/24-mcp-search-index-kb/) backed by official Microsoft Learn contracts for [Search Index KS](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index), [MCP Server KS](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server), [Knowledge Base creation](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base), and [retrieve](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve).
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
- Canonical v2 YAML schema and executable `offline`, `search-index`, `mcp-search-index`, `three-source`, `mcp-only`, `byo-fabric`, and `full` profiles.
- Plan-first `init`, `doctor`, `plan`, `up`, `verify`, `down`, and `e2e` commands with JSON output.
- Redacted configuration locks, explicit resource ownership, BYO-preserving cleanup, and full-capacity acknowledgement.
- GitHub Pages interactive offline replay backed by the same canonical fixtures as the CLI and managed API.
- Windows launcher CI and focused configuration, no-mutation, compatibility, and cleanup safety tests.
- BYO Fabric preflight checks that confirm the configured workspace and ontology are readable without persisting delegated tokens.
- Ignored JSON and Markdown E2E reports that preserve the existing sanitized maintainer evidence workflow.

### Changed

- The existing protected read-only retrieve test remains available, while the same test module now owns the opt-in full lifecycle canary contract. Normal CI runs neither credentialed path.
- Profile selection, CLI/configuration documentation, generated environment catalogs, and API matrices now describe the guarded `search-index -> mcp-search-index` expansion without changing any existing profile.
- Direct Search requests now accept an explicit API version so the combined lifecycle uses `2026-04-01` only for the Search Index KS and `2026-05-01-preview` only for MCP KS, combined KB, and retrieve.
- Every profile now serializes environment `plan`, `up`, and `down`; E2E holds the same lock through optional cleanup. Direct Search profiles use ETag-conditional create and delete requests and reuse unchanged owned objects without another PUT.
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

- Repository validation proves canary and resilience contract shape only. Protected live execution remains **NOT RUN** until an approved manual Environment run succeeds.
- `mcp-search-index` requires both pinned versions, an existing Azure OpenAI chat deployment, and Search managed identity access to that model; it never falls back to the standalone stable or provisioned preview request shape.
- Normal CI skips the protected live contract. Manual protected execution performs read/call verification only and does not create or delete cloud resources.
- Search Index KS uses generally available `2026-04-01`, `intents`, and minimal extractive retrieval; MCP Server and Fabric Ontology profiles remain on `2026-05-01-preview` with `messages` and answer synthesis.
- The Knowledge Base MCP tool accepts its documented `queries` input only; retrieve-only source-forcing parameters are not sent through MCP, so independent source proof uses the corresponding single-source Knowledge Base.
- The checked-in Airline Ops terms are synthetic sample evidence and are not assumed to exist in an arbitrary BYO Fabric ontology; live assertions must match the connected ontology's own sanitized facts.
- MCP Server and Fabric Ontology Knowledge Source APIs remain pinned to `2026-05-01-preview`; the Search Index profile is pinned separately to stable `2026-04-01`.
- Python 3.11+, Azure Developer CLI 1.27.0+, and Node.js 22+ are required for live profiles.
- Legacy dotenv input remains supported through `--env-file` and one-time `init --from-env` migration.

## Initial Release

- Seeded MCP Server KS, Fabric Ontology KS, combined Knowledge Base routing, offline trace replay, notebooks, synthetic Airline Ops data, and one-command deployment paths.
