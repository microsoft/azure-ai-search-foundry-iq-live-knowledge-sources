# MemPalace First-Run Evidence Adaptation Audit

This maintainer record captures the 2026-08-15 read-only benchmark review and the repository-native adaptation. It is excluded from the public Pages build. No MemPalace code, workflow YAML, prose, branding, visual assets, commands, or domain model were copied.

## External Evidence

| Item | Verified value |
| --- | --- |
| Repository | `MemPalace/mempalace` |
| Default branch at review | `develop` |
| Reviewed revision | `06cb6987f02610784fefbad4b2bd5d026d164ba6` |
| Commit time | `2026-08-15T01:20:07Z` |
| License | MIT, confirmed by GitHub metadata and the root `LICENSE` at the reviewed revision |
| Repository snapshot | 58,379 stars and 7,498 forks when queried on 2026-08-15 |

Observed paths and the abstract pattern considered:

| Upstream path | Observation | Adaptation boundary |
| --- | --- | --- |
| `README.md` headings `What it is`, `Install`, `Docker`, `Quickstart`, and `Benchmarks` | The reader moves from product boundary to a short run path and then to evidence. | Keep LiveKS terminology and the existing replay-to-live progression; make the first documented command assert its own contract. |
| `.github/workflows/docker-publish.yml` | A runtime smoke job gates image publication and calls a dedicated smoke script. | Run the LiveKS no-cloud entry point in the existing validation gate. Do not introduce Docker because this repository's first path is a dependency-free Python replay. |
| `scripts/docker-smoke.sh` | The shipped runtime, persistence, MCP handshake, and Compose syntax are tested rather than inferred from a build. | Assert the Foundry IQ fixture's known answer, activity, references, and source identities. Retain the existing protected live retrieve and Knowledge Base MCP checks for cloud claims. |
| `LICENSE` | MIT permission and notice are present. | No substantial material was reused, so no copied notice is added. This repository remains under its existing MIT license. |

The official `actions/upload-artifact` action added for short-lived CI evidence was separately checked as an active MIT-licensed GitHub repository. It follows this repository's existing major-version action policy.

## Internal Baseline

| Contract | Existing state | Finding |
| --- | --- | --- |
| First documented command | README and manual start with dependency-free `./liveks try`. | Correct user path, but Linux validation did not execute the wrapper exactly as documented. |
| Offline result | `tools/try_offline.py` printed canonical response fixtures. | `status` was fixed to `pass`, so missing source evidence could still produce a successful command. |
| Configuration failures | Schema v2 fails closed on unknown fields, raw secret values, and missing BYO Fabric IDs. | Already meets the no-credential PR contract; retain it. |
| Southbound MCP transport | MCP Server KS is documented and built as a reachable remote HTTPS endpoint. | Already explicit; stdio Docker flags are inapplicable. |
| Northbound MCP transport | `liveks mcp` uses stateless JSON-RPC 2.0 over HTTP and parses JSON or SSE. | Already covered by protocol, content, failure-normalization, and persistence tests. |
| Protected live evidence | `verify`, `mcp`, and `e2e` separate source trace proof, protocol success, known-fact grounding, controlled failure, and cleanup. | Keep protected and tenant-specific. Do not add cloud mutations to PR validation. |
| Evidence files | Detailed JSON and Markdown E2E reports are ignored. | They can contain local messages or identifiers and lacked a separate allowlist-sanitized machine manifest. |

## Independent Implementation

1. `liveks try` now derives its status from four Foundry IQ replay invariants: a known synthetic fact, required activity source types, required reference source types, and required Knowledge Source identities.
2. `--evidence-out` writes a no-cloud capsule with repository revision, runtime, fixture digest, source counts, and assertion status. Answer text, query text, the raw response, and credentials are excluded by construction.
3. The existing local gate runs the same first-success entry point shown in README. Pull requests retain the resulting capsule for 14 days.
4. Live E2E writes separate allowlist-sanitized JSON and Markdown capsules. Only profile, revision, assertion names and statuses, proved source types, and a digest of the detailed local report cross into the capsule.
5. Detailed E2E messages, environment names, resource identifiers, service endpoints, raw responses, and credentials remain outside the sanitized capsules and outside git.

## Validation Contract

| Claim | Required check |
| --- | --- |
| Packaged first success is intact | `./liveks try --evidence-out .deployment/first-run-evidence.json` returns zero and reports four passing assertions. |
| A fixture regression fails visibly | Unit tests remove expected reference evidence and require a failing report. |
| Offline capsule is safe-field-only | Unit tests inject answer and query markers and require both to be absent from serialized evidence. |
| Live capsule is safe-field-only | Unit tests inject a token-like value, private endpoint, and environment name into detailed evidence and require all to be absent from the capsule. |
| Repository contracts remain aligned | `bash scripts/validate-local.sh --no-color` and `git diff --check` pass. |

## Explicit Non-Adaptations

- No MemPalace name, palace terminology, benchmark result, product claim, branding, image, or community wording is used.
- No Docker image, persistence volume, stdio `-i`, Compose setting, backend plugin, coverage threshold, platform matrix, retry rule, release branch, or package publishing design is adopted.
- No MemPalace performance number is presented as LiveKS evidence.
- Offline replay still proves response shape only. Live `mcpServer` or `fabricOntology` claims still require protected source-specific verification, and native MCP grounding still requires a known-fact assertion paired with retrieve evidence.
