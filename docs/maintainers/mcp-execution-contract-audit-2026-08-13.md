# MCP Execution Contract Audit

This maintainer record documents the 2026-08-13 review that aligned the MCP guide around one payload-to-live-evidence contract. It is excluded from the GitHub Pages build by `mkdocs.yml`.

## Decision

| Candidate | Decision | Evidence |
| --- | --- | --- |
| `docs/03-mcp-server-ks.md` | Reorder and connect existing commands. | The guide documented payload-level REST, LiveKS deployment, retrieve evidence, native MCP, and cleanup, but did not connect `samples/python/build_payloads.py` or the local and resolved payload checks to that acceptance path. |
| `samples/python/build_payloads.py` | No change. | The script executes successfully, emits parseable placeholder-only JSON, and its MCP KS and MCP-only KB members match the corresponding REST bodies after placeholder substitution. |
| Factories, profiles, and deployment code | No change. | MCP names, endpoint, tool, source reference, output parsing, inclusion mode, and token limit agree across the generator, `src/ks_factory`, `profiles/mcp-only.yaml`, REST samples, and postprovision path. |
| CI and deployment workflows | No change. | Existing gates already compile and execute the generator, test factory shape, dry-run resolved payloads in `plan`, and separate validation from Pages and Azure deployment. |

No new command, configuration field, payload property, cloud resource, authentication path, workflow permission, or telemetry mechanism was introduced.

## Source Contract

The following sources were read in full or through the complete relevant implementation block:

| Area | Source | Verified contract |
| --- | --- | --- |
| User guide | `docs/03-mcp-server-ks.md` | Existing local replay, deployment lifecycle, retrieve evidence, native MCP checks, REST requests, authentication guidance, and cleanup. |
| Representative generator | `samples/python/build_payloads.py` | Prints five top-level payload members. `mcp` and `mcpOnlyKnowledgeBase` are the members used by this path. No environment, credential store, network, or cloud API is read. |
| Payload builders | `src/ks_factory/__init__.py`, `mcp_server.py`, `knowledge_base.py`, `fabric_ontology.py` | MCP KS and Knowledge Base request shapes are plain dictionaries with explicit model, source, parsing, and tool fields. |
| REST contract | `samples/rest/01-create-mcp-server-ks.http`, `02-create-mcp-only-kb.http`, `03-retrieve-mcp.http` | Create KS, create MCP-only KB, and retrieve order; `includeActivity`, references, source data, low reasoning effort, and 60-second runtime. |
| Executable defaults | `profiles/mcp-only.yaml`, `config/schema.yaml` | `microsoft-learn-mcp-ks`, `live-knowledge-sources-mcp-kb`, Microsoft Learn MCP, `microsoft_docs_search`, API `2026-05-01-preview`, and the required tool/resource set. |
| Resolved deployment | `src/liveks/cli.py`, `scripts/postprovision.py` | `plan` runs Bicep, `scripts/postprovision.py --dry-run`, npm install, and app build. `up` repeats plan, runs ARM preview, confirms, deploys, then verifies. |
| Live acceptance | `src/liveks/cli.py` | MCP-only verify requires live `mcpServer` activity or references and a native MCP known-content check for `Azure AI Search`. The explicit MCP command exposes `tools-list`, `tools-call`, and `grounding-content` checks. |
| Local validation | `scripts/validate-local.sh`, `tests/test_ks_factory.py` | The gate compiles and executes the generator, runs builder shape tests, inspects offline traces, checks secrets and repository hygiene, builds the app, and builds Bicep when Azure CLI is present. |
| Validate workflow | `.github/workflows/validate.yml`, `requirements-liveks.txt` | Pull requests and `main` run Python 3.11 and Node 22. The workflow installs pinned PyYAML, runs the local gate and whitespace check, and has only `contents: read`; no concurrency or deployment job is declared. |
| Pages workflow | `.github/workflows/pages.yml`, `requirements-docs.txt`, `static-app/package.json` | Docs changes run strict Material build plus `npm --prefix static-app run build`. Pages uses the `pages` concurrency group with cancellation disabled and deploys only non-PR public-repository builds. |
| Azure deployment | `azure.yaml`, `scripts/deploy_static_webapp_api.py`, `infra/main.bicep` | Azure Developer CLI provisions Bicep, runs postprovision, builds the single static-app package script, and deploys the Static Web Apps frontend and managed API. Validate does not invoke this deployment. |

## Structured Consistency Checks

The review parsed the generator output and REST JSON rather than comparing text.

