# Foundry IQ Live Knowledge Sources

Platform teams connect a governed Fabric Ontology or remote HTTPS MCP tool, submit a natural-language question to a Foundry IQ Knowledge Base, and receive a grounded result that can be inspected through REST and consumed through MCP.

[Run the managed-organization path](runbook.md){ .md-button .md-button--primary }
[Inspect the offline trace](09-offline-replay.md){ .md-button }

<figure class="manual-hero">
  <img
    src="assets/clone-to-grounded-proof.svg"
    alt="From clone to grounded proof: replay locally, choose a live profile, check with doctor and plan, deploy after confirmation, prove source evidence, and clean up generated resources."
    width="1600"
    height="800"
    loading="eager"
    fetchpriority="high"
  />
</figure>

!!! tip "First success from a fresh clone"
    Run `./liveks try`. It requires Python 3.11 or newer, installs no packages, creates no cloud resources, and prints the answer before the MCP Server and Fabric Ontology evidence trace. This proves the packaged replay contract only.

The representative path below reuses an existing Fabric workspace and ontology. It proves one source first, then calls the same Knowledge Base through its native MCP endpoint. It does not publish Fabric identifiers, tokens, endpoints, or raw live responses.

## Components At A Glance

| Component | Role in the representative path | Immediate evidence |
| --- | --- | --- |
| Domain input | `Which airlines have the highest customer-care exposure this month?` | One stable question is reused for REST and MCP. |
| Fabric Ontology Knowledge Source | Resolves governed Airline Ops entities and relationships at query time. | REST activity or references include `type: fabricOntology`. |
| Foundry IQ Knowledge Base | Plans retrieval and synthesizes the grounded result. | A live response contains answer content plus inspectable source evidence. |
| Retrieve API | Provides the auditable envelope used to prove source execution. | `activity`, `references`, and `sourceData` can be checked independently. |
| Knowledge Base MCP endpoint | Exposes `knowledge_base_retrieve` to MCP-compatible clients. | `tools/list` publishes the tool, `tools/call` returns text, and a known-fact check proves useful grounding content. |
| LiveKS CLI | Validates, plans, deploys, verifies, calls MCP, and cleans up. | Every command returns a status and nonzero failures. |

Two MCP directions are involved. The Fabric path does not route through the external MCP Server Knowledge Source:

```text
Northbound: MCP client -> Knowledge Base MCP endpoint -> Foundry IQ -> Fabric Ontology KS
Southbound: Foundry IQ Knowledge Base -> MCP Server KS -> remote HTTPS MCP tool
```

## Run One Live Knowledge Source

Use `byo-fabric` when the organization already owns the Fabric workspace and ontology. The generated Azure resources can be deleted later; the existing Fabric assets are preserved.

```bash
git clone --depth 1 https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources.git
cd azure-ai-search-foundry-iq-live-knowledge-sources
./liveks bootstrap
./liveks init --profile byo-fabric --env liveks-byo
```

Edit the ignored `.liveks/liveks-byo.yaml` ledger:

```yaml
version: 2
profile: byo-fabric
environment: liveks-byo
azure:
  location: eastus
fabric:
  workspace_id: 11111111-1111-1111-1111-111111111111
  ontology_id: 22222222-2222-2222-2222-222222222222
```

The GUIDs are resource identifiers, not secrets, but this repository still keeps tenant-specific values in ignored local files. A delegated source token is acquired transiently during verification; do not paste it into YAML.

```bash
az login --tenant <tenant-guid>
azd auth login
./liveks doctor --env liveks-byo
./liveks plan --env liveks-byo
./liveks up --env liveks-byo
```

`plan` is non-provisioning. `up` displays the Azure preview and cost context, then requires `create liveks-byo` before it creates resources. Postprovision attaches the Fabric source to a Fabric-only Knowledge Base for isolated validation and to the combined Knowledge Base for routing tests. The first live pass is not the deployment message; it is `fabricOntology` evidence from a retrieve call.

No existing Fabric ontology? Start with `mcp-only` and the [MCP Server KS path](03-mcp-server-ks.md). Use `full` only for an explicitly approved greenfield run because it creates a billable Fabric F2 capacity.

## Confirm Foundry IQ Grounding

Run the source-level verifier before testing combined routing:

```bash
./liveks verify --env liveks-byo --format json
```

For the checked-in Airline Ops ontology contract, the verifier submits:

```text
Which airlines have the highest customer-care exposure this month?
```

A sanitized pass contains these checks:

```json
{
  "checks": [
    {
      "name": "fabric-retrieve",
      "status": "pass",
      "message": "Live Fabric ontology evidence returned"
    },
    {
      "name": "knowledge-base-mcp",
      "status": "warn",
      "message": "MCP protocol content returned, but source grounding was not content-verified; repeat with --expect-term using a known non-sensitive fact."
    }
  ],
  "status": "pass"
}
```

