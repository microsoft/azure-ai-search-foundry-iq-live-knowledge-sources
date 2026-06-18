# Airline Operations Sample Data

This folder contains a small synthetic dataset for the Fabric Ontology Knowledge Source walkthrough.

The schema is inspired by public airline operations fields such as carrier, airport, route, flight, delay, cancellation, and disruption metrics. The rows are intentionally tiny and tutorial-focused. They are not copied from a customer system and should not be treated as official transportation statistics.

## Files

| File | Purpose |
| --- | --- |
| `airlines.csv` | Carrier dimension used for airline-level questions. |
| `airports.csv` | Airport dimension used for route and market questions. |
| `routes.csv` | Origin-destination routes used by flights. |
| `flights.csv` | Sample flight operations facts. |
| `delay_events.csv` | Delay attribution and customer-care exposure facts. |
| `passenger_care_policies.csv` | Small synthetic policy table keyed by carrier scope and delay category. |
| `regulatory_references.csv` | Synthetic regulation-style summaries for semantic join demos. |

## Expected Counts

Use these counts when validating your Fabric ontology or offline replay:

| Item | Expected count |
| --- | ---: |
| Airlines | 5 |
| Airports | 8 |
| Routes | 8 |
| Flights | 15 |
| Delayed flights over 15 minutes | 10 |
| Delay events | 10 |
| Passenger-care policies | 4 |
| Regulatory references | 4 |

## Why Carrier Names Are Fictional

The sample uses fictional carrier names and codes to avoid implying performance, risk, or compliance findings about real airlines. Public airport names remain real because they provide useful geography without ranking a private company.

For semantic join demos, do not rely on real airline names appearing in policy or regulation text. Join through stable business fields instead:

- `airline_code`
- `delay_category`
- `applicable_delay_category`
- `trigger_condition`
- `applicable_scope`

This keeps the sample safe for official publication while still demonstrating how operational facts can be joined with policy or regulation-style content.

## Intended Ontology Shape

Use `samples/ontology/airline-ops/ontology-contract.yaml` as the reader-facing contract. The repo does not create a Fabric ontology for you in Phase 1. Instead, it provides the data shape, relationships, measures, and validation questions that a Fabric workspace owner can map into an ontology in their own tenant.

## Public Data Option

If you want a larger dataset, replace these rows with a small subset from a public source such as U.S. DOT/BTS Airline On-Time Performance data or the Kaggle `usdot/flight-delays` dataset. Keep the checked-in sample small and remove any fields that are not needed for the tutorial.
