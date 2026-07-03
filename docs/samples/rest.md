# REST Requests

The REST samples show the raw Azure AI Search request order for Knowledge Sources, Knowledge Bases, retrieve calls, and cleanup.

Start with these files:

```text
samples/rest/01-create-mcp-server-ks.http
samples/rest/02-create-mcp-only-kb.http
samples/rest/03-retrieve-mcp.http
samples/rest/04-create-fabric-ontology-ks.http
samples/rest/05-create-combined-kb.http
samples/rest/06-retrieve-fabric-ontology.http
samples/rest/08-retrieve-combined-airline-ops.http
samples/rest/07-delete-resources.http
```

Use the REST path when you want exact request shapes without the deployment wrapper. Keep live endpoints, API keys, and query-time authorization headers in local tooling only.

Next: use [Test Queries](../08-test-queries.md) to pick validation prompts and expected trace signals.
