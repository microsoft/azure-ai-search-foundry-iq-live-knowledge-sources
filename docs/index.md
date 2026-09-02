# Foundry IQ Live Knowledge Sources

Wrap and prove an existing Azure AI Search index with the stable API, compose it with preview MCP Server retrieval, then extend the same guarded lifecycle to governed Fabric Ontology sources.

[Start the stable live path](23-search-index-ks.md){ .md-button .md-button--primary }
[Inspect the no-cloud replay](09-offline-replay.md){ .md-button }

<figure class="manual-hero">
  <img
    src="assets/clone-to-grounded-proof.svg"
    alt="Three stages from clone to proof: a 30-second offline replay, a choice between stable Search Index and preview MCP live paths, and advanced Fabric expansion."
    width="1600"
    height="760"
    loading="eager"
    fetchpriority="high"
  />
</figure>

## Choose Your Outcome

| Role | Finish line | Start here |
| --- | --- | --- |
| **Evaluator** | Inspect the packaged answer and trace contract with no cloud access. | `./liveks try` |
| **Search implementer** | Prove an existing agentic-ready index through the GA data plane. | [Stable Search Index KS](23-search-index-ks.md) |
| **Knowledge composer** | Combine that existing index with Microsoft Learn MCP without provisioning a new service. | [MCP + Search Index KB](24-mcp-search-index-kb.md) |
| **Three-source composer** | Add an existing native Fabric ontology to the reused Search and MCP path. | [Preview Three-Source KB](25-three-source-kb.md) |
| **Azure implementer** | Prove Microsoft Learn MCP runs live through the preview Foundry IQ path. | [Codespaces First Live](15-codespaces-first-live.md) |
| **Fabric implementer** | Add governed entities and relationships after the Azure path works. | [Fabric Live BYO Validation](11-fabric-live-byo-validation.md) |

The accelerator is not a production reference architecture. It keeps the human path narrow while [AGENTS.md](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/AGENTS.md) defines the separate execution contract for coding agents.

## 30-Second Replay

```bash
./liveks try --evidence-out .deployment/first-run-evidence.json
```

Require `Contract: PASS (4/4 assertions)`. Python 3.11 or newer is the only dependency, no package is installed, and no cloud resource is created.

!!! warning "Replay is not live"
    The replay proves a checked-in response and evidence contract. A realistic answer, `mcpServer` activity, or `fabricOntology` activity in this fixture does not prove that Azure called either source.

The ignored evidence capsule retains scenario/pack versions, revision, manifest and fixture digests, source types/counts, assertion status, ownership, and cleanup expectation. It excludes query, expected terms, answer, raw response, source identities, sourceData, endpoints, tenant values, and credentials. Pull-request validation executes the same entry point.

## Lowest-Risk Live: Existing Search Index

```bash
./liveks init --profile search-index --env liveks-index
# Fill the existing endpoint, index, semantic configuration, and optional fields.
az login --use-device-code --tenant <tenant-guid>
./liveks doctor --env liveks-index
./liveks plan --env liveks-index
./liveks up --env liveks-index
./liveks verify --env liveks-index --query "<question>" --expect-term "<known term>"
```

This generally available `2026-04-01` lane creates only a Search Index KS and minimal extractive Knowledge Base. The Search service and index remain reused assets, and cleanup must finish with `search-index-preserved=pass`.

[Follow the stable execution contract](23-search-index-ks.md){ .md-button .md-button--primary }

## Compose Existing Search With MCP

```bash
./liveks init --profile mcp-search-index --env liveks-combined
# Fill existing Search index and Azure OpenAI deployment values.
./liveks doctor --env liveks-combined
./liveks plan --env liveks-combined
./liveks up --env liveks-combined --query "<index question>" --expect-term "<known term>"
```

The Search Index KS remains on GA `2026-04-01`. MCP Server KS, the combined KB, and the three ordered retrieve calls use `2026-05-01-preview`. Independent `searchIndex` and `mcpServer` evidence must pass before combined routing evidence is reported. The Search service, index, and Azure OpenAI deployment remain reused assets.

[Follow the two-source execution contract](24-mcp-search-index-kb.md){ .md-button .md-button--primary }

When existing native Fabric assets are also ready, continue to the [three-source execution contract](25-three-source-kb.md).

## First Preview Live: MCP-Only

The checked-in Codespaces environment supplies Python 3.11, Node.js 22, Azure CLI, Bicep, and Azure Developer CLI. Container creation runs only safe local checks.

```bash
./liveks init --profile mcp-only --env liveks-mcp
az login --use-device-code --tenant <tenant-guid>
azd auth login --use-device-code
./liveks doctor --env liveks-mcp
./liveks plan --env liveks-mcp
./liveks up --env liveks-mcp
```

`doctor` and `plan` must pass before creation. `up` runs an ARM preview and waits for `create liveks-mcp` before provisioning. The result is a hosted app, MCP Server KS, and MCP-only Knowledge Base without any Fabric dependency.

Typical duration is 10-20 minutes. The exact subscription, region, model availability, and ARM preview determine the actual result and cost.

### Prove Source Execution

```bash
./liveks verify --env liveks-mcp --format json
./liveks mcp \
  --env liveks-mcp \
  --query "What must be configured for an Azure AI Search MCP Server knowledge source?" \
  --expect-term "Azure AI Search"
```

