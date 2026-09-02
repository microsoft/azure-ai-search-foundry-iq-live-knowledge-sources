# Offline Responses

The checked-in response files let you inspect retrieve traces without Azure, Fabric, tenant access, or network calls.

Use:

```text
samples/responses/mcp-retrieve.sample.json
samples/responses/fabric-airline-ops-retrieve.sample.json
samples/responses/combined-airline-ops-retrieve.sample.json
samples/responses/three-source-airline-ops-retrieve.sample.json
```

These responses are synthetic teaching examples. They demonstrate trace shape, not proof of live tenant retrieval.

Check for:

- `mcpServer` activity in the MCP sample.
- `fabricOntology` activity in the Fabric sample.
- source-specific `references` and `sourceData`.
- combined routing behavior in the combined sample.
- `searchIndex`, `mcpServer`, and `fabricOntology` evidence in the three-source sample.

Next: run the commands in [Offline Replay](../09-offline-replay.md).
