# Scenario Packs

Scenario packs turn synthetic domain demonstrations into deterministic, credential-free evidence. They are separate from deployment profiles: a case selects one existing profile and its ownership/API contract but never redefines Azure or Fabric resource topology.

Manifests use strict JSON so the pre-bootstrap `./liveks try` path remains standard-library-only. `config/scenario-pack-schema.json` defines the accepted fields, versions, identifiers, assertion kinds, ownership classes, cleanup expectations, and protected-live adapter values.

<!-- scenario-catalog:start -->
## Checked-In Catalog

| Scenario ID | Version | Legacy aliases | Profile | Expected source types | Protected live |
| --- | --- | --- | --- | --- | --- |
| `airline-ops.combined-guidance-replay` | `1.0.0` | `combined`, `semantic-join` | `byo-fabric` | `fabricOntology`, `mcpServer` | not implemented |
| `airline-ops.fabric-exposure-replay` | `1.0.0` | `fabric` | `byo-fabric` | `fabricOntology` | not implemented |
| `microsoft-learn-mcp.guidance-replay` | `1.0.0` | `mcp` | `mcp-only` | `mcpServer` | not implemented |

All checked-in cases are synthetic. Ordinary validation runs every case with zero network calls.
<!-- scenario-catalog:end -->

## Commands

```bash
./liveks scenarios list
./liveks scenarios inspect combined --format json
./liveks scenarios validate --run-all --format json
./liveks scenarios run airline-ops.fabric-exposure-replay
./liveks scenarios run mcp --evidence-out .deployment/mcp-scenario.json
```

`mcp`, `fabric`, and `combined` remain explicit aliases for the existing `./liveks try --sample ...` commands. `semantic-join` now aliases the combined Airline Ops case; the former non-deployment file under `profiles/` has moved into the scenario authority.

A successful scenario run reports the exact scenario version and four assertion IDs. A failure reports the violated assertion ID and a safe diagnostic, but omits the query, expected facts, answer, source identities, `sourceData`, endpoint, tenant values, and credentials.

## Replay Proof Versus Live Proof

Scenario replay verifies a pinned synthetic fixture, expected activity and reference source types, source identity plus `sourceData` presence, and known non-sensitive facts. It performs zero network calls. It does not prove that Azure AI Search, Microsoft Learn MCP, or Fabric Ontology ran.

The optional protected-live adapter is declarative and currently **not implemented**. The existing protected canary combines Search Index and MCP sources, while these packs select `mcp-only` or `byo-fabric`. A future adapter must accept an existing configuration/environment, pass doctor and plan, retain ownership locks, and require exactly one existing E2E cleanup policy. It must not create a second lifecycle implementation.

**Azure live validation: NOT RUN. Fabric live validation: NOT RUN. Protected scenario run: NOT RUN.**

## Evidence Capsule

The ignored capsule includes scenario and pack IDs/versions, manifest and fixture digests, profile, source types/counts, assertion IDs/status, ownership class, cleanup expectation, repository revision, runtime, and explicit privacy flags. It excludes queries, expected terms, answers, raw responses, source identities, source data, resource identifiers, endpoints, tenant values, and credentials.

## Author A Pack

1. Create `scenario-packs/<pack-id>/manifest.json`.
2. Use `schemaVersion: 1`, a stable lowercase pack ID, and a semantic pack version.
3. Keep every value synthetic or public. Tenant IDs, workspace/ontology IDs, endpoints, tokens, keys, and customer data fail validation.
4. Select an existing deployment profile. Declare only evidence, ownership, cleanup, and API expectations; do not copy resource topology into the pack.
5. Put replay fixtures under `samples/responses/`, pin their SHA-256 digest, and require all four assertion kinds.
6. For a synthetic ontology domain, pin the ontology contract and combined CSV data digest. The validator checks entity counts and validation queries.
7. Run `./liveks scenarios catalog --write`, then `./liveks scenarios validate --run-all`.

Adding another synthetic domain requires only a new manifest, fixture, and optional domain contract. Python registries do not need editing.

## Product Contracts

- [Create an MCP Server Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
- [Create a Fabric Ontology Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology)
- [Create a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [Query a Knowledge Base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
- [API Compatibility](14-api-compatibility.md)
- [Offline Replay](09-offline-replay.md)
