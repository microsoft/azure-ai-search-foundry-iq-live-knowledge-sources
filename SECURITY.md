# Security

## Data Handling

- Do not commit API keys, bearer tokens, connection strings, private endpoint details, tenant-specific IDs, or customer data.
- Keep `.env` local.
- Use `.env.sample` for placeholders only.
- Redact workspace IDs, ontology IDs, search service names, user identifiers, and source payloads before sharing logs or screenshots.

## Authentication Baseline

- Use API keys only for quick proof-of-concept flows.
- Use Azure RBAC and Microsoft Entra ID for reusable implementations.
- Use delegated user auth when source permissions are user-sensitive.
- Validate Fabric workspace, ontology, and tenant permissions before running retrieve requests.
- Vet MCP servers before connecting them to a Knowledge Base.

## Preview Features

Fabric Ontology Knowledge Source and MCP Server Knowledge Source capabilities use preview APIs. Review product terms, data residency, compliance, and tenant governance requirements before using regulated or customer data.

