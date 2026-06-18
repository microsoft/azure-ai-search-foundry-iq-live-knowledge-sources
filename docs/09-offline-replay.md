# Offline Replay

Offline replay lets you inspect expected retrieve shapes without live Azure resources, Fabric tenant access, or Microsoft Learn MCP calls.

## Why It Exists

Live Knowledge Sources are tenant and network dependent:

- MCP Server KS needs an HTTPS MCP endpoint that Azure AI Search can reach.
- Fabric Ontology KS needs a Fabric workspace, ontology item, and end-user source authorization for live retrieval.
- Combined Knowledge Bases can route differently depending on source descriptions, query wording, and model behavior.

The checked-in responses are small synthetic examples for learning the trace structure. They are not captured customer data.

## Run The Inspector

```bash
python samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

## What To Look For

For MCP Server KS:

- `activity[*].type == "mcpServer"`
- `activity[*].toolName` or `activity[*].mcpServerArguments.toolName`
- MCP references with `sourceData`

For Fabric Ontology KS:

- `activity[*].type == "fabricOntology"`
- `activity[*].fabricOntologyArguments.search`
- Fabric references with `sourceData.fabricAnswer`
- Fabric references with `sourceData.fabricRawData`

For a combined Knowledge Base, treat `knowledgeSourceParams` as runtime options, not as a strict source allow-list. If you need deterministic validation, run a single-source Knowledge Base first.