| Check | Result |
| --- | --- |
| Generated `mcp` equals REST MCP KS body after substituting `knowledgeSourceName`. | Pass |
| Generated `mcpOnlyKnowledgeBase` equals REST MCP-only KB body after substituting placeholders. | Pass |
| MCP KS name equals the `mcp-only` profile default. | Pass |
| MCP-only KB name equals the `mcp-only` profile default. | Pass |
| MCP endpoint and tool name equal the profile defaults. | Pass |
| MCP-only KB references exactly the generated MCP KS name. | Pass |

Descriptions and retrieval instructions in the live postprovision path are deployment-specific wording, while the API fields and routing contract are equivalent. This does not justify changing the representative generator.

## External Learning-Path Comparison

The primary read-only comparison was `microsoft/iq-series` at commit `76aa0c0485a974741c3fa1d0e789029b645a6be8` from 2026-08-03. At inspection time GitHub reported 344 stars, 248 forks, Jupyter Notebook as the primary language, and an MIT license.

Observed transferable structure:

- the root README orders Foundry IQ episodes from concepts, to Knowledge Sources, to multi-source Knowledge Base querying;
- each episode moves from summary to a hands-on cookbook and then an explicit next step;
- cookbook pages place prerequisites and deployment before a numbered lab sequence;
- MCP client material follows Knowledge Base creation rather than replacing source-execution proof.

Only that learning-order pattern was used. The external `.env` convention, package versions, deployment button, API versions, notebook code, wording, images, and MCP client configurations were not copied. No third-party material was incorporated, so no additional license notice is required.

The other supplied repositories were checked only as discovery candidates. Their broader RAG, UI, or agentic-retrieval scope did not provide a closer contract than the Microsoft IQ Series plus this repository's own source and official Microsoft Learn manuals.

## Traffic Baseline

GitHub's traffic REST API was queried on 2026-08-13. The latest returned daily bucket was 2026-08-11 UTC.

| Signal | Verified value |
| --- | --- |
| Trailing API window | 185 views and 56 unique visitors across the 14 returned daily buckets. |
| Latest seven daily buckets | 141 views for 2026-08-05 through 2026-08-11, versus 44 for the preceding seven buckets, a difference of 97. Daily uniques are not summed into a custom-window unique count. |
| Clones | 1,525 clones and 92 unique cloners across the 14 returned daily buckets. The 2026-07-30 bucket contains 1,267 clones, so the total is not treated as adoption or successful execution. |
| MCP guide path | 7 views and 7 unique visitors in the popular-path snapshot. |
| Payload generator path | 4 views and 1 unique visitor in the popular-path snapshot. |
| Validate | The latest organization `main` run at `efa45fcb17cc018b8e59f85bafbf2d376ec6df92` completed successfully. |

The supplied feedback labeled 185 as a seven-day view count, 34 as today's views, and the week-over-week change as 134. The official endpoint returns a trailing 14-day payload, its latest bucket was two UTC days behind the review date, and the two seven-bucket sums differ by 97. The supplied labels are therefore not used as public claims.

## Evidence Boundary

The revised guide intentionally separates these claims:

1. `build_payloads.py` proves representative JSON generation only.
2. `scripts/validate-local.sh` proves repository-local builder and packaging consistency.
3. `liveks plan` proves selected settings reach the resolved postprovision dry-run without cloud mutation.
4. `liveks verify` proves a live retrieve returned source activity or references.
5. `liveks mcp --expect-term` proves native MCP protocol execution and expected non-sensitive grounding content.
6. `liveks down` proves generated Azure resources are absent.

Clone, view, star, and path traffic cannot prove any of these execution stages. No telemetry is added by this documentation change.

## Validation Contract

A local `mcp-contract-audit` environment was initialized for this review and removed after validation. `doctor` passed authentication, tool, version, provider-registration, and OpenAI region checks; it retained the expected warning that Search agentic preview availability is proven by deployment preview and live E2E. `plan` then passed `bicep-build`, `payload-dry-run`, `app-install`, and `app-build`. Neither `up` nor any other cloud-mutating command was run, and no cloud resource was created.

```bash
./liveks try --sample mcp --details
python3 samples/python/build_payloads.py
PATH="$PWD/.liveks/venv/bin:$PATH" bash scripts/validate-local.sh --no-color
python3 scripts/check-doc-links.py
mkdocs build --strict --site-dir _site
git diff --check
```

After rollout, the fork pull request and organization `main` must pass Validate and Pages. The deployed MCP guide must render the ordered contract and resolve its internal links under the project Pages base path.
