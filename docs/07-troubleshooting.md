# Troubleshooting

## Knowledge Source Creation Fails

- Confirm `SEARCH_API_VERSION` is `2026-05-01-preview` or later when required by the preview.
- Confirm the source kind is supported in your search service region.
- Confirm API key or RBAC permissions are valid.
- Confirm GUID fields are valid GUIDs.

## MCP Server KS Fails

- Confirm the MCP server is reachable over HTTPS by Azure AI Search.
- Confirm the tool name in the knowledge source matches the remote MCP server.
- Confirm output parsing is compatible with the tool response.
- Increase `maxRuntimeInSeconds` if the tool is slow.
- Use query-time header passthrough for per-user credentials.

## Fabric Ontology KS Fails

- Confirm the Fabric workspace ID and ontology ID.
- Confirm the user can access the Fabric workspace and ontology.
- Confirm `x-ms-query-source-authorization` is present in retrieve calls.
- Confirm the delegated token is scoped for Azure AI Search.
- Use `includeReferenceSourceData` during validation.

