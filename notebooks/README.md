# Notebooks

The notebooks provide guided, reader-friendly walkthroughs for the two live Knowledge Source paths.

They are safe to open without live tenant values. Live calls are optional and should only be enabled after you configure local, ignored environment values.

## Notebook Map

| Notebook | Use when | What it covers |
| --- | --- | --- |
| [01-mcp-server-ks-quickstart.ipynb](01-mcp-server-ks-quickstart.ipynb) | You want the fastest guided path | Microsoft Learn MCP Server KS payloads, MCP-only KB payloads, optional live retrieve, and offline replay. |
| [02-fabric-ontology-ks-airline-ops.ipynb](02-fabric-ontology-ks-airline-ops.ipynb) | You want the Fabric ontology path | Airline Ops sample data, ontology contract, Fabric Ontology KS payloads, combined KB payloads, optional delegated retrieve, and offline replay. |

## Default Safety Behavior

The notebooks are designed around these defaults:

- build payloads locally,
- inspect sample data and ontology contracts,
- use offline replay by default,
- make live calls only when explicitly configured,
- keep tenant IDs, tokens, endpoints, and keys out of tracked files.

Use a local ignored env file for live testing:

```bash
export LIVE_KS_ENV_FILE=/path/to/.env.external.local
```

Do not commit that env file.

## Suggested Reader Path

1. Open [01-mcp-server-ks-quickstart.ipynb](01-mcp-server-ks-quickstart.ipynb).
2. Run the payload-building and offline replay cells.
3. Add live values only if you have a Search service and model deployment ready.
4. Open [02-fabric-ontology-ks-airline-ops.ipynb](02-fabric-ontology-ks-airline-ops.ipynb).
5. Review the Airline Ops data and ontology contract before enabling live Fabric calls.

## Related Files

- REST equivalents: [samples/rest](../samples/rest/README.md)
- Offline replay responses: [samples/responses](../samples/responses/README.md)
- Fabric prerequisites: [docs/fabric-ontology-prerequisites.md](../docs/fabric-ontology-prerequisites.md)
- Reviewer evidence: [docs/12-reviewer-evidence.md](../docs/12-reviewer-evidence.md)
