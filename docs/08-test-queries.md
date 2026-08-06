# Post-Deployment Tests And Expected Traces

Use this guide after `./liveks up` to prove that the deployed app can retrieve from the expected Knowledge Source. A successful deployment is not enough by itself: the answer, response mode, source activity, references, and source data must agree.

## Choose A Test Surface

| Surface | Use it for | What it proves |
| --- | --- | --- |
| Deployed demo app | First manual acceptance test and live presentation | A person can run the packaged query and inspect the same evidence shown to an audience. |
| `./liveks verify` | Repeatable deployment verification | The app and single-source retrieve paths return recognized live evidence. |
| REST samples | Request and response troubleshooting | The exact Knowledge Base retrieve payload and headers. |
| Notebooks | Guided experimentation | Payload construction, query changes, and deeper trace inspection. |

Start with the deployed app, then run `./liveks verify`. Use REST or notebooks only when you need to inspect or change the underlying request.

## Live Versus Replay

The app can show canonical offline responses when a live source is unavailable. Those responses are useful for learning the trace shape, but they do not prove that the deployed source was called.

| Screen signal | Meaning | Can it prove a live call? |
| --- | --- | --- |
| Answer badge is `live` | The managed API returned an Azure AI Search retrieve response. | Yes, when the expected source also appears in the trace. |
| Answer badge is `offline` or `offline-replay` | The app used a checked-in response fixture. | No. |
| Notice says `Canonical sample response` | GitHub Pages or API fallback supplied replay data. | No. |
| Source badge names a KS but response mode is offline | The fixture demonstrates the expected trace shape. | No. |

!!! warning "Do not validate by answer text alone"
    Offline replay intentionally returns a useful, realistic answer. Require a `live` badge and expected `activity` or `references` before claiming that a live Knowledge Source worked.

## Open The Deployed App

After deployment, read the generated local summary:

```text
deployments/<environment>/deployment-summary.md
```

1. Open the **App URL** from the summary.
2. Confirm that the top-right status pill says `<deployment-mode> live`.
3. Select **Deployment**.
4. Select **Re-check**.
5. In **Runtime Status**, confirm `reachabilityStatus` is `live`, `reachable` is `true`, and `deploymentMode` matches the profile you deployed.

The status check proves that the app can reach Azure AI Search. It does not by itself prove MCP or Fabric retrieval, so continue with the source tests below.

## Test 1: MCP Server KS

This test applies to all three live profiles.

### Run It In The App

1. Select **MCP Live** in the top navigation.
2. Select **Run retrieve**.
3. Wait for the button to change from **Running...** back to **Run retrieve**.
4. In **Answer**, require the `live` badge.
5. Require the **MCP Server KS** source badge.
6. Scroll to **Source Trace** and confirm the activity and reference counts are greater than zero.
7. Scroll to **Activity** and find `type: "mcpServer"` and `toolName: "microsoft_docs_search"`.
8. Scroll to **References** and **Source Data** and confirm Microsoft Learn evidence is present.

The app submits this query:

```text
What must be configured to create an Azure AI Search MCP Server knowledge source?
```

Expected answer content includes relevant setup guidance, such as a remote HTTPS MCP endpoint, allowed tools, output parsing, and Knowledge Base attachment. Wording can vary; the trace is the routing proof.

### Additional MCP Questions

Use the REST sample or notebook when you want to replace the packaged app query.

| Test query | Expected source | What to check |
| --- | --- | --- |
| How do I inspect activity, references, and sourceData from an Azure AI Search knowledge base retrieve response? | `microsoft-learn-mcp-ks` | `references[*].type == "mcpServer"` and source data is present. |
| How can I pass per-request credentials to an MCP Server knowledge source? | `microsoft-learn-mcp-ks` | The answer describes paired query-time control headers rather than storing per-user tokens. |

Good MCP activity contains this shape:

```json
{
  "type": "mcpServer",
  "knowledgeSourceName": "microsoft-learn-mcp-ks",
  "mcpServerArguments": {
    "toolName": "microsoft_docs_search"
  }
}
```

Automated equivalent:

```bash
./liveks verify --env <environment>
```

REST equivalent: `samples/rest/03-retrieve-mcp.http`.

## Test 2: Fabric Ontology KS

This test applies to `byo-fabric` and `full`. Those profiles create a Fabric-only Knowledge Base so source execution is deterministic before combined routing. In `mcp-only`, an offline response explaining that Fabric was not created is expected and is not a live Fabric pass.

The packaged app question targets the repo's Airline Ops ontology contract. `full` creates that sample. For `byo-fabric`, the Alpine Air answer is expected only when the connected ontology maps the same sample data and relationships. With another ontology, require live Fabric trace evidence and validate the answer against that ontology's known facts; use the REST sample or Fabric notebook to submit a domain-specific question.

### Acquire Delegated Source Authorization

Live Fabric retrieve needs a raw end-user token scoped to Azure AI Search:

```bash
az account get-access-token \
  --resource https://search.azure.com \
  --query accessToken \
  --output tsv
```

Run the command in a private terminal and copy only the token value. Do not add a `Bearer` prefix. The app keeps the value only in the current password field, includes it in Fabric and Combined requests, and does not persist it. Refreshing or closing the page clears the value.

### Run It In The App

