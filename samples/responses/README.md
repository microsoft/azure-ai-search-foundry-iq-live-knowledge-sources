# Offline Response Samples

This folder contains synthetic retrieve responses that let you inspect expected trace shapes without live Azure or Fabric access.

Offline replay is useful for:

- reviewing `activity`,
- reviewing `references`,
- seeing source-specific `sourceData`,
- testing notebooks without tenant values,
- preparing presentation fallbacks.

## Files

| File | Shows |
| --- | --- |
| [mcp-retrieve.sample.json](mcp-retrieve.sample.json) | MCP Server KS activity and Microsoft Learn-style references. |
| [fabric-airline-ops-retrieve.sample.json](fabric-airline-ops-retrieve.sample.json) | Fabric Ontology KS activity, Airline Ops answer shape, and Fabric source data. |
| [combined-airline-ops-retrieve.sample.json](combined-airline-ops-retrieve.sample.json) | Combined MCP + Fabric trace behavior. |

## Inspect Locally

```bash
python samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

## Boundary

Offline replay is not proof of live retrieval.

Use offline replay to understand trace shape and user experience. Use E2E reports and live retrieve activity when you need to prove a live MCP or Fabric path.

For query and trace guidance, see [Test Queries And Expected Traces](../../docs/08-test-queries.md).
