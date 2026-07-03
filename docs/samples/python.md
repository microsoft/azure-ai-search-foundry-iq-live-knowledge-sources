# Python Helpers

The Python helpers provide small, inspectable utilities for local payload generation and offline response inspection.

Use:

```text
samples/python/build_payloads.py
samples/python/inspect_retrieve_response.py
```

Run the inspector against checked-in sample responses:

```bash
python3 samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python3 samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

Use `build_payloads.py` when you want representative MCP Server KS, Fabric Ontology KS, MCP-only KB, and combined KB payloads generated from the reusable Python builders.

Next: read [Offline Replay](../09-offline-replay.md).
