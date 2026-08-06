# Langflow Benchmark Adaptation Record

This maintainer record documents why and how an external repository journey was adapted. It is not included in the GitHub Pages navigation and is not a claim that the external repository caused this project's adoption or quality.

## Selection Rationale

Benchmark cutoff: `2026-08-06`.

In the supplied candidate-ranking snapshot, `langflow-ai/langflow` had the highest `hot_score` at `757.4`, with `152,865` stars, a push age of `0` days at collection time, and `fit_score` `101`. These values indicate current attention and activity in that supplied snapshot. They do not establish that README structure, CI, or any other observed repository feature caused the popularity.

The ranking data was supplied for this task. It was not independently recomputed by this repository.

## Verifiable Scope

Research is limited to the supplied snapshots of:

- `langflow-ai/langflow/README.md`,
- the repository file listing,
- `.github/workflows/*`.

Studied observations:

- the README value proposition and section order,
- the Quickstart installation, execution, and success-check contract,
- API, JSON, and MCP as post-success extension surfaces,
- workflow separation used to guard installation, accessibility, and security regressions.

Explicitly not studied:

- visual builder internal state management,
- the agent-orchestration engine,
- concrete API server implementation,
- concrete MCP server implementation,
- Desktop packaging code.

Those core-code snapshots were not supplied. No conclusion about their architecture or quality is supported by this benchmark.

## Adaptation Rule

The adaptation unit is an abstract journey pattern:

```text
user problem -> first success -> evidence -> extension -> quality gate
```

External wording, badge collections, screen composition, source code, and assets are not copied. The pattern is reimplemented around this repository's own Azure AI Search, Foundry IQ, Fabric Ontology, LiveKS, REST, and MCP contracts.

## Discovery-To-First-Success Card

Repository: `microsoft/azure-ai-search-foundry-iq-live-knowledge-sources`.

| Journey element | Internal contract |
| --- | --- |
| 10-second understanding | Platform teams connect a governed Fabric Ontology or remote HTTPS MCP tool, submit a natural-language question to a Foundry IQ Knowledge Base, and receive a grounded result with source evidence that can also be consumed through MCP. |
| One first success | The representative managed-organization path is `byo-fabric`; it runs one Fabric Ontology KS question before combined routing. |
| Immediate execution evidence | `./liveks verify` must return live `fabricOntology` activity or references. A final answer alone is insufficient. |
| Extension path | After source proof: native Knowledge Base MCP, `mcp-only`, combined routing, offline replay, REST, notebooks, and `full`. |
| Trust path | Configuration, security, preview limitations, troubleshooting, ownership-aware cleanup, and official Microsoft Learn links are separate evidence-backed sections. |
| Optional interest signal | Repository/demo links remain after the product sentence; no star CTA appears before the first result contract. |

Acceptance for the card:

- the opening sentence contains the user, input, and result,
- one representative live path is named,
- live success is tied to a source trace,
- compatibility and security statements link to tests, generated artifacts, workflow gates, or official manuals,
- no performance claim is made without a benchmark artifact.

## Traceability Matrix

