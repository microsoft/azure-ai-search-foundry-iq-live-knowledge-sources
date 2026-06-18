# Fabric Ontology Knowledge Source

Primary manual: https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology

## What It Demonstrates

Fabric Ontology KS lets a Knowledge Base ground responses in Fabric IQ ontology semantics, including business definitions, entities, and relationships.

This repo uses an Airline Ops sample contract so the Fabric path has a concrete business shape even before you have production data ready:

- sample data: `samples/data/airline-ops/`
- ontology contract: `samples/ontology/airline-ops/ontology-contract.yaml`
- setup checklist: `docs/fabric-ontology-prerequisites.md`

## Notebook Walkthrough

Use `notebooks/02-fabric-ontology-ks-airline-ops.ipynb` for the guided Fabric path. It validates the Airline Ops sample facts, reviews the ontology contract, builds Fabric Knowledge Source and combined Knowledge Base payloads, optionally performs delegated live retrieve, and inspects offline Fabric traces.

## Key Design Points

- Search service and Fabric workspace must align with tenant requirements.
- The knowledge source needs Fabric workspace and ontology item IDs.
- Retrieve calls require delegated user context.
- Pass the raw user access token with `x-ms-query-source-authorization`.
- Use `includeReferenceSourceData` during validation to inspect returned source data.
- Validate data handling when Search and Fabric resources are in different regions.
- Treat the ontology as a tenant-owned prerequisite in Phase 1; this repo does not automate Fabric ontology creation yet.

## Reasoning Effort

Use `low` or `medium` retrieval reasoning effort for this pattern.

Fabric Ontology KS doesn't support `minimal`, so the Knowledge Base should include an Azure OpenAI model block when you use `low` or `medium` reasoning effort.

## Airline Ops Validation

After mapping the sample data into your own Fabric ontology, start with these questions:

| Query | Expected validation signal |
| --- | --- |
| Which airlines have the highest customer-care exposure this month? | `fabricOntology` activity and a ranking led by Alpine Air |
| Which routes have the most delayed flights over 15 minutes? | Route and Flight entities are joined by ontology relationships |
| Which delay categories are controllable and driving customer-care exposure? | DelayEvent category and exposure fields are used |

For offline trace inspection, run:

```bash
python samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
```
