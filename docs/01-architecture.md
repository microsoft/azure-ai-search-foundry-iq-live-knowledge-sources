# Architecture

```mermaid
flowchart LR
  User["User question"]
  Agent["Foundry Agent or custom app"]
  KB["Foundry IQ Knowledge Base"]
  Fabric["Fabric Ontology KS\nEntities, definitions, relationships"]
  MCP["MCP Server KS\nRemote HTTPS tools"]
  Answer["Grounded answer\nreferences + activity"]

  User --> Agent --> KB
  KB --> Fabric
  KB --> MCP
  Fabric --> Answer
  MCP --> Answer
```

## Northbound MCP vs Southbound MCP

There are two useful MCP directions to distinguish:

```text
Northbound MCP:
  A Knowledge Base is exposed as an MCP server so MCP clients can call it.

Southbound MCP Server KS:
  A Knowledge Base calls an external MCP server as a Knowledge Source.
```

This repository focuses on the southbound MCP Server Knowledge Source pattern.

