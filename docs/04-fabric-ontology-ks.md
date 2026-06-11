# Fabric Ontology Knowledge Source

Primary manual: https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology

## What It Demonstrates

Fabric Ontology KS lets a Knowledge Base ground responses in Fabric IQ ontology semantics, including business definitions, entities, and relationships.

## Key Design Points

- Search service and Fabric workspace must align with tenant requirements.
- The knowledge source needs Fabric workspace and ontology item IDs.
- Retrieve calls require delegated user context.
- Pass the raw user access token with `x-ms-query-source-authorization`.
- Use `includeReferenceSourceData` during validation to inspect returned source data.
- Validate data handling when Search and Fabric resources are in different regions.

## Reasoning Effort

Use `low` or `medium` retrieval reasoning effort for this pattern.

Fabric Ontology KS doesn't support `minimal`, so the Knowledge Base should include an Azure OpenAI model block when you use `low` or `medium` reasoning effort.
