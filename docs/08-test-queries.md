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

Replace the sample wording with a real entity, metric, or process from your ontology.

| Test query | Expected source | What to check |
| --- | --- | --- |
| Use the governed ontology to summarize relevant business entities and relationships. | `fabric-ontology-ks` | `activity[*].type == "fabricOntology"` |
| Which ontology entities, definitions, and relationships are most relevant to this business question? | `fabric-ontology-ks` | `references[*].sourceData.fabricAnswer` and `references[*].sourceData.fabricRawData` are present |
| Which KPI, business term, or entity definition should I use for this scenario? | `fabric-ontology-ks` | The answer uses ontology semantics instead of free-form document text |

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
| What must be configured to connect a remote MCP server as a Knowledge Source? | MCP only | `activity` contains `mcpServer` and not `fabricOntology` |
| Use the governed ontology to explain the relevant business entities for this scenario. | Fabric only | `activity` contains `fabricOntology` |
| Explain the governed business entity from the ontology and cite Microsoft Learn guidance for how the Knowledge Base should inspect references. | Mixed or source-selected | Confirm whether one or both sources were selected; do not assume both will always be called |

When routing does not match your expectation, improve:

- Knowledge Source descriptions
- `retrievalInstructions`
- the query wording
- `knowledgeSourceParams.alwaysQuerySource` during controlled tests

## Pass/Fail Checklist

Treat a test as passing only when all are true:

- The answer is useful.
- The expected source appears in `activity`.
- References are returned when `includeReferences` is true.
- Source data is returned when `includeReferenceSourceData` is true.
- Authentication behavior is understood and repeatable.
- No customer, tenant, or secret values are saved into tracked sample responses.
