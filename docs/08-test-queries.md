# Test Queries And Expected Traces

This guide makes the validation loop explicit:

```text
Question
  -> expected Knowledge Source
  -> expected activity record
  -> expected references and sourceData
```

Use these queries after creating the Knowledge Source and Knowledge Base resources in `samples/rest/`.

## MCP Server KS

Run `samples/rest/03-retrieve-mcp.http` after:

```text
samples/rest/01-create-mcp-server-ks.http
samples/rest/02-create-mcp-only-kb.http
```

| Test query | Expected source | What to check |
| --- | --- | --- |
| What must be configured to create an Azure AI Search MCP Server knowledge source? | `microsoft-learn-mcp-ks` | `activity[*].type == "mcpServer"` and `activity[*].mcpServerArguments.toolName == "microsoft_docs_search"` |
| How do I inspect activity, references, and sourceData from an Azure AI Search knowledge base retrieve response? | `microsoft-learn-mcp-ks` | `references[*].type == "mcpServer"` and `references[*].sourceData` is present |
| How can I pass per-request credentials to an MCP Server knowledge source? | `microsoft-learn-mcp-ks` | Answer mentions query-time paired control headers, not storing per-user tokens |

Good MCP trace:

```json
{
  "type": "mcpServer",
  "knowledgeSourceName": "microsoft-learn-mcp-ks",
  "mcpServerArguments": {
    "toolName": "microsoft_docs_search"
  }
}
```

## Fabric Ontology KS

Run `samples/rest/06-retrieve-fabric-ontology.http` after:

```text
samples/rest/04-create-fabric-ontology-ks.http
samples/rest/05-create-combined-kb.http
```

For this repo, map the Airline Ops sample contract first:

```text
samples/data/airline-ops/
samples/ontology/airline-ops/ontology-contract.yaml
docs/fabric-ontology-prerequisites.md
```

| Test query | Expected source | What to check |
| --- | --- | --- |
| Which airlines have the highest customer-care exposure this month? | `fabric-ontology-ks` | `activity[*].type == "fabricOntology"` and Alpine Air appears first |
| Which routes have the most delayed flights over 15 minutes? | `fabric-ontology-ks` | The answer joins Route and Flight, and delayed flights over 15 minutes total 10 |
| Which delay categories are controllable and driving customer-care exposure? | `fabric-ontology-ks` | `references[*].sourceData.fabricAnswer` and `references[*].sourceData.fabricRawData` are present |
| Which passenger-care policies or regulation topics explain the risk for the highest-exposure airline? | `fabric-ontology-ks` | The answer joins through delay category and trigger condition rather than airline-name matching |

Good Fabric trace:

```json
{
  "type": "fabricOntology",
  "knowledgeSourceName": "fabric-ontology-ks",
  "fabricOntologyArguments": {
    "search": "<natural-language ontology query>"
  }
}
```

Good Fabric reference:

```json
{
  "type": "fabricOntology",
  "sourceData": {
    "fabricAnswer": "<natural-language ontology answer>",
    "fabricRawData": "<CSV grounding data>"
  }
}
```

## Combined KB Routing

Run `samples/rest/05-create-combined-kb.http` after both Knowledge Sources exist.

| Test query | Expected source behavior | What to check |
| --- | --- | --- |
| What must be configured to connect a remote MCP server as a Knowledge Source? | MCP should provide the answer | `activity` contains an `mcpServer` call with `count > 0`; other sources can appear with `count == 0` |
| Which airlines have the highest customer-care exposure this month? | Fabric should provide the answer | `activity` contains `fabricOntology`; use a Fabric-only KB if you need deterministic source isolation |
| Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response. | Mixed or source-selected | Confirm whether one or both sources were selected; do not assume both will always be called |

When routing does not match your expectation, improve:

- Knowledge Source descriptions
- `retrievalInstructions`
- the query wording
- separate single-source Knowledge Bases for controlled tests

`knowledgeSourceParams` configures runtime options for a source, but it isn't a strict allow-list in combined Knowledge Bases. During live validation, MCP Server KS rejected `alwaysQuerySource`, so use a single-source KB when you need deterministic MCP-only or Fabric-only behavior.

## Offline Replay

Use the checked-in responses to validate trace inspection without live keys:

```bash
python samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

## Pass/Fail Checklist

Treat a test as passing only when all are true:

- The answer is useful.
- The expected source appears in `activity`.
- References are returned when `includeReferences` is true.
- Source data is returned when `includeReferenceSourceData` is true.
- Authentication behavior is understood and repeatable.
- No customer, tenant, or secret values are saved into tracked sample responses.