1. Select **Fabric** in the top navigation.
2. Paste the raw token into **Fabric Source Authorization**.
3. Select **Run retrieve** under **Fabric Ontology**.
4. Wait for the button to return from **Running...** to **Run retrieve**.
5. In **Answer**, require the `live` badge. An `offline` answer does not pass this test even if it names Alpine Air.
6. Require the **Fabric Ontology KS** source badge.
7. For `full` or an Airline Ops BYO ontology, confirm the answer ranks Alpine Air first. For another BYO ontology, validate the answer against its own known facts.
8. In **Activity**, find `type: "fabricOntology"`.
9. In **References** or **Source Data**, find `fabricAnswer` and `fabricRawData`.

The app submits this query:

```text
Which airlines have the highest customer-care exposure this month?
```

### Additional Fabric Questions

| Test query | Expected result | What it validates |
| --- | --- | --- |
| Which routes have the most delayed flights over 15 minutes? | Delayed flights over 15 minutes total 10. | Route and Flight relationships are traversable. |
| Which delay categories are controllable and driving customer-care exposure? | Controllable categories and exposure evidence are returned. | DelayEvent category and exposure semantics are mapped. |
| Which passenger-care policies or regulation topics explain the risk for the highest-exposure airline? | Policy evidence is joined through category, trigger, and scope. | The answer uses ontology relationships rather than airline-name matching. |

Good Fabric evidence contains this shape:

```json
{
  "type": "fabricOntology",
  "sourceData": {
    "fabricAnswer": "<natural-language ontology answer>",
    "fabricRawData": "<CSV grounding data>"
  }
}
```

Automated equivalent:

```bash
./liveks verify --env <environment>
```

REST equivalent: `samples/rest/06-retrieve-fabric-ontology.http`.

## Test 3: Combined Knowledge Base

Run the MCP and Fabric single-source tests first. They prove each source independently; the combined Knowledge Base planner can select one or both sources for an individual question.

The packaged combined question also assumes Airline Ops semantics. For a non-Airline Ops BYO ontology, use the REST sample or notebook to replace the business half of the question before evaluating answer quality.

### Run It In The App

1. Complete the Fabric test and leave the token in the **Fabric Source Authorization** field.
2. Select **Combined Trace** in the top navigation.
3. Select **Run retrieve**.
4. Wait for the button to return from **Running...** to **Run retrieve**.
5. In **Answer**, require the `live` badge.
6. Read the answer and identify the business conclusion and any implementation guidance it returned.
7. Inspect the source badges and **Activity** to see whether the planner selected Fabric, MCP, or both.
8. Match each claim to its corresponding **References** and **Source Data** entry.

The app submits this query:

```text
Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the Knowledge Base retrieve response.
```

Expected interpretation:

- Fabric Ontology KS can provide the airline ranking and exposure evidence.
- MCP Server KS can provide Azure AI Search implementation guidance.
- One or both sources can appear because planner routing is dynamic.
- A two-source offline replay demonstrates the ideal trace shape, not a live two-source call.

Do not use source badges alone to claim that both live sources ran. Require `mode: "live"` and inspect the corresponding activity and references.

REST equivalent: `samples/rest/08-retrieve-combined-airline-ops.http`.

## Test 4: Native Knowledge Base MCP

Run this only after the applicable single-source test has passed. The retrieve trace proves which Knowledge Source ran; the native MCP call proves that an MCP-compatible client can consume the same Knowledge Base.

For the synthetic Airline Ops contract:

```bash
./liveks mcp \
  --env <environment> \
  --query "Which airlines have the highest customer-care exposure this month?" \
  --expect-term "Alpine Air"
```

Require `tools-list=pass`, `tools-call=pass`, and `grounding-content=pass`. For a non-Airline Ops BYO ontology, replace both the question and expected term with a non-sensitive known fact from that ontology. A protocol pass with `grounding-content=warn` is not source-content acceptance.

The current MCP result does not return separate `activity` and `references` arrays. Do not use this test by itself to claim that Fabric or MCP Server KS ran. Pair it with the matching source-specific retrieve test above.

See [Call the Knowledge Base Through MCP](22-knowledge-base-mcp.md) for authentication and normalized failure tests.

## What Each Result Lets You Claim

| Observed evidence | Supported claim |
| --- | --- |
| MCP test is live and identifies `microsoft_docs_search` | Azure AI Search called the Microsoft Learn MCP tool during retrieve. |
| Fabric test is live and returns Fabric source data | Azure AI Search grounded retrieval in the configured Fabric ontology with delegated source authorization. |
| Both single-source tests pass | Both live Knowledge Source paths are independently operational. |
| Combined test is live and its trace contains both source types | This retrieve call used both grounding paths. |
| Combined test is live and contains one source type | Planner routing worked, but this call does not prove that both sources ran. |
| Native MCP call matches a known fact after a source-specific retrieve pass | An MCP client consumed expected grounding content from the same operational Knowledge Base. |
| Any result is offline or offline-replay | Only the packaged response shape and inspection experience are demonstrated. |

## Pass/Fail Checklist

Treat a live acceptance test as passing only when all applicable checks are true:

- [ ] The app status is live and the deployment mode is correct.
- [ ] The Answer badge is `live`, not `offline` or `offline-replay`.
- [ ] The answer is useful for the submitted question.
- [ ] The expected source appears in `activity` or `references`.
- [ ] References are returned.
- [ ] Source data is returned for the evidence being discussed.
- [ ] Fabric tests use delegated source authorization.
- [ ] Combined routing is described from the observed trace rather than assumed.
- [ ] No token, tenant value, endpoint, or raw live response is copied into tracked files.

For the complete presenter sequence, use [Guided Live Demo Walkthrough](16-demo-walkthrough.md). For payload-level experimentation, use the [notebooks](samples/notebooks.md).
