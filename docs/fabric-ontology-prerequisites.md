# Fabric Ontology Prerequisites

This repo has two Fabric deployment postures. The validated `byo-fabric` path treats Fabric Ontology as a tenant-owned prerequisite. The `full` path creates a small greenfield Fabric sample stack: Fabric capacity, workspace, Lakehouse tables, ontology definition, ontology-backed GraphModel readiness, and the Azure AI Search Fabric Ontology Knowledge Source.

## What This Repo Provides

- Synthetic Airline Ops CSV files in `samples/data/airline-ops/`.
- A reader-facing ontology contract in `samples/ontology/airline-ops/ontology-contract.yaml`.
- Fabric Ontology KS REST samples that bind an existing Fabric workspace and ontology item to Azure AI Search.
- Offline retrieve responses that show the expected `activity`, `references`, and `sourceData` shapes.

## What You Bring

- A Microsoft Fabric workspace you can access.
- An ontology item that exposes equivalent Airline Ops entities and relationships.
- Permission to query the ontology as the signed-in user.
- An Azure AI Search service using the preview API version from `.env.sample`.
- An Azure OpenAI or Foundry model deployment for Knowledge Base answer synthesis.

## Capacity Posture

This public sample does not create Fabric capacity in the default validated path.

Use one of these paths:

| Path | Recommended use | Notes |
| --- | --- | --- |
| BYO Fabric Trial | Default for sample validation | Works well for an external tenant demo when a Fabric Trial capacity is already available. A 64 CU trial environment is more than enough for the Airline Ops sample. |
| BYO existing capacity | Customer or field tenant validation | Use when the tenant already has governed Fabric workspace/capacity ownership. |
| Automated F2 capacity | Full greenfield mode | `F2` is the smallest default sample capacity. Use a region where the subscription has Fabric quota. |

Keep `DEPLOYMENT_MODE=byo-fabric` and `FABRIC_CAPACITY_MODE=byo` for existing Fabric assets. Use `DEPLOYMENT_MODE=full` and `FABRIC_CAPACITY_MODE=create` for the greenfield path. If the selected Fabric region has quota `0`, switch `FABRIC_LOCATION` or use BYO Fabric.

## Greenfield Graph Readiness

Creating the ontology item is not enough for live retrieve. Fabric also creates an ontology-backed GraphModel. That graph must have a valid definition, finish graph loading, and become queryable before Azure AI Search Fabric Ontology KS can return `fabricOntology` activity.

The `full` path handles this explicitly:

1. Load the Airline Ops CSV files into Lakehouse Delta tables.
2. Create the Fabric ontology definition.
3. Find the ontology-backed GraphModel item.
4. Update the GraphModel definition with data sources, node/edge tables, graph types, and layout metadata.
5. Wait until a GraphModel probe query succeeds.
6. Create the Azure AI Search Fabric Ontology Knowledge Source and run retrieve.

If this step is skipped, direct Fabric MCP calls can list ontology entity types but `search_ontology` and Azure AI Search retrieve can fail with messages such as `GraphIsNotLoaded`, `GraphNotRefreshable`, or “The natural language query could not be processed.”

## Minimum Ontology Shape

Map equivalent entities to the sample contract:

| Entity | Source file | Key | Required relationships |
| --- | --- | --- | --- |
| Airline | `airlines.csv` | `airline_code` | Airline operates Flight |
| Airport | `airports.csv` | `airport_code` | Route origin and destination |
| Route | `routes.csv` | `route_id` | Flight uses Route |
| Flight | `flights.csv` | `flight_id` | Flight has DelayEvent |
| DelayEvent | `delay_events.csv` | `delay_event_id` | DelayEvent belongs to Flight |
| PassengerCarePolicy | `passenger_care_policies.csv` | `policy_id` | Join by `applicable_delay_category` and trigger condition |
| RegulatoryReference | `regulatory_references.csv` | `reference_id` | Optional search-index/semantic-join content |

The most important validation measures are:

- delayed flights over 15 minutes: `10`
- customer-care exposure: `15800`
- controllable delay events: `7`
- top customer-care exposure carrier: `Alpine Air`

## Semantic Join Design

Carrier names are fictional on purpose. This avoids implying risk or performance findings about real airlines in a Microsoft sample.

For regulation or passenger-care joins, use business keys and policy conditions instead of airline-name matching:

- `Airline.airline_code` for carrier identity inside the ontology.
- `DelayEvent.delay_category` for the operational cause.
- `PassengerCarePolicy.applicable_delay_category` for policy matching.
- `RegulatoryReference.applicable_delay_category` and `trigger_condition` for regulation-style references.
- `applicable_scope == all_carriers` or `applicable_airline_code == ALL` for carrier-neutral guidance.

This gives the demo a realistic semantic join path while keeping the public sample brand-neutral.

## Recommended BYO Setup Flow

1. Load the CSV files into your Fabric workspace using your preferred Fabric-supported data path.
2. Create or map ontology entities that match `ontology-contract.yaml`.
3. Create relationships between Airline, Airport, Route, Flight, and DelayEvent.
4. Add business-friendly synonyms such as carrier, route, delayed flight, controllable delay, and customer-care exposure.
5. Validate natural-language questions inside Fabric before connecting Azure AI Search.
6. Copy the Fabric workspace ID and ontology item ID into `samples/rest/04-create-fabric-ontology-ks.http`.
7. Create the Fabric Ontology Knowledge Source.
8. Retrieve with a raw end-user Search access token in `x-ms-query-source-authorization`.

## Validation Questions

Use these questions after the ontology is mapped:

| Question | Expected check |
| --- | --- |
| Which airlines have the highest customer-care exposure this month? | Alpine Air is first; total exposure is 15800 USD. |
| Which routes have the most delayed flights over 15 minutes? | The answer joins Route and Flight. |
| Which delay categories are controllable and driving customer-care exposure? | Crew availability, maintenance, and late aircraft appear as controllable drivers. |
| Which passenger-care policies or regulation topics explain the risk for the highest-exposure airline? | The answer joins through delay category and trigger condition, not real airline names. |
| List delayed flights from the transcontinental market and explain the related route and airline. | The answer joins Flight, Route, Airline, and DelayEvent. |

## Boundary

Do not wire Fabric's ontology endpoint through the generic MCP Server Knowledge Source path for this sample. Fabric Ontology KS is the native path for this scenario. MCP Server KS remains the pattern for remote HTTPS MCP servers such as Microsoft Learn MCP or custom operational tools.
