# Overview

This accelerator focuses on two live, query-time Knowledge Source patterns for Azure AI Search and Foundry IQ:

- Fabric Ontology Knowledge Source
- MCP Server Knowledge Source

Both patterns are different from classic indexing-first retrieval. They allow a Knowledge Base to ground responses with live enterprise semantics or tool-backed remote data at retrieval time.

## Positioning

```text
Fabric Ontology KS
= governed business-semantic grounding from Microsoft Fabric

MCP Server KS
= tool-backed dynamic retrieval from a remote HTTPS MCP endpoint
```

## Why These Two Belong Together

Both are live/federated Knowledge Source patterns:

- They are invoked at query time.
- They require explicit source configuration and security design.
- They expose activity and references that should be inspected during validation.
- They can be reused by Foundry Agents, custom apps, and demo experiences through the same Knowledge Base.

