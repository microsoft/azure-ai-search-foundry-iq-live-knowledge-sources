# REST Samples

This folder shows the raw Azure AI Search Knowledge Source and Knowledge Base REST flow.

Use these files when you want to see the exact request shapes without the deployment wrapper or notebooks.

## Run Order

| Step | File | Purpose |
| --- | --- | --- |
| 1 | [01-create-mcp-server-ks.http](01-create-mcp-server-ks.http) | Create the Microsoft Learn MCP Server Knowledge Source. |
| 2 | [02-create-mcp-only-kb.http](02-create-mcp-only-kb.http) | Create a Knowledge Base that uses only the MCP source. |
| 3 | [03-retrieve-mcp.http](03-retrieve-mcp.http) | Retrieve from the MCP-only Knowledge Base and inspect activity, references, and sourceData. |
| 4 | [04-create-fabric-ontology-ks.http](04-create-fabric-ontology-ks.http) | Create the Fabric Ontology Knowledge Source after Fabric workspace and ontology IDs are ready. |
| 5 | [05-create-combined-kb.http](05-create-combined-kb.http) | Attach both MCP Server KS and Fabric Ontology KS to one Knowledge Base. |
| 6 | [06-retrieve-fabric-ontology.http](06-retrieve-fabric-ontology.http) | Retrieve from Fabric Ontology KS with delegated source authorization. |
| 7 | [08-retrieve-combined-airline-ops.http](08-retrieve-combined-airline-ops.http) | Run the combined Airline Ops + Microsoft Learn trace query. |
| Cleanup | [07-delete-resources.http](07-delete-resources.http) | Delete the Knowledge Base and Knowledge Sources created by the REST samples. |

## Modes

| Mode | REST files |
| --- | --- |
| `mcp-only` | `01`, `02`, `03`, then optional `07` cleanup |
| `byo-fabric` | `01`, `02`, `03`, `04`, `05`, `06`, `08`, then optional `07` cleanup |
| `full` | Prefer `scripts/deploy.sh --mode full`; use these REST files to inspect or replay the KS/KB layer |

## Variables To Set

Common variables:

```text
@searchEndpoint
@apiVersion
@searchApiKey
@knowledgeBaseName
```

Model variables:

```text
@azureOpenAIEndpoint
@azureOpenAIDeploymentId
@azureOpenAIModelName
@azureOpenAIApiKey
```

Fabric variables:

```text
@fabricWorkspaceId
@fabricOntologyId
@userSearchToken
```

`@userSearchToken` is a raw end-user token scoped to:

```text
https://search.azure.com/.default
```

Do not prefix it with `Bearer`. Do not commit real token values.

## What To Inspect

For retrieve calls, turn on:

```json
"includeActivity": true
```

Then inspect:

- `activity`
- `references`
- `references[*].sourceData`
- `sourceData.fabricAnswer`
- `sourceData.fabricRawData`

For guidance on what counts as good evidence, see [Reviewer Evidence Guide](../../docs/12-reviewer-evidence.md).