The auditable REST evidence must include `fabricOntology` in `activity` or `references`. For the sample ontology, `sourceData` also contains `fabricAnswer` and `fabricRawData`. A useful answer without that source evidence does not prove live Fabric grounding.

If a BYO ontology uses another domain, replace the question and expected fact with a known ontology fact. Do not force the Airline Ops expectation onto unrelated organizational data.

[Use the full source-level acceptance checklist](08-test-queries.md){ .md-button .md-button--primary }

## Call It Through MCP

Each Knowledge Base is also a native MCP server. After the REST evidence proves the Fabric source independently, call the same Fabric-only Knowledge Base and business question through `knowledge_base_retrieve`:

```bash
./liveks mcp \
  --env liveks-byo \
  --query "Which airlines have the highest customer-care exposure this month?" \
  --expect-term "Alpine Air"
```

The command performs `tools/list`, invokes `tools/call`, and records only sanitized counts under the ignored `deployments/liveks-byo/` directory:

```text
LiveKS mcp: PASS
[PASS] tools-list: Knowledge Base publishes knowledge_base_retrieve.
[PASS] tools-call: knowledge_base_retrieve returned 1 text block(s).
[PASS] grounding-content: MCP content matched 1/1 expected term(s).
```

Use this sample expectation only for an Airline Ops ontology. A different BYO ontology needs its own known-answer question and non-sensitive expected fact. Running without `--expect-term` validates transport and tool execution but deliberately leaves grounding at `WARN`.

The sample deployment uses a transient Search admin key by default because it already uses local Search authentication. The key is never printed or persisted. For an organization-managed client identity with the **Search Index Data Reader** role, use the recommended bearer path:

```bash
./liveks mcp --env liveks-byo --auth bearer
```

Reproduce the delegated-authorization boundary without exposing the service response:

```bash
./liveks mcp \
  --env liveks-byo \
  --omit-source-authorization \
  --expect-failure
```

Expected normalized output:

```text
[PASS] tools-call: Expected failure reproduced: knowledge_base_retrieve returned a tool error; check source authorization and source readiness.
```

The current MCP result contains `result.content[]`, not the retrieve API's separate `activity` and `references` arrays. Its tool schema accepts only a single `queries` array, so retrieve-only `knowledgeSourceParams` cannot be forced from this client call. Therefore, the acceptance proof is the pair: source-specific REST evidence first, then an MCP known-fact match for the same Knowledge Base and question.

[Read the native MCP client contract](22-knowledge-base-mcp.md){ .md-button }

## Configuration And Known Limitations

| Concern | Supported contract |
| --- | --- |
| Authoring source | `.liveks/<environment>.yaml`; profile defaults fill omitted values. |
| Secrets | Use `{env: VARIABLE_NAME}` references. Raw values never belong in YAML, git, or reports. |
| Fastest live path | `mcp-only`; Azure sign-in is required and profile defaults are runnable. |
| Managed organization path | `byo-fabric`; `fabric.workspace_id` and `fabric.ontology_id` are required. |
| Greenfield path | `full`; Fabric quota and `--accept-fabric-capacity` are required. |
| API contract | Pinned to `2026-05-01-preview`; Microsoft Learn is authoritative when behavior changes. |
| MCP evidence | Text content proves protocol execution; a known-fact match plus REST activity is required to claim source grounding. |
| Fabric authorization | A raw end-user Search token is sent in `x-ms-query-source-authorization`, without a `Bearer` prefix. |
| BYO ownership | Cleanup deletes generated Azure resources and preserves the existing Fabric workspace and ontology. |

Continue with [Configuration](21-configuration.md), [Security and Governance](06-security-governance.md), [Troubleshooting](07-troubleshooting.md), and [Public Preview Limitations](13-public-preview-limitations.md). When the rehearsal is complete:

```bash
./liveks down --env liveks-byo
```

Require `resource-group-absent` before closing the run.

## Official Microsoft Manuals

| Need | Manual |
| --- | --- |
| Agentic retrieval and Foundry IQ | [Agentic retrieval overview](https://learn.microsoft.com/en-us/azure/search/search-agentic-retrieval-concept) |
| Knowledge Sources | [What is a Knowledge Source?](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-overview) |
| Fabric Ontology KS | [Create a Fabric Ontology knowledge source](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-fabric-ontology) |
| MCP Server KS | [Create an MCP Server knowledge source](https://learn.microsoft.com/en-us/azure/search/agentic-knowledge-source-how-to-mcp-server) |
| Knowledge Base | [Create a Knowledge Base](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-knowledge-base) |
| REST and native MCP calls | [Query a Knowledge Base using retrieve or MCP](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-retrieve) |
| Fabric Ontology | [Microsoft Fabric Ontology overview](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview) |

Do not publish tenant IDs, keys, tokens, raw live responses, generated reports, or private screenshots. Public evidence is limited to sanitized status, source type, expected-term counts, and cleanup outcome.
