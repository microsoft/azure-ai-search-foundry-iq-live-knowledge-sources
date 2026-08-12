# Repository Lifecycle Hardening Audit

This maintainer record captures the repository-wide review completed on 2026-08-13. The review concentrated on deployment ownership, Fabric billing release, cleanup evidence, public logging boundaries, dependency maintenance, and the local validation contract. No customer or tenant identifiers are included.

## Baseline

The starting branch passed the complete local contract before modification:

- `python3 tools/validate.py --profile offline --format json`: pass.
- `bash scripts/validate-local.sh`: 15 of 15 gates passed.
- `python3 -m unittest discover -s tests`: 51 tests passed.
- `az bicep lint --file infra/main.bicep`: no diagnostics.
- `npm --prefix static-app audit --omit=dev --json`: no vulnerabilities.
- `git diff --check`: pass.

The current `2026-05-01-preview` Search API remains intentional. [Microsoft Learn's retrieve guidance](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve) documents that the preview is required for the repository's synthesized Knowledge Base response and MCP feature set.

## Findings

| Priority | Finding | Risk | Resolution |
| --- | --- | --- | --- |
| High | Full create mode accepted any same-named capacity returned by the Fabric API. | A greenfield run could silently adopt a capacity created by another environment, then preserve it during cleanup while reporting success. | Create mode now requires the same-environment summary or the direct `azd` path's exact tagged Bicep ARM output. BYO remains explicit. |
| High | Capacity ownership was written only after ARM readiness and Fabric API visibility. | A failure during resource-group creation, the capacity PUT, or either propagation window could leave residual infrastructure without a usable cleanup record. | Resource-group ownership is journaled immediately after group creation; ARM ID and capacity ownership are journaled immediately after the ARM PUT and before readiness polling. |
| High | Capacity ownership implied ownership of the whole resource group. | Cleanup could delete a pre-existing group or a group that later acquired unrelated resources. | Capacity and resource-group ownership are separate. Whole-group deletion requires both group ownership and an inventory containing no unrelated resources; otherwise only the exact capacity is deleted. |
| High | A missing or invalid environment lock fell back to configured ownership. | Fabric deletion could proceed without the required agreement between resolved configuration and the lock. | Any absent, invalid, or conflicting Fabric ownership record now preserves all Fabric assets, continues Azure cleanup, and returns partial. |
| Medium | A missing full-mode Fabric summary was treated as "nothing to delete." | Cleanup could return success without proving release of a billable capacity. | Missing or invalid ownership evidence now produces partial cleanup while Azure cleanup continues. |
| Medium | Configuration/lock disagreement preserved Fabric but still reported a passing cleanup. | Operators could close a run without assigning the uncertain residual for follow-up. | Ownership disagreement now remains non-destructive and produces an explicit partial result. |
| Medium | Provisioning printed the complete settings object. | Administrator UPNs and generated Fabric IDs could enter local or CI logs. | Administrator and runtime ID fields are masked in settings output. |
| Low | Dependabot covered Actions and npm but not root Python requirements. | Pinned Python dependencies required manual update discovery. | Weekly grouped pip updates now cover the repository root. |

## External Comparison

Only primary Microsoft and Azure repositories and Microsoft Learn documentation were used. The review borrowed lifecycle principles, not source text or implementation code.

| Source | Observed pattern | Decision here |
| --- | --- | --- |
| [Build 2026 LAB532](https://github.com/microsoft/Build26-LAB532-from-data-to-context-agent-ready-knowledge-with-foundry-iq) | Fabric capacity is deployed in the lab resource group, and lab teardown explicitly removes capacities to release regional quota. | Adopt explicit capacity-release evidence. Keep this repository's separate group because Fabric preprovisioning must complete before the main deployment consumes the capacity. |
| [Microsoft IQ Solution Accelerator](https://github.com/microsoft/microsoft-iq-solution-accelerator) | `predown` removes Fabric workspace assets before `azd down`; CI cleanup runs with `always()` and has a direct RG fallback. | Adopt ordered external-service cleanup and continuation into Azure cleanup. Do not add an unconditional RG fallback because this repository requires resolved configuration and lock agreement before Fabric deletion. |
| [Azure Verified Module for Fabric capacity](https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/fabric/capacity) | Capacity modules expose tags and return exact resource IDs and resource-group names. | Add environment, solution, and manager tags to the Python ARM creation path and retain exact ARM IDs in the ignored summary. |
| [Deploy Your AI Application In Production](https://github.com/microsoft/Deploy-Your-AI-Application-In-Production) | Orphan cleanup uses preview/detection filters and preserves resources outside the proven target set. | Adopt target inventory checks and preservation of unrelated resources. Do not add global orphan auto-deletion because age and naming are weaker evidence than this repository's ownership ledger. |
| [Azure Developer CLI hooks](https://learn.microsoft.com/azure/developer/azure-developer-cli/azd-extensibility) | `predown` and `postdown` can wrap resource removal. | Keep `liveks down` as the authoritative path. Direct `azd down` lacks the YAML-plus-lock ownership agreement required by this repository, so a destructive compatibility hook was not added. |

## Resulting Contract

For `full` create mode:

1. A same-named capacity is either proven by the same-environment journal or by the exact tagged Bicep output used by direct `azd`, otherwise it is rejected.
2. The capacity and resource group receive environment and solution tags when created by the Python preprovisioner, and group ownership is recorded before the capacity PUT.
3. The summary distinguishes `capacityCreated` from `capacityResourceGroupCreated`.
4. Cleanup deletes generated Fabric items before Azure resources.
5. The dedicated group is deleted only when it is owned and contains no unrelated resources.
6. The exact capacity must be absent after owned cleanup; owned dedicated groups must also be absent.
7. A pre-existing capacity group must remain present and receives an explicit preservation check.
8. Missing or conflicting evidence preserves uncertain assets and returns partial cleanup for manual follow-up.

For `byo-fabric`, capacity, workspace, and ontology preservation remains unchanged.

## Validation

The implementation must pass:

```bash
python3 tools/validate.py --profile offline --format json
bash scripts/validate-local.sh
python3 -m unittest discover -s tests -v
az bicep lint --file infra/main.bicep
git diff --check
```

Live resource creation was not required for this repository audit. The focused tests mock the ARM and Fabric boundaries and assert the destructive command targets exactly.

After implementation, all 15 local validation gates and 71 Python contract tests pass.
