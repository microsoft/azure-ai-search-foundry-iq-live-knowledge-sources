# Visual Assets

This folder contains public-safe visuals used by the README, docs, private review notes, workshops, and blog drafts.

Tracked assets must not contain tenant IDs, resource names, service endpoints, tokens, keys, customer data, or screenshots from private deployments.

## Asset Catalog

| Asset | Use it for | Where it appears |
| --- | --- | --- |
| `deployment-modes.svg` | First-reader mode selection: `mcp-only`, `byo-fabric`, and `full`. | `README.md`, `docs/02-choose-a-pattern.md` |
| `current-demo-flow.svg` | Short demo walkthrough: choose a path, deploy, run retrieve, inspect trace evidence, and clean up. | `docs/16-demo-walkthrough.md` |
| `live-knowledge-sources-architecture.svg` | Architecture overview: Knowledge Base retrieval across MCP Server KS and Fabric Ontology KS. | `README.md`, `docs/01-architecture.md` |
| `architecture.mmd` | Mermaid source for the compact architecture sketch. | Reference source for quick edits |

## Promotion Rules

Keep screenshots and local captures under ignored `scratch/` until they pass review.

Promote a visual into `assets/` only when:

```text
[ ] It contains no tenant ID, token, key, private endpoint, resource group, or customer data
[ ] It uses fictional or sample data only
[ ] It supports a claim that is also backed by repo evidence or Learn documentation
[ ] It is readable without exposing raw service URLs
[ ] It has a clear caption or surrounding text
[ ] It can survive public preview wording changes
```

## Recommended Usage

Use this sequence for demos and blog drafts:

1. `current-demo-flow.svg`
2. `deployment-modes.svg`
3. `live-knowledge-sources-architecture.svg`
4. Sanitized app screenshots from ignored `scratch/`, only after review
5. Sanitized E2E summary or flow diagram, not raw deployment output

## Accessibility

SVG files should include:

- `role="img"`,
- `<title>`,
- `<desc>`,
- readable text labels,
- enough contrast for projection and screenshots.
