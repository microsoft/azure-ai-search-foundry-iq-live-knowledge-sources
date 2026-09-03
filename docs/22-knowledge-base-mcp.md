# Call The Knowledge Base Through MCP

This page covers the northbound MCP path: an MCP client calls the Knowledge Base, and Foundry IQ retrieves from the Knowledge Sources attached to that Knowledge Base.

It is different from the southbound MCP Server Knowledge Source, where Foundry IQ calls a remote HTTPS MCP server.

## Client Contract

Every Azure AI Search Knowledge Base exposes this endpoint:

```text
https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=2026-05-01-preview
```

The endpoint publishes one tool named `knowledge_base_retrieve`. The repository client sends stateless JSON-RPC 2.0 requests over HTTP and accepts either JSON or server-sent event responses.

The implementation follows the endpoint, authentication, and tool shape in the current [Microsoft Learn retrieve and MCP contract](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-retrieve). That article now also documents a newer preview API. This repository's deployed preview profiles and consumer remain pinned to `2026-05-01-preview`; the standalone consumer rejects a different version instead of silently claiming compatibility.

## Independent Consumer

[`samples/python/knowledge_base_mcp_consumer.py`](https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources/blob/main/samples/python/knowledge_base_mcp_consumer.py) proves the northbound MCP surface without importing or invoking the lifecycle CLI. It uses the lifecycle-neutral JSON/SSE transport and protocol helpers in `src/liveks/mcp_client.py`.

Run `./liveks bootstrap` first. Then supply configuration through process environment variables so credentials never appear in command arguments or generated files.

| Variable | Requirement |
| --- | --- |
| `AZURE_SEARCH_MCP_ENDPOINT` | Full HTTPS Knowledge Base MCP endpoint, including this repository's `api-version=2026-05-01-preview`. |
| `AZURE_SEARCH_MCP_QUERY` | A non-sensitive question suitable for the deployed Knowledge Base. |
| `AZURE_SEARCH_MCP_EXPECT_TERM` | One known, non-sensitive fact that must occur in returned text. This is mandatory. |
| `AZURE_SEARCH_MCP_AUTH_MODE` | Optional: `bearer` (default and recommended) or `admin-key`. |
| `AZURE_SEARCH_MCP_BEARER_TOKEN` | Required for `bearer`; a Search-scoped token whose identity has **Search Index Data Reader**. |
| `AZURE_SEARCH_ADMIN_KEY` | Required for `admin-key`; use only for sample development because it grants broad Search access. |
| `AZURE_SEARCH_MCP_SOURCE_AUTHORIZATION` | Optional raw user Search token for a Knowledge Base whose source enforces delegated access. Do not add a `Bearer` prefix. |

The endpoint must use `https://<service>.search.windows.net/knowledgebases/<name>/mcp` with exactly the pinned API query parameter. The consumer never prints the endpoint, Knowledge Base name, query, expected term, headers, token, response body, content, or source identity.

**POSIX**

```bash
export AZURE_SEARCH_MCP_ENDPOINT='https://<service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=2026-05-01-preview'
export AZURE_SEARCH_MCP_AUTH_MODE='bearer'
export AZURE_SEARCH_MCP_QUERY='<non-sensitive question>'
export AZURE_SEARCH_MCP_EXPECT_TERM='<known non-sensitive fact>'
read -rsp 'Search bearer token: ' AZURE_SEARCH_MCP_BEARER_TOKEN && echo
export AZURE_SEARCH_MCP_BEARER_TOKEN
.liveks/venv/bin/python samples/python/knowledge_base_mcp_consumer.py --format json
unset AZURE_SEARCH_MCP_BEARER_TOKEN
```

**Windows PowerShell**

