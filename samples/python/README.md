# Python Helpers

This folder contains small helper scripts that make the REST payload and retrieve trace shapes easier to inspect.

The helpers are intentionally lightweight. They are not an SDK wrapper and they should not hide the REST contract.

## Scripts

| Script | Purpose |
| --- | --- |
| [build_payloads.py](build_payloads.py) | Generate representative MCP Server KS, Fabric Ontology KS, MCP-only KB, and combined KB payloads from reusable Python builders. |
| [inspect_retrieve_response.py](inspect_retrieve_response.py) | Print summarized `activity` and `references` from a saved retrieve response. |

## Generate Payloads

```bash
python samples/python/build_payloads.py
```

The generated payloads use safe placeholders. They do not contain live tenant values.

## Inspect Offline Responses

```bash
python samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/fabric-airline-ops-retrieve.sample.json
python samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json
```

## Validation

These helpers are included in the local validation gate:

```bash
bash scripts/validate-local.sh
```

If you change payload builders or offline response shapes, update the helpers and sample responses together.