A pass requires:

1. a live app status,
2. `mcpServer` activity or references,
3. `microsoft-learn-mcp-ks` and `microsoft_docs_search` identity,
4. native MCP tool discovery, call, and expected-term checks.

<figure class="manual-hero">
  <img
    src="assets/mcp-only-live-proof.png"
    alt="Sanitized evidence from a controlled live MCP-only validation."
    width="1600"
    height="760"
    loading="lazy"
  />
</figure>

The source-backed public record is `samples/evidence/mcp-only-live-proof.sample.json` in the repository. It is derived from a controlled live E2E run and excludes endpoint, tenant, query, answer, raw response, and credentials. The image explains the evidence shape; it does not replace `verify`.

[Follow every Codespaces step](15-codespaces-first-live.md){ .md-button .md-button--primary }
[Use the local execution runbook](runbook.md){ .md-button }

## Expand To Fabric

| Profile | Add it when | Required proof |
| --- | --- | --- |
| `byo-fabric` | Existing workspace and ontology IDs are ready. | Separate MCP and Fabric retrieve checks, then combined routing. |
| `full` | Greenfield creation and billable F2 capacity are explicitly approved. | Generated Fabric readiness, both source checks, and complete teardown. |

BYO cleanup preserves the existing Fabric assets. Full cleanup deletes only assets proven to be generated by the same environment. Start with [Choose a Pattern](02-choose-a-pattern.md), then use [Fabric Prerequisites](fabric-ontology-prerequisites.md) or [Fabric Live BYO Validation](11-fabric-live-byo-validation.md).

## What Gets Demonstrated

| Component | Role | Acceptance evidence |
| --- | --- | --- |
| Search Index KS | Wraps an existing index for stable extractive retrieval. | `searchIndex` evidence, expected content, and preserved-index cleanup proof. |
| MCP Server KS | Calls an explicitly allowed remote HTTPS MCP tool. | `mcpServer` activity or references and tool identity. |
| Fabric Ontology KS | Resolves governed business entities and relationships. | `fabricOntology` activity or references plus source data. |
| Foundry IQ Knowledge Base | Selects sources and returns grounded output. | Answer, `activity`, `references`, and `sourceData`. |
| Native Knowledge Base MCP | Publishes `knowledge_base_retrieve` to MCP clients. | `tools/list`, `tools/call`, and a known-fact match. |
| LiveKS | Plans, deploys, verifies, and cleans up. | Nonzero failures, sanitized reports, and absence checks. |

Two MCP directions are distinct:

```text
Northbound: MCP client -> Knowledge Base MCP endpoint -> Foundry IQ -> Knowledge Source
Southbound: Foundry IQ -> MCP Server KS -> remote HTTPS MCP tool
```

Fabric Ontology is a native Knowledge Source and is not routed through the external MCP Server KS.

## Configuration And API Boundary

The ignored `.liveks/<environment>.yaml` file is the authoring ledger. `azd env` is generated state. Secrets are environment references, never raw YAML values.

`search-index` is pinned to generally available `2026-04-01`, `intents`, and minimal extractive retrieval. `mcp-search-index` and `three-source` pin Search Index KS separately to `2026-04-01` and MCP/Fabric/KB/retrieve operations to `2026-05-01-preview`. Other live compositions remain preview-only. Cross-lane API overrides fail closed.

[Compare stable and preview support](14-api-compatibility.md){ .md-button }

## Finish With Cleanup

```bash
./liveks down --env <environment>
```

For `search-index`, `mcp-search-index`, and `three-source`, require `search-index-preserved=pass`; three-source also requires `fabric-assets-preserved=pass`. For provisioned preview profiles, require `resource-group-absent=pass`.

## Manual Map

| Need | Manual |
| --- | --- |
| Shortest complete sequence | [Execution Runbook](runbook.md) |
| Stable existing-index path | [Stable Search Index KS](23-search-index-ks.md) |
| Existing-index plus MCP composition | [MCP + Search Index KB](24-mcp-search-index-kb.md) |
| Existing Search plus MCP plus native Fabric | [Preview Three-Source KB](25-three-source-kb.md) |
| Every first-live Codespaces step | [Codespaces First Live](15-codespaces-first-live.md) |
| MCP payload and source contract | [MCP Server Knowledge Source](03-mcp-server-ks.md) |
| Fabric source contract | [Fabric Ontology Knowledge Source](04-fabric-ontology-ks.md) |
| Post-deployment clicks and queries | [Guided Live Demo](16-demo-walkthrough.md) |
| Trace-level acceptance | [Post-Deployment Tests](08-test-queries.md) |
| Stable vs preview API | [API Compatibility](14-api-compatibility.md) |
| Configuration authority | [Configuration](21-configuration.md) |
| Security and safe claims | [Security and Governance](06-security-governance.md) |
| Failure recovery | [Troubleshooting](07-troubleshooting.md) |

## Microsoft Sources Of Truth

- [Agentic retrieval overview](https://learn.microsoft.com/azure/search/search-agentic-retrieval-concept)
- [Knowledge Source overview](https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview)
- [Create a Search Index knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index)
- [Create an MCP Server knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server)
- [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology)
- [Query a Knowledge Base using retrieve or MCP](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
