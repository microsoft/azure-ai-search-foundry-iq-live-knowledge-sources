# First-Live Product And DX Overhaul

Date: 2026-08-19

## Decision

The repository keeps its current name and its safety lifecycle. The product front door now optimizes for the smallest actual Azure success:

```text
offline replay -> mcp-only live -> Fabric expansion
```

This work does not add another Knowledge Source. It makes the existing first live path reproducible, visible, and harder to confuse with replay.

## Problems Addressed

| Prior behavior | Product risk | Applied change |
| --- | --- | --- |
| README and manual home led with BYO Fabric configuration. | A new user encountered the highest tenant burden before seeing a live result. | Both entry pages now lead with `mcp-only`. |
| Demo mode cards were ordered `full`, `byo-fabric`, `mcp-only`. | The UI contradicted the documented lowest-friction path. | The app now orders `mcp-only`, `byo-fabric`, `full`. |
| GitHub Pages showed source-shaped fixtures under an MCP Live label. | A realistic replay could be mistaken for a live source call. | Status, tab, result badge, source badges, and trace copy now say replay or fixture. |
| Fresh users installed five tools manually. | Tool setup delayed the first supported path. | A pinned Dev Container supplies the supported toolchain. |
| Stable and preview behavior was summarized as one preview caveat. | Users could try a stable version with incompatible source and retrieval payloads. | A compatibility matrix and fail-closed API enum define the tested lane. |
| Live evidence existed only in ignored tenant-specific reports. | Public readers could not see a truthful, safe proof shape. | A structured sanitized evidence sample and derived visual retain only allowed fields. |

## Preserved Contracts

- `postCreateCommand` never authenticates or mutates cloud state.
- `doctor -> plan -> ARM preview -> exact confirmation -> up` remains visible.
- Offline pull-request validation remains secret-free.
- `mcp-only` requires source activity or references, expected source and tool identity, and native MCP checks.
- BYO cleanup preserves existing Fabric assets.
- Full cleanup remains ownership-gated and requires absence evidence.
- Telemetry remains disabled by default.
- Raw responses, endpoints, tenant identifiers, and credentials remain outside tracked evidence.

## Executable Acceptance

| Requirement | Enforcement |
| --- | --- |
| Dev Container versions are pinned. | `scripts/check-devcontainer.py` validates image and feature contracts. |
| Container creation cannot run deployment commands. | The same checker rejects automatic `liveks up`, `azd up`, deployment, and Fabric provisioning commands. |
| Stable API cannot reach provisioning accidentally. | YAML schema and direct postprovision validation accept only `2026-05-01-preview`. |
| Public live proof is sanitized. | Sample hygiene validates required checks, redaction flags, and absence of URLs or GUID-shaped identifiers. |
| Replay remains deterministic. | `liveks try` stays in Linux and Windows validation. |
| UI and docs remain buildable. | Static app build, Markdown links, strict MkDocs, and visual viewport checks run before promotion. |

## Deliberately Deferred

| Candidate | Reason for sequencing |
| --- | --- |
| Search Index Knowledge Source | It is a separate architecture and profile change. It should reuse this first-live journey instead of enlarging onboarding first. |
| Foundry Agent Service consumer | Useful after the first Knowledge Base endpoint is easy to reach and prove; it should stay optional. |
| Protected scheduled live canary | Requires an approved Microsoft-owned subscription, environment, secrets, retention, and cleanup ownership. It must not run on public pull requests. |
| Stable capability-aware profile | Requires a separate Search-index-only, minimal/extractive payload and live test lane. The current change fails closed instead of pretending compatibility. |
| Opt-in telemetry | Requires privacy review and explicit opt-in. Default-off remains the contract. |
| Additional domain pack | Valuable after source and verification expectations become manifest-driven rather than Airline Ops-specific. |

## Next Architecture Slice

After this first-live path is exercised from a fresh Codespace, the next product slice can wrap the existing synthetic regulatory index as a Search Index Knowledge Source. Its acceptance should prove a three-source Knowledge Base without making Fabric a prerequisite for `mcp-only`.