| Change proposal | External observation path or heading | Why it applies here | Independent implementation scope | Verification | License handling |
| --- | --- | --- | --- | --- | --- |
| Make user, input, and result legible in one sentence. | Supplied `README.md` opening value proposition. | Managed-organization reviewers need to identify the operator, business question, and grounded output immediately. | New project-specific sentence in `README.md` and `docs/index.md`. | Maintainer review against the journey-card acceptance bullets. | Abstract pattern only; no external wording copied. |
| Order the manual by components, one live run, evidence, MCP extension, then limits. | Supplied `README.md` progression from value proposition and highlight features into the easiest entry point, Quickstart, advanced setup, Security, Deployment, and Contribute. | The repository previously exposed all modes before establishing one auditable live scenario. | Reorganized internal content around BYO Fabric and existing LiveKS commands. | `mkdocs build --strict`; link check; manual sequence review. | Information architecture only; no copied layout, badges, or assets. |
| Keep exactly one representative first live path. | Supplied `README.md` easiest-entry and Quickstart sequence. | `byo-fabric` best matches an organization that already governs Fabric assets. | Existing profile and YAML contract; no external implementation. | `doctor`, `plan`, `up`, and source-specific `verify`. | No external code or text used. |
| Put evidence immediately after execution. | Supplied Quickstart install/run/success-check contract. | A deployment message or fluent answer cannot prove Knowledge Source routing. | Existing REST trace plus explicit `fabricOntology` pass criteria. | `./liveks verify --env <env> --format json`; `tests/test_liveks_config.py`. | No external artifact included. |
| Add MCP as a post-proof client surface. | Supplied README API/JSON/MCP extension references. | Managed agent clients need the Knowledge Base's northbound MCP surface after source execution is proven. | New `./liveks mcp` command using Azure AI Search's documented JSON-RPC endpoint. | `tests/test_mcp_invocation.py`; live `tools/list`, `tools/call`, and known-fact check; ignored sanitized report. | Independently implemented from the Microsoft protocol contract; no Langflow code used. |
| Make success and failure reproducible without raw data. | Supplied Quickstart success contract and workflow-oriented regression posture. | Public evidence must not expose organizational content, endpoints, IDs, keys, or tokens. | Count-only MCP report and normalized failure categories. | Unit tests inject secret-like strings and assert they are absent from persisted reports; no-secret scan. | No external text or fixture copied. |
| Keep trust and limitations separate from feature claims. | Supplied `README.md` Security, Deployment, and Contribute sections. | Preview status, delegated authorization, admin-key tradeoffs, and cleanup ownership need explicit boundaries. | Links to repository security, configuration, preview, troubleshooting, and Microsoft Learn pages. | Markdown link check; repository security scan; maintainer review. | Section-role pattern only. |
| Preserve installation and platform regression gates. | Supplied `.github/workflows/*` snapshot. | The CLI and manual must remain runnable on the supported Python, Node, Linux, and Windows baselines. | Existing Ubuntu local gate, Windows launcher job, Pages build, and secret/size checks; MCP tests join the Python suite. | `.github/workflows/validate.yml`; `bash scripts/validate-local.sh`; Pages workflow. | Workflow concepts only; no external YAML copied. |
| Keep optional calls to action after result evidence. | Supplied `README.md` `Stay up-to-date` placement. | Interest signals must not displace the functional contract. | Documentation and demo links remain secondary; no leading star request. | Visual review of README and Pages first viewport. | Placement principle only. |

## Internal Change Set

| Internal file | Responsibility |
| --- | --- |
| `README.md` | Repository discovery journey and concise live acceptance path. |
| `docs/index.md` | Manual landing sequence in the proposed order. |
| `docs/runbook.md` | Configuration-first operational lifecycle. |
| `docs/22-knowledge-base-mcp.md` | Native MCP client, sanitized evidence, and failure reproduction. |
| `src/liveks/cli.py` | Read-only `mcp` command and verification integration. |
| `src/liveks/runtime.py` | JSON/SSE MCP transport parsing. |
| `tests/test_mcp_invocation.py` | Protocol parsing, count-only evidence, and raw-error redaction checks. |
| `.github/workflows/validate.yml` | Existing Linux and Windows quality gates that execute the test suite. |

## Completion Checks

```bash
python3 tools/validate.py --profile offline --format json
bash scripts/validate-local.sh
mkdocs build --strict --site-dir _site
git diff --check
```

Live acceptance uses an ignored `byo-fabric` environment:

```bash
./liveks verify --env <environment> --format json
./liveks mcp --env <environment> --query <domain-question> --expect-term <known-synthetic-fact>
./liveks mcp --env <environment> --omit-source-authorization --expect-failure
```

The live result is shareable only after reducing it to source type, pass/fail state, expected-term counts, and cleanup outcome.
