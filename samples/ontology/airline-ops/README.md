# Airline Ops Ontology Contract

This folder contains the reader-facing ontology contract for the Fabric Ontology Knowledge Source tutorial.

| File | Purpose |
| --- | --- |
| [ontology-contract.yaml](ontology-contract.yaml) | Entity, relationship, measure, synonym, and validation-question contract for the Airline Ops sample. |

## How To Use It

Use the contract when creating or mapping a Fabric ontology in your own tenant:

1. Load the CSV files from [samples/data/airline-ops](../../data/airline-ops/README.md).
2. Create equivalent entities, fields, and relationships in Fabric.
3. Add business-friendly synonyms for airline, carrier, route, delayed flight, controllable delay, and customer-care exposure.
4. Validate the expected counts and questions before creating the Azure AI Search Fabric Ontology Knowledge Source.

## Expected Validation Signals

| Signal | Expected value |
| --- | ---: |
| Airlines | 5 |
| Airports | 8 |
| Routes | 8 |
| Flights | 15 |
| Delayed flights over 15 minutes | 10 |
| Delay events | 10 |
| Customer-care exposure | 15800 USD |

The top customer-care exposure carrier is `Alpine Air`, a fictional carrier name.

## Boundary

This contract describes the ontology shape expected by the sample. It is not a production ontology and does not represent real airline performance, risk, or compliance findings.

For setup details, see [Fabric Ontology Prerequisites](../../../docs/fabric-ontology-prerequisites.md).
