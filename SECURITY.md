# Security

Microsoft takes the security of our software products and services seriously, which includes all source code repositories managed through our GitHub organizations.

If you believe you have found a security vulnerability in this repository, please report it to us as described below.

## Reporting Security Issues

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them to the Microsoft Security Response Center (MSRC) at [https://msrc.microsoft.com/create-report](https://aka.ms/security/create-report).

If you prefer to submit without logging in, send email to [secure@microsoft.com](mailto:secure@microsoft.com). If possible, encrypt your message with our PGP key; please download it from the [Microsoft Security Response Center PGP Key page](https://aka.ms/security/pgp).

You should receive a response within 24 hours. If for some reason you do not, please follow up via email to ensure we received your original message. Additional information can be found at [microsoft.com/msrc](https://www.microsoft.com/msrc).

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

