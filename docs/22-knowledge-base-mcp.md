# Call The Knowledge Base Through MCP

This page covers the northbound MCP path: an MCP client calls the Knowledge Base, and Foundry IQ retrieves from the Knowledge Sources attached to that Knowledge Base.

It is different from the southbound MCP Server Knowledge Source, where Foundry IQ calls a remote HTTPS MCP server.

## Client Contract

Every Azure AI Search Knowledge Base exposes this endpoint:

```text
https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=2026-05-01-preview
```

The endpoint publishes one tool named `knowledge_base_retrieve`. The repository client sends stateless JSON-RPC 2.0 requests over HTTP and accepts either JSON or server-sent event responses.

The implementation follows the current [Microsoft Learn retrieve and MCP contract](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-retrieve). Preview behavior can change; that article remains authoritative.

## Run A Live Call

Prerequisites:

- A passing `./liveks verify --env <environment>` run.
- Azure CLI access to the deployed Search service.
- For `byo-fabric` or `full`, delegated access to the Fabric ontology.

Call the profile's deterministic single-source Knowledge Base. `mcp-only` selects the MCP-only KB; `byo-fabric` and `full` select the Fabric-only KB:

```bash
./liveks mcp --env liveks-byo
```

`mcp-search-index` exposes its combined KB instead and requires `--auth bearer`. Run its ordered REST `verify` contract first because the native MCP response does not provide separate activity and references for source-routing proof:

```bash
./liveks mcp --env liveks-combined --auth bearer
```

This no-expectation form proves endpoint discovery and tool execution only. Because the MCP response has no separate source trace, the command reports `grounding-content=warn` until a known fact is supplied.

For the synthetic Airline Ops scenario, make the expected result executable:

```bash
./liveks mcp \
  --env liveks-byo \
  --query "Which airlines have the highest customer-care exposure this month?" \
  --expect-term "Alpine Air"
```

Repeat `--expect-term` when several non-sensitive facts must be present. The command checks terms in memory, then stores counts only. It never writes the query, matched text, response content, service endpoint, key, or token to the report.

The ignored report is written to:

```text
deployments/<environment>/mcp-call-report.json
```

## Authentication Modes

### Sample Deployment Default

```bash
./liveks mcp --env liveks-byo --auth admin-key
```

The command reads the primary Search admin key through Azure CLI and keeps it in process memory only. This matches the sample app's local-auth deployment contract, but an admin key has full Search data-plane privileges and is not the preferred production client credential.

### Organization-Managed Identity

```bash
./liveks mcp --env liveks-byo --auth bearer
```

The active Azure CLI identity must have **Search Index Data Reader** on the Search service. The client acquires a token scoped to `https://search.azure.com/.default` and sends it in the `Authorization` header.

For `byo-fabric` and `full`, the client separately acquires a user Search token and sends the raw value in `x-ms-query-source-authorization`. It does not add a `Bearer` prefix to that source-authorization header.

## Evidence Contract

`./liveks mcp` performs two protocol calls and one optional content check:

1. `tools/list` must publish `knowledge_base_retrieve`.
2. `tools/call` must return at least one text content block without a JSON-RPC or tool error.
3. When `--expect-term` is supplied, every expected term must occur in the returned content.

The report is intentionally narrow:

```json
{
  "command": "mcp",
  "status": "pass",
  "checks": [
    {
      "name": "tools-list",
      "status": "pass",
      "message": "Knowledge Base publishes knowledge_base_retrieve."
    },
    {
      "name": "tools-call",
      "status": "pass",
      "contentBlocks": 1
    },
    {
      "name": "grounding-content",
      "status": "pass",
      "expectedTermCount": 1,
      "matchedExpectedTermCount": 1
    }
  ]
}
```

The native MCP response currently differs from the retrieve API response: it returns `result.content[]` and does not provide separate `activity` or `references` arrays. The published tool schema accepts exactly one `queries` array and rejects additional properties, so a client cannot add retrieve-only `knowledgeSourceParams` such as `alwaysQuerySource`. Use `./liveks verify` first to prove `fabricOntology` or `mcpServer` source execution, then require a known-fact match from `./liveks mcp` before claiming grounded MCP content. See the official [retrieve and MCP contract](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-retrieve).

## Reproduce A Failure

For a Fabric profile, omit delegated source authorization deliberately:

```bash
./liveks mcp \
  --env liveks-byo \
  --omit-source-authorization \
  --expect-failure
```

The command succeeds only if the MCP call fails. It normalizes the external error instead of printing the raw response:

```text
[PASS] tools-call: Expected failure reproduced: knowledge_base_retrieve returned a tool error; check source authorization and source readiness.
```

Other normalized failures include:

| Message | Check |
| --- | --- |
| `Azure AI Search rejected MCP authentication (HTTP 401/403).` | Client credential, role assignment, and token audience. |
| `The Knowledge Base MCP endpoint was not found (HTTP 404).` | Search endpoint, Knowledge Base name, and API version. |
| `The Knowledge Base or one of its sources failed (HTTP 5xx).` | Source readiness, delegated authorization, throttling, and dependency availability. |
| `MCP content matched N/M expected term(s).` with `grounding-content=fail` | Query suitability, source selection, source readiness, and expected facts for the connected ontology. |

Do not use `--expect-failure` as a health check. It exists to demonstrate a known boundary in a controlled environment.

## Acceptance Sequence

```bash
./liveks verify --env liveks-byo --format json
./liveks mcp \
  --env liveks-byo \
  --query "Which airlines have the highest customer-care exposure this month?" \
  --expect-term "Alpine Air"
./liveks mcp \
  --env liveks-byo \
  --omit-source-authorization \
  --expect-failure
```

Accept the scenario only when:

- `verify` reports live `fabricOntology` evidence,
- the MCP tool is discoverable,
- the MCP result contains the known synthetic fact,
- the missing-authorization run produces a normalized failure,
- no raw response or secret appears in tracked files.

For an arbitrary BYO ontology, replace both the question and `--expect-term` with a known, non-sensitive domain fact. A fluent no-data answer, a text block without an expectation, or `grounding-content=warn` is not an accepted Fabric-through-MCP result.
