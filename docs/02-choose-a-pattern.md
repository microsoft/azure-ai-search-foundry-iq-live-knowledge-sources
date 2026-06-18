# Choose a Pattern

![Deployment modes](../assets/deployment-modes.svg)

| Pattern | Use when | Start here |
| --- | --- | --- |
| MCP Server KS | You need a low-friction public preview quickstart or tool-backed live retrieval | `samples/rest/01-create-mcp-server-ks.http` |
| Fabric Ontology KS | You need governed business semantics from Microsoft Fabric | `samples/rest/04-create-fabric-ontology-ks.http` |
| Combined KB | You need to validate multi-source routing and trace behavior | `samples/rest/05-create-combined-kb.http` |

## Deployment Modes

Start with `mcp-only` unless you already have Fabric workspace and ontology IDs ready.
If you are choosing between `byo-fabric` and `full`, skim the [FAQ](19-faq.md) before deploying. It calls out the most common points of confusion: offline replay, Fabric source authorization, Fabric quota, and MCP endpoint requirements.

| Mode | Use when | Success signal |
| --- | --- | --- |
| `mcp-only` | You want the fastest Azure AI Search MCP Server KS validation without Fabric. | MCP retrieve returns activity or references from `microsoft_docs_search`. |
| `byo-fabric` | You already have a Fabric workspace and ontology and want the validated live Fabric path. | Fabric KS is created and live retrieve works with delegated source authorization, or offline replay explains what is missing. |
| `full` | You want a greenfield path that creates the Fabric sample stack and connects it to Azure AI Search. | Fabric IDs are generated, KS/KB assets are created, app loads, and cleanup evidence is recorded. |

Command shapes:

```bash
bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus

bash scripts/deploy.sh \
  --mode byo-fabric \
  --env-file .env.external.local \
  --env-name liveks-byo \
  --location eastus

bash scripts/deploy.sh \
  --mode full \
  --env-name liveks-full \
  --location eastus \
  --fabric-location westus3
```

## Recommended Order

1. Create the MCP Server KS.
2. Create the MCP-only Knowledge Base.
3. Retrieve from MCP and inspect `activity`, `references`, and source data.
4. Add Fabric Ontology KS with BYO Fabric IDs or run `--mode full` to create the sample Fabric assets.
5. Create a combined Knowledge Base and repeat trace validation.

## How To Check A Run

The short version:

- local validation proves the repo shape,
- E2E reports prove create-call-load-delete behavior,
- retrieve traces prove source selection,
- screenshots explain the experience but are not enough by themselves.
