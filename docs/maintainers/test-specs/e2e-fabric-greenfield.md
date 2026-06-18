# Fabric Greenfield Full-Run Test Specification

This test validates only the Microsoft Fabric side of the full deployment before it is connected to Azure AI Search.

## Purpose

Prove that the repo can create or reuse a Fabric capacity, create a workspace, create a Lakehouse, upload the Airline Ops CSV files, load Delta tables, create an ontology definition, validate the ontology-backed GraphModel is queryable, and clean up generated Fabric assets.

## Inputs

Use an ignored local env file, such as `.env.external.local`:

```bash
EXTERNAL_TENANT_ID=<tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext
FABRIC_LOCATION=<fabric-region-with-quota>
```

For a quota-safe smoke test that reuses an existing capacity:

```bash
FABRIC_CAPACITY_MODE=byo
FABRIC_CAPACITY_NAME=<existing-capacity-display-name>
```

For a greenfield capacity test:

```bash
FABRIC_CAPACITY_MODE=create
FABRIC_CAPACITY_SKU=F2
FABRIC_CAPACITY_ADMIN=<admin-upn>
```

## Commands

Reuse an existing capacity:

```bash
bash scripts/fabric-e2e-test.sh \
  --env-file .env.external.local \
  --env-name ext-liveks-fabric-e2e \
  --fabric-location westus3 \
  --capacity-mode byo \
  --capacity-name <existing-capacity-name> \
  --cleanup
```

Create a new F2 capacity:

```bash
bash scripts/fabric-e2e-test.sh \
  --env-file .env.external.local \
  --env-name ext-liveks-fabric-e2e \
  --fabric-location westus3 \
  --capacity-mode create \
  --cleanup
```

## Required Checks

| Check | Expected |
| --- | --- |
| External tenant login | PASS |
| Required tools | PASS |
| azd environment prepared | PASS |
| Fabric provisioner completes | PASS |
| Fabric summary generated | PASS |
| Capacity, workspace, lakehouse, ontology IDs present | PASS |
| Airline Ops tables loaded | PASS |
| Ontology definition readable | PASS |
| Ontology-backed GraphModel queryable | PASS |
| Cleanup completes | PASS when `--cleanup` is used |

## Pass Criteria

The run passes when `deployments/<env>/fabric-test-report.md` shows all checks passing, and `deployments/<env>/fabric-summary.json` shows:

- `workspaceCreated == true`
- `lakehouseCreated == true`
- `ontologyCreated == true`
- all Airline Ops tables loaded
- `ontologyValidation.status == "ok"`
- `graphValidation.status == "ok"`
- `graphValidation.probe.rowCount > 0`

Generated reports are ignored by git and must not contain tokens or credentials.