```powershell
$env:AZURE_SEARCH_MCP_ENDPOINT = 'https://<service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=2026-05-01-preview'
$env:AZURE_SEARCH_MCP_AUTH_MODE = 'bearer'
$env:AZURE_SEARCH_MCP_QUERY = '<non-sensitive question>'
$env:AZURE_SEARCH_MCP_EXPECT_TERM = '<known non-sensitive fact>'
$env:AZURE_SEARCH_MCP_BEARER_TOKEN = Read-Host 'Search bearer token' -MaskInput
.\.liveks\venv\Scripts\python.exe samples\python\knowledge_base_mcp_consumer.py --format json
Remove-Item Env:AZURE_SEARCH_MCP_BEARER_TOKEN
```

For an admin-key development call, set `AZURE_SEARCH_MCP_AUTH_MODE=admin-key` and securely populate `AZURE_SEARCH_ADMIN_KEY` instead. If delegated source access is required, securely populate `AZURE_SEARCH_MCP_SOURCE_AUTHORIZATION` for the same process.

The sample executes `tools/list`, requires `knowledge_base_retrieve`, and then sends `tools/call` with exactly `{"queries": ["<question>"]}`. Its JSON output is allowlist-only:

```json
{
  "checks": [
    {"name": "endpoint-configuration", "status": "pass"},
    {"headerCount": 1, "name": "authentication-readiness", "status": "pass"},
    {"name": "tools-list", "status": "pass", "toolCount": 1},
    {"name": "tools-call", "status": "pass"},
    {"contentBlockCount": 1, "name": "text-content", "status": "pass"},
    {
      "expectedTermCount": 1,
      "matchedExpectedTermCount": 1,
      "name": "grounding-content",
      "status": "pass"
    }
  ],
  "command": "knowledge-base-mcp-consumer",
  "mode": {
    "apiVersion": "2026-05-01-preview",
    "authentication": "bearer",
    "responseFormats": ["json", "sse"],
    "sourceAuthorization": "absent",
    "transport": "stateless-json-rpc-2.0-over-https"
  },
  "schemaVersion": 1,
  "status": "pass"
}
```

Exit code `0` means every check passed. Exit code `2` means local configuration or credential readiness failed before network access. Exit code `1` means endpoint, protocol, tool, text, or expected-term validation failed. `--format text` emits only check names, status, and normalized error categories.

| Error category | Meaning |
| --- | --- |
| `missing-configuration`, `invalid-endpoint`, `unsupported-api-version` | Required endpoint, query, expected term, or pinned endpoint shape is missing or invalid. |
| `unsupported-auth-mode`, `missing-credential`, `invalid-credential` | Authentication input is not one of the two supported environment-only modes. |
| `authentication-rejected` | Azure AI Search returned HTTP 401 or 403. |
| `endpoint-not-found` | The Knowledge Base MCP endpoint returned HTTP 404. |
| `request-timeout-exhausted`, `throttling-exhausted`, `service-error` | A classified transient or service response remained after bounded retries. |
| `network-timeout-exhausted`, `network-error`, `malformed-response` | The transport failed or returned invalid JSON/SSE. |
| `json-rpc-error`, `missing-tool`, `tool-call-error` | MCP discovery or invocation failed. |
| `missing-text-content`, `expected-term-mismatch` | Protocol execution returned no usable text or omitted the required known fact. |

Only already classified transient HTTP/network failures are retried, at most three attempts. Authentication, endpoint, schema, tool, and content failures are deterministic and are not retried.

The consumer's text-content check proves MCP protocol content only. It does not expose REST `activity`, `references`, or `sourceData`. Run source-specific `./liveks verify` first and inspect its sanitized evidence before naming which Knowledge Source ran.

## Lifecycle-Bound Client

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

## Optional Foundry Agent Decision

No Foundry Agent sample is included in this change. The current public [Foundry Agent connection guide](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect) requires a Foundry project, model deployment, RBAC, a project MCP connection, the preview `azure-ai-projects` dependency, and a newer preview API contract. Creating or exercising those resources would violate this sample's credential-free, no-cloud-mutation validation boundary and add installer complexity unrelated to the standalone consumer. Use the official guide as the source of truth for an explicitly approved future integration; this accelerator makes no production-readiness claim for that path.
