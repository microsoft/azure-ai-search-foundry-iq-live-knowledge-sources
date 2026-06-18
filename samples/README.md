# Samples

This folder contains the reusable sample assets behind the accelerator.

Use it as a catalog:

| Folder | Purpose | Start here |
| --- | --- | --- |
| [rest](rest/README.md) | Raw Azure AI Search Knowledge Source and Knowledge Base REST calls. | Start here when you want exact request shapes. |
| [data/airline-ops](data/airline-ops/README.md) | Synthetic Airline Operations CSV data for the Fabric ontology path. | Start here when mapping Fabric entities and measures. |
| [ontology/airline-ops](ontology/airline-ops/README.md) | Reader-facing ontology contract for the Airline Ops sample. | Start here when creating or reviewing the Fabric ontology. |
| [responses](responses/README.md) | Offline retrieve responses for trace inspection without live Azure or Fabric access. | Start here for demos, docs, and fallback walkthroughs. |
| [python](python/README.md) | Small helper scripts for payload generation and response inspection. | Start here when validating payloads locally. |

## Recommended Flow

1. Read [rest](rest/README.md) to understand the Knowledge Source and Knowledge Base API order.
2. Inspect [data/airline-ops](data/airline-ops/README.md) and [ontology/airline-ops](ontology/airline-ops/README.md) before using Fabric.
3. Use [responses](responses/README.md) to understand the expected retrieve trace shape.
4. Use [python](python/README.md) for local payload and response checks.

## Safety Boundary

The checked-in sample data and offline responses are synthetic.

Do not add:

- customer data,
- real tenant IDs,
- raw bearer tokens,
- service URLs from private deployments,
- generated live retrieve outputs from private tenants.
