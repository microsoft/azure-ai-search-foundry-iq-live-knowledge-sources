# Provider And Lifecycle Boundary

The provider modularization is intentionally limited to stable boundaries already shared by the direct `search-index`, `mcp-search-index`, and `three-source` profiles.

## Provider modules

- `src/liveks/providers/sources.py` owns payload construction and remote-definition matching for Search Index KS, MCP Server KS, native Fabric Ontology KS, stable extractive Knowledge Bases, and preview combined Knowledge Bases.
- `src/liveks/providers/data_plane.py` owns Azure AI Search object paths and request normalization for read, conditional create, retrieve, and conditional delete operations.
- `src/liveks/evidence.py` owns source-evidence classification and counts. Answer text is never accepted as routing evidence.
- `src/ks_factory/` remains the pure serializer used by the source operations. It does not own lifecycle policy.

Each operation carries its explicit API version. Search Index KS stays on `2026-04-01`; MCP Server KS, Fabric Ontology KS, preview Knowledge Base, and preview retrieve stay on `2026-05-01-preview`.

## Centralized in the lifecycle

`src/liveks/cli.py` continues to own:

- profile selection, sequencing, state transitions, and public report shape;
- doctor and plan gates;
- configuration-digest and environment-lock matching;
- generated-object ownership, ETag journaling, and BYO preservation;
- cleanup authorization, dependency ordering, continuation, and residual reporting;
- delegated Fabric authorization;
- independent Search Index, MCP, and Fabric evidence gates before combined retrieval;
- API compatibility checks, error classification, redaction, and public failure messages.

The provider data-plane layer accepts no ownership object and cannot authorize deletion. A delete requires an ETag already authorized or reconciled by the lifecycle. Ambiguous transport responses may be reconciled against the expected payload, but the lifecycle decides whether that result can be journaled or removed.

Provisioned `mcp-only`, `byo-fabric`, and `full` profiles retain their existing orchestration-to-script boundary. Their provider-specific deployment work was already outside the shared CLI sequence, so this change does not move or duplicate it.

## Non-goals

There is no provider registry, dynamic discovery, entry point, dependency injection container, external extension surface, or compatibility promise for third-party providers. Add another explicit implementation only after two current paths demonstrate a shared stable boundary and regression tests prove payload, report, ownership, and cleanup parity.
