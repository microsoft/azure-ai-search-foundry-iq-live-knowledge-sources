#!/usr/bin/env python3
"""Build the "clone -> mock -> test -> deploy -> verify -> cleanup" guide video.

Produces one MP4 per chapter under video-guide/clips/ and a single merged final
MP4. Content uses outputs that were actually run against this repo (offline mock,
local validation gate, dry-run, generated deployment summary). Terminal text is
real command output / JSON / file content and is identical across languages; only
the captions, callouts and labels are localized.

The storyboard is bilingual. The same scene order and timing produce a Korean and
an English video; pick the language with --lang.

Usage:
    python3 build_guide_video.py                  # build everything (Korean)
    python3 build_guide_video.py --lang en        # build everything (English)
    python3 build_guide_video.py --only m2,m4     # build selected chapters
    python3 build_guide_video.py --no-final       # skip the merge step

Outputs:
    Korean : video-guide/clips/NN-*.mp4      + video-guide/repo-quickstart-guide.mp4
    English: video-guide/clips/en/NN-*.mp4   + video-guide/repo-quickstart-guide-en.mp4
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import engine as E
import scenes as S
from engine import (
    Ctx, Module, INK, DIM, FAINT, BLUE, GREEN, ORANGE, RED, YELLOW, WHITE, tr,
)

HERE = Path(__file__).resolve().parent
WORK_BASE = Path("/tmp/vg_work")

REPO_URL = "https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources.git"
REPO_DIR = "azure-ai-search-foundry-iq-live-knowledge-sources"
TOTAL = 7


def out_paths(lang: str):
    """Return (work_dir, clips_dir, final_mp4) for the given language."""
    if lang == "en":
        return (WORK_BASE / "en", HERE / "clips" / "en",
                HERE / "repo-quickstart-guide-en.mp4")
    return (WORK_BASE / "ko", HERE / "clips",
            HERE / "repo-quickstart-guide.mp4")


# ---------------------------------------------------------------------------
# Localized chapter labels (top-left chapter chip)
# ---------------------------------------------------------------------------

def lbl_intro():   return tr("소개 · Overview", "Overview")
def lbl_clone():   return tr("Clone & 폴더 구조", "Clone & Structure")
def lbl_local():   return tr("로컬 mock 실행", "Local Mock Run")
def lbl_test():    return tr("테스트 · 검증", "Tests & Validation")
def lbl_deploy():  return tr("배포 · Deploy", "Deploy")
def lbl_verify():  return tr("동작 확인 · Verify", "Verify")
def lbl_summary(): return tr("요약 · Summary", "Summary")


# ---------------------------------------------------------------------------
# JSON line colorizer (keys orange, strings green, punctuation dim)
# ---------------------------------------------------------------------------

def jl(s: str):
    segs = []
    buf = ""
    i, n = 0, len(s)

    def flush(col=INK):
        nonlocal buf
        if buf:
            segs.append((buf, col))
            buf = ""

    while i < n:
        c = s[i]
        if c == '"':
            j = i + 1
            while j < n and s[j] != '"':
                j += 1
            tok = s[i:j + 1]
            k = j + 1
            while k < n and s[k] == ' ':
                k += 1
            flush()
            segs.append((tok, ORANGE if (k < n and s[k] == ':') else GREEN))
            i = j + 1
            continue
        if c in '{}[]:,':
            flush()
            segs.append((c, DIM))
            i += 1
            continue
        buf += c
        i += 1
    flush()
    return segs


def lines(*rows):
    return [jl(r) if isinstance(r, str) else r for r in rows]


# ===========================================================================
# Chapter 1 — Intro
# ===========================================================================

def m1() -> Module:
    m = Module("01-intro")
    ctx = Ctx(1, TOTAL, lbl_intro())
    S.title_card(
        m, ctx, "Live Knowledge Sources",
        subtitle=tr("Azure AI Search · Foundry IQ — Clone → Deploy 가이드",
                    "Azure AI Search · Foundry IQ — Clone → Deploy guide"),
        bullets=[
            tr("MCP Server + Fabric Ontology를 하나의 Knowledge Base로 라우팅",
               "Route MCP Server + Fabric Ontology through one Knowledge Base"),
            tr("응답에서 activity · references · sourceData 추적을 직접 확인",
               "See activity · references · sourceData traces in the response"),
        ],
        code="clone → mock → test → deploy → verify → cleanup",
        big=True, hold=3.4,
    )
    ctx2 = Ctx(1, TOTAL, lbl_intro(),
               caption=tr("이 레포가 하는 일: 라이브 소스가 '무엇을 근거로' 답했는지 추적으로 증명합니다.",
                          "What this repo does: prove what a live source grounded its answer on — via the trace."))
    S.note_card(m, ctx2, tr("이 영상에서 다루는 6개 모듈", "The 6 modules in this guide"), [
        ("step", tr("Clone & 폴더 구조 — 무엇을 보고 어떤 값을 넣는지",
                    "Clone & structure — what to read and which values to set")),
        ("step", tr("로컬 mock 실행 — Azure 없이 30초 만에 trace 체험",
                    "Local mock run — see a trace in 30s, no Azure")),
        ("step", tr("테스트 — validate-local.sh 로 13개 항목 검증",
                    "Tests — validate 13 checks with validate-local.sh")),
        ("step", tr("배포 — deploy.sh (dry-run → 실제 → cleanup)",
                    "Deploy — deploy.sh (dry-run → real → cleanup)")),
        ("step", tr("동작 확인 — deployment-summary.md · 데모 앱 라우트",
                    "Verify — deployment-summary.md · demo app routes")),
        ("ok",   tr("10분이면 따라할 수 있게 핵심만 순서대로 보여줍니다",
                    "Just the essentials, in order — follow along in 10 minutes")),
    ], settle=3.6)
    ctx3 = Ctx(1, TOTAL, lbl_intro(),
               caption=tr("왜 이 레포인가 — 문서가 아니라 '실행 추적'을 직접 봅니다.",
                          "Why this repo — you watch the execution trace, not just docs."))
    S.note_card(m, ctx3, tr("이 레포를 쓰는 이유", "Why use this repo"), [
        ("info", tr("See the trace, not just docs — 어떤 소스·도구가 실행됐는지 응답에서 확인",
                    "See the trace, not just docs — which sources/tools ran, right in the response")),
        ("info", tr("Run in 30s with zero setup — 키·테넌트·Fabric 없이 오프라인 체험",
                    "Run in 30s with zero setup — offline, no keys/tenant/Fabric")),
        ("info", tr("Go live with one command — 준비되면 deploy.sh 로 라이브 전환",
                    "Go live with one command — flip to live with deploy.sh when ready")),
    ], settle=3.4)
    return m


# ===========================================================================
# Chapter 2 — Clone & folder structure
# ===========================================================================

def m2() -> Module:
    m = Module("02-clone")
    ctx = Ctx(2, TOTAL, lbl_clone(),
              caption=tr("GitHub에서 clone — 모든 것은 이 한 줄에서 시작합니다.",
                         "Clone from GitHub — everything starts with this one line."),
              caption_sub="git clone " + REPO_URL[:42] + "…")
    res = S.terminal_scene(
        m, ctx, "$ ", "git clone " + REPO_URL,
        lines(
            [("Cloning into '" + REPO_DIR + "'...", DIM)],
            [("remote: Enumerating objects: 100% (642/642), done.", DIM)],
            [("remote: Total 642 (delta 318), reused 540 (delta 196)", DIM)],
            [("Receiving objects: 100% (642/642), 3.21 MiB | 6.4 MiB/s, done.", DIM)],
            [("Resolving deltas: 100% (318/318), done.", DIM)],
        ),
        term_title="bash — git clone", settle=2.0,
        explains=[
            (tr("git clone 으로 레포 전체를 로컬에 복사 — 추가 설정은 필요 없습니다.",
                "git clone copies the whole repo locally — no extra setup needed."),
             tr("복제가 끝나면 cd 로 폴더에 들어갑니다.",
                "When it finishes, cd into the folder.")),
            (tr("이후 모든 명령은 이 레포 루트 폴더에서 실행합니다.",
                "Run every later command from this repo root."),
             "cd azure-ai-search-foundry-iq-live-knowledge-sources"),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 250, 1740, 322),
        tr("원본은 microsoft 조직 레포지토리 — 여기를 clone 합니다.",
           "The source is the microsoft org repo — clone from here."),
        sub="github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources",
        settle=2.6,
    )

    # cd + folder tree
    ctx_tree = Ctx(2, TOTAL, lbl_clone(),
                   caption=tr("폴더 구조 한눈에 — 어디에 무엇이 있는지부터 익힙니다.",
                              "Folder structure at a glance — learn where things live first."))
    S.tree_view(m, ctx_tree, "azure-ai-search-foundry-iq-live-knowledge-sources/", [
        {"indent": 0, "name": REPO_DIR, "kind": "root"},
        {"indent": 1, "name": "README.md", "kind": "emph",
         "comment": tr("시작 지점 · 무엇을/왜/30초 체험", "Start here · what/why/30s demo")},
        {"indent": 1, "name": ".env.sample", "kind": "emph",
         "comment": tr("배포 입력값 템플릿", "Deploy input template")},
        {"indent": 1, "name": "docs", "kind": "dir",
         "comment": tr("개념 · 배포 · 문제해결 · FAQ", "Concepts · deploy · troubleshooting · FAQ")},
        {"indent": 1, "name": "scripts", "kind": "dir",
         "comment": tr("deploy · destroy · validate 스크립트", "deploy · destroy · validate scripts")},
        {"indent": 1, "name": "infra", "kind": "dir",
         "comment": tr("Azure 리소스 Bicep", "Azure resources (Bicep)")},
        {"indent": 1, "name": "static-app", "kind": "dir",
         "comment": tr("데모 앱 (SWA + Functions)", "Demo app (SWA + Functions)")},
        {"indent": 1, "name": "samples", "kind": "dir",
         "comment": tr("오프라인 응답 · 페이로드 · 데이터", "Offline responses · payloads · data")},
        {"indent": 1, "name": "notebooks", "kind": "dir",
         "comment": tr("MCP · Fabric 튜토리얼", "MCP · Fabric tutorials")},
        {"indent": 1, "name": "src/ks_factory", "kind": "dir",
         "comment": tr("재사용 Python 빌더", "Reusable Python builders")},
    ], settle=2.8)

    # README one-liner
    ctx_rm = Ctx(2, TOTAL, lbl_clone(),
                 caption=tr("README.md — 이 레포가 하는 일을 한 줄로 요약해 둡니다.",
                            "README.md — it sums up what this repo does in one line."))
    res_rm = S.file_view(m, ctx_rm, "README.md", [
        ("# Live Knowledge Sources for Azure AI Search", WHITE),
        ("", INK),
        ("One Knowledge Base can route a query to live MCP tools and", INK),
        ("governed Fabric semantics, then return the trace contract:", INK),
        ('  activity, references, and sourceData.', GREEN),
        ("", INK),
        ("## Try It In 30 Seconds", BLUE),
        ("No Azure subscription, keys, tenant, or Fabric workspace required:", DIM),
        ("", INK),
        ("$ python3 samples/python/inspect_retrieve_response.py \\", INK),
        ("    samples/responses/mcp-retrieve.sample.json", INK),
    ], highlights={3, 4, 5, 10, 11}, start_no=14, settle=1.8, font_size=25, lh=33)
    S.zoom_callout(
        m, S.compose(Ctx(1, 1, ""), "README.md",
                     [[("trace contract:", INK)],
                      [("  activity, references, and sourceData", GREEN, True)]],
                     chrome=False, font_size=40, lh=70),
        (E.MARGIN, 240, 1500, 430),
        tr("핵심 한 줄: 응답이 activity · references · sourceData 를 돌려줍니다.",
           "The key line: the response returns activity · references · sourceData."),
        sub=tr("이 세 가지가 '무엇을 근거로 답했는가'를 증명하는 trace 계약입니다.",
               "These three are the trace contract proving what grounded the answer."),
        settle=2.8,
    )

    # .env.sample
    ctx_env = Ctx(2, TOTAL, lbl_clone(),
                  caption=tr(".env.sample — 배포에 넣을 값들의 템플릿. 복사해서 채웁니다.",
                             ".env.sample — a template of deploy values. Copy it and fill in."))
    res_env = S.file_view(m, ctx_env, ".env.sample", [
        ("# Choose: byo-fabric | mcp-only | full", DIM),
        ("DEPLOYMENT_MODE=byo-fabric", INK),
        ("", INK),
        ("# Azure AI Search", DIM),
        ("SEARCH_ENDPOINT=https://<search-service>.search.windows.net", INK),
        ("SEARCH_API_VERSION=2026-05-01-preview", INK),
        ("", INK),
        ("# MCP Server Knowledge Source", DIM),
        ("MCP_SERVER_URL=https://learn.microsoft.com/api/mcp", INK),
        ("MCP_TOOL_NAME=microsoft_docs_search", INK),
        ("", INK),
        (tr("# Fabric Ontology (byo-fabric / full 에서 필요)",
            "# Fabric Ontology (needed for byo-fabric / full)"), DIM),
        ("FABRIC_WORKSPACE_ID=00000000-0000-0000-0000-000000000000", INK),
        ("FABRIC_ONTOLOGY_ID=00000000-0000-0000-0000-000000000001", INK),
    ], highlights={2, 5, 13, 14}, start_no=1, settle=1.6, font_size=24, lh=31)
    S.zoom_callout(
        m, S.compose(Ctx(1, 1, ""), ".env.sample",
                     lines("DEPLOYMENT_MODE=byo-fabric",
                           "SEARCH_ENDPOINT=https://<search-service>.search.windows.net",
                           "FABRIC_WORKSPACE_ID=00000000-0000-0000-0000-000000000000",
                           "FABRIC_ONTOLOGY_ID=00000000-0000-0000-0000-000000000001"),
                     chrome=False, font_size=30, lh=58),
        (E.MARGIN, 250, 1700, 520),
        tr("DEPLOYMENT_MODE 와 Fabric ID 가 핵심 입력값입니다.",
           "DEPLOYMENT_MODE and the Fabric IDs are the key inputs."),
        sub=tr("mcp-only 는 Fabric 값이 필요 없습니다 — 가장 빠른 시작 경로.",
               "mcp-only needs no Fabric values — the fastest path to start."),
        settle=2.8,
    )

    # key files to read
    ctx_kf = Ctx(2, TOTAL, lbl_clone(),
                 caption=tr("처음 열어볼 파일은 이 다섯 개면 충분합니다.",
                            "These five files are all you need to open first."))
    S.note_card(m, ctx_kf, tr("꼭 봐야 할 파일", "Files you must read"), [
        ("info", tr("README.md — 무엇을 · 왜 · 30초 체험 · 배포 모드 표",
                    "README.md — what · why · 30s demo · deploy mode table")),
        ("info", tr("docs/10-one-command-deployment.md — 배포 전 과정",
                    "docs/10-one-command-deployment.md — the full deploy walkthrough")),
        ("info", tr(".env.sample — 배포에 넣을 값(모드·엔드포인트·Fabric ID)",
                    ".env.sample — deploy values (mode · endpoint · Fabric IDs)")),
        ("info", tr("scripts/deploy.sh · destroy.sh — 배포 · 정리 진입점",
                    "scripts/deploy.sh · destroy.sh — deploy · cleanup entry points")),
        ("info", tr("scripts/validate-local.sh — 클라우드 없이 로컬 검증",
                    "scripts/validate-local.sh — local validation, no cloud")),
    ], settle=2.6)
    return m


# ===========================================================================
# Chapter 3 — Local mock run
# ===========================================================================

def m3() -> Module:
    m = Module("03-local")
    ctx0 = Ctx(3, TOTAL, lbl_local(),
               caption=tr("설치가 필요할까? — python3 하나면 됩니다. 추가 의존성 없음.",
                          "Need to install anything? — just python3. No extra dependencies."))
    res0 = S.terminal_scene(
        m, ctx0, "$ ", "python3 --version",
        lines([("Python 3.11.9", GREEN)]),
        term_title="bash — live-knowledge-sources", settle=1.6,
        explains=[
            (tr("로컬 mock 은 pip install 도, 가상환경도 필요 없습니다 — python3 만 있으면 OK.",
                "The local mock needs no pip install and no virtualenv — just python3."),
             tr("Python 3.9 이상이면 그대로 진행합니다.",
                "Python 3.9+ and you're good to go.")),
        ],
    )

    # MCP mock
    ctx1 = Ctx(3, TOTAL, lbl_local(),
               caption=tr("mock 모드: 저장된 오프라인 응답을 그대로 검사합니다.",
                          "Mock mode: inspect a saved offline response as-is."),
               caption_sub="inspect_retrieve_response.py  ·  mcp-retrieve.sample.json")
    res1 = S.terminal_scene(
        m, ctx1, "$ ",
        "python3 samples/python/inspect_retrieve_response.py samples/responses/mcp-retrieve.sample.json",
        lines(
            [("Activity", BLUE, True)],
            "[",
            '  { "type": "mcpServer",',
            '    "knowledgeSourceName": "microsoft-learn-mcp-ks",',
            '    "toolName": "microsoft_docs_search" }',
            "]",
            [("References", BLUE, True)],
            '  { "title": "Create an MCP Server knowledge source",',
            '    "hasSourceData": true,',
            '    "sourceDataKeys": ["content", "title"] }',
            [("Source Data Preview", BLUE, True)],
            '  "content": "Synthetic sample content. Replace with a real…"',
        ),
        font_size=24, lh=34, settle=2.0,
        explains=[
            (tr("Activity[] = 이 질의에서 '실제로 실행된' 소스/도구 목록입니다.",
                "Activity[] = the sources/tools that actually ran for this query."),
             tr("여기선 mcpServer 가 microsoft_docs_search 도구를 호출했습니다.",
                "Here the mcpServer called the microsoft_docs_search tool.")),
            (tr("References[] = 답의 근거가 된 항목 — 제목과 sourceData 키를 가집니다.",
                "References[] = the items that grounded the answer — title + sourceData keys."),
             tr("Source Data Preview = 그 근거의 실제 내용 미리보기.",
                "Source Data Preview = a peek at that grounding content.")),
        ],
    )
    S.zoom_term(
        m, res1, (E.MARGIN, 470, 1500, 640),
        tr("references[] — 어떤 근거가 돌아왔는지와 sourceData 키를 보여줍니다.",
           "references[] — shows what grounding came back and its sourceData keys."),
        sub='hasSourceData: true   sourceDataKeys: ["content","title"]',
        settle=2.8, font_size=24, lh=34,
    )

    # Combined mock
    ctx2 = Ctx(3, TOTAL, lbl_local(),
               caption=tr("combined 샘플: Fabric(업무 데이터) + MCP(문서)를 한 번에.",
                          "Combined sample: Fabric (business data) + MCP (docs) in one call."))
    res2 = S.terminal_scene(
        m, ctx2, "$ ",
        "python3 samples/python/inspect_retrieve_response.py samples/responses/combined-airline-ops-retrieve.sample.json",
        lines(
            [("Activity", BLUE, True)],
            '  { "type": "fabricOntology",',
            '    "knowledgeSourceName": "fabric-ontology-ks", "count": 5 }',
            '  { "type": "mcpServer",',
            '    "toolName": "microsoft_docs_search", "count": 2 }',
            [("Source Data Preview", BLUE, True)],
            '  "fabricAnswer": "The ontology ranks Alpine Air first by',
            '   customer-care exposure in the sample period…"',
            '  "fabricRawData": "airline_code,airline_name,exposure_usd',
            '   ALP,Alpine Air,6800 …"',
        ),
        font_size=24, lh=34, settle=2.0,
        explains=[
            (tr("한 번의 질의가 Fabric(업무 데이터)과 MCP(문서) 둘 다로 라우팅됩니다.",
                "One query routes to both Fabric (business data) and MCP (docs)."),
             tr("activity 에 fabricOntology · mcpServer 가 함께 보입니다.",
                "activity shows fabricOntology · mcpServer together.")),
            (tr("fabricAnswer/fabricRawData = 업무 데이터 근거, MCP = 문서 근거.",
                "fabricAnswer/fabricRawData = business-data grounding, MCP = docs grounding."),
             tr("이것이 '하나의 KB가 라이브로 통합'한다는 의미입니다.",
                "This is what 'one KB unifies live sources' means.")),
        ],
    )
    S.zoom_term(
        m, res2, (E.MARGIN, 250, 1560, 470),
        tr("activity[] 에 두 소스가 모두 — 하나의 KB가 라이브로 라우팅한 증거.",
           "Both sources in activity[] — proof one KB routed live."),
        sub="type: fabricOntology  +  type: mcpServer",
        settle=2.8, font_size=24, lh=34,
    )

    # notebooks (.ipynb) — what you can actually do, and how the 3 modes differ
    ctx_nb = Ctx(3, TOTAL, lbl_local(),
                 caption=tr("같은 계약을 노트북으로 직접 실행 — 페이로드 생성부터 retrieve 까지.",
                            "Run the same contract yourself in notebooks — from payloads to retrieve."),
                 caption_sub="notebooks/01-mcp-server-ks-quickstart.ipynb · 02-fabric-ontology-ks-airline-ops.ipynb")
    S.kv_card(m, ctx_nb, tr("노트북(.ipynb)으로 직접 해보기", "Do it yourself in the notebooks (.ipynb)"), [
        ("01 · mcp-only", tr("MCP KS·KB 생성 → retrieve → trace", "build MCP KS·KB → retrieve → trace"),
         tr("Microsoft Learn MCP 라이브 루프 검증", "validate the live Microsoft Learn MCP loop")),
        ("02 · byo-fabric/full", tr("Fabric Ontology KS + combined KB", "Fabric Ontology KS + combined KB"),
         tr("Airline Ops 샘플·온톨로지 기반", "built on the Airline Ops sample ontology")),
    ], note=tr("기본은 dry-run(offline) — RUN_LIVE_CALLS=true 와 키를 넣으면 실제 Azure 호출.",
               "Default is dry-run (offline) — set RUN_LIVE_CALLS=true + keys for real Azure calls."),
       settle=2.8)

    ctx_modes = Ctx(3, TOTAL, lbl_local(),
                    caption=tr("세 모드의 차이 = retrieve 때 '어떤 라이브 소스가 답하나' 입니다.",
                               "The 3 modes differ in which live source answers at retrieve time."))
    S.note_card(m, ctx_modes, tr("세 모드는 retrieve 때 무엇이 다른가", "What differs at retrieve across the 3 modes"), [
        ("info", tr("mcp-only — MCP(Microsoft Learn 문서) 한 소스만 응답",
                    "mcp-only — only MCP (Microsoft Learn docs) answers")),
        ("info", tr("byo-fabric — 내 Fabric 업무 데이터 + MCP 문서가 함께 응답",
                    "byo-fabric — your Fabric business data + MCP docs answer together")),
        ("info", tr("full — 자동 생성된 Fabric 샘플 + MCP 가 함께 응답",
                    "full — auto-created Fabric sample + MCP answer together")),
        ("ok",   tr("어느 모드든 응답 형태는 동일: activity · references · sourceData",
                    "Same response shape in every mode: activity · references · sourceData")),
    ], settle=3.0)

    ctx3 = Ctx(3, TOTAL, lbl_local(),
               caption=tr("출력에서 볼 것 / 실패하면 어디를 보는지 정리.",
                          "What to read in the output / where to look on failure."))
    S.note_card(m, ctx3, tr("출력 읽는 법 & 문제 해결", "Reading the output & troubleshooting"), [
        ("ok",   tr("Activity = 실행된 소스, References = 근거, Source Data = 미리보기",
                    "Activity = sources that ran, References = grounding, Source Data = preview")),
        ("ok",   tr("combined 샘플엔 fabricOntology 와 mcpServer 가 함께 보이면 정상",
                    "In the combined sample, fabricOntology + mcpServer together = healthy")),
        ("warn", tr("실패 시: 파일 경로 확인 — samples/responses/*.json 가 맞는지",
                    "On failure: check the file path — is samples/responses/*.json correct?")),
        ("warn", tr("Traceback 이면 repo 루트에서 실행했는지 · python3 버전 확인",
                    "On a Traceback: did you run from repo root? check the python3 version")),
    ], settle=2.8)
    return m


# ===========================================================================
# Chapter 4 — Tests / validation
# ===========================================================================

def m4() -> Module:
    m = Module("04-test")
    ctx = Ctx(4, TOTAL, lbl_test(),
              caption=tr("한 번의 명령으로 전부 검증 — 13개 항목을 차례로 통과시킵니다.",
                         "Validate everything with one command — 13 checks pass in sequence."),
              caption_sub="bash scripts/validate-local.sh")
    res = S.terminal_scene(
        m, ctx, "$ ", "bash scripts/validate-local.sh",
        [
            [("[####--------------------] 1/13 Shell syntax", DIM)],
            [("PASS", GREEN, True), (" Shell syntax", INK)],
            [("[#####-------------------] 3/13 Python compile  ", DIM), ("PASS", GREEN, True)],
            [("[#######-----------------] 3/13 Python contract tests", DIM)],
            [("Ran 11 tests in 3.80s  ", INK), ("OK   ", GREEN), ("PASS", GREEN, True)],
            [("[#########---------------] 5/13 Notebook JSON parse   ", DIM), ("PASS", GREEN, True)],
            [("[###########-------------] 6/13 Markdown links (127)  ", DIM), ("PASS", GREEN, True)],
            [("[##############----------] 8/13 Sample payload gen    ", DIM), ("PASS", GREEN, True)],
            [("[################--------] 9/13 Offline responses     ", DIM), ("PASS", GREEN, True)],
            [("[##################------] 10/13 No-secret scan       ", DIM), ("PASS", GREEN, True)],
            [("[######################--] 12/13 Static app build     ", DIM), ("PASS", GREEN, True)],
            [("[########################] 13/13 Bicep build          ", DIM), ("PASS", GREEN, True)],
            [("Local validation: PASS", GREEN, True)],
        ],
        term_title="bash — validate-local.sh", font_size=24, lh=37,
        line_reveal=0.16, settle=2.0,
        explains=[
            (tr("스크립트가 13개 검증을 순서대로 실행 — 셸 문법부터 Bicep 빌드까지.",
                "The script runs 13 checks in order — from shell syntax to Bicep build."),
             tr("각 줄 끝의 초록 PASS 가 그 단계 통과를 뜻합니다.",
                "The green PASS at each line end means that step passed.")),
            (tr("중간에 contract 테스트 11개(unittest)도 함께 돌아갑니다.",
                "Along the way, 11 contract tests (unittest) run too."),
             tr("Ran 11 tests … OK 가 보이면 계약 테스트도 통과.",
                "'Ran 11 tests … OK' means the contract tests passed.")),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 690, 1100, 760),
        tr("마지막 줄이 초록 'Local validation: PASS' 이면 끝 — 공유/PR 준비 완료.",
           "Green 'Local validation: PASS' on the last line = done — ready to share/PR."),
        sub="Local validation: PASS  (13/13)",
        settle=2.8, font_size=24, lh=37,
    )

    ctx2 = Ctx(4, TOTAL, lbl_test(),
               caption=tr("원하면 개별 검증 명령도 그대로 사용할 수 있습니다.",
                          "You can also run each individual check on its own."))
    S.terminal_scene(
        m, ctx2, "$ ", "python3 -m unittest discover -s tests",
        lines(
            [("...........", DIM)],
            [("Ran 11 tests in 3.79s", INK)],
            [("", INK)],
            [("OK", GREEN, True)],
        ),
        term_title="bash — unit tests", settle=2.2,
        explains=[
            (tr("점 하나가 통과한 테스트 1개 — 11개가 모두 통과하면 마지막에 OK.",
                "Each dot is one passing test — all 11 pass and you get OK at the end."),
             tr("FAIL/ERROR 가 보이면 그 테스트 이름으로 원인을 좁힙니다.",
                "On FAIL/ERROR, narrow it down by the test name.")),
        ],
    )

    # atomic checks the user explicitly asked about: py_compile + bash -n
    ctx_atom = Ctx(4, TOTAL, lbl_test(),
                   caption=tr("가장 기초 점검: 파이썬 컴파일과 셸 문법 — 출력이 없으면 통과입니다.",
                              "The most basic checks: Python compile and shell syntax — no output means pass."),
                   caption_sub="py_compile  ·  bash -n")
    S.terminal_scene(
        m, ctx_atom, "$ ",
        "python3 -m py_compile samples/python/inspect_retrieve_response.py",
        lines(
            [("$ echo $?", DIM)],
            [("0", GREEN, True)],
            [("$ bash -n scripts/deploy.sh", INK)],
            [("$ echo $?", DIM)],
            [("0", GREEN, True)],
        ),
        term_title="bash — py_compile · bash -n", settle=2.0,
        explains=[
            (tr("py_compile 은 파이썬 파일이 문법적으로 import 가능한지 검사합니다.",
                "py_compile checks a Python file is syntactically importable."),
             tr("아무 메시지 없이 종료코드 0 이면 정상 — 출력이 곧 성공 신호.",
                "No message and exit code 0 = healthy — silence is the success signal.")),
            (tr("bash -n 은 셸 스크립트를 '실행하지 않고' 문법만 확인합니다.",
                "bash -n checks shell syntax 'without running' the script."),
             tr("배포 전에 deploy.sh / destroy.sh 를 안전하게 점검하는 방법.",
                "A safe way to vet deploy.sh / destroy.sh before deploying.")),
        ],
    )

    ctx3 = Ctx(4, TOTAL, lbl_test(),
               caption=tr("무엇을 보고, 실패하면 어떻게 좁히는지.",
                          "What to look at, and how to narrow down a failure."))
    S.note_card(m, ctx3, tr("의미 있는 검증 명령들", "Validation commands that matter"), [
        ("step", tr("bash -n scripts/*.sh — 셸 문법    ·    py_compile — 파이썬 컴파일",
                    "bash -n scripts/*.sh — shell syntax    ·    py_compile — Python compile")),
        ("step", tr("python3 -m unittest discover -s tests — 계약 테스트 11개",
                    "python3 -m unittest discover -s tests — 11 contract tests")),
        ("step", tr("no-secret scan · Static app build · Bicep build",
                    "no-secret scan · Static app build · Bicep build")),
        ("ok",   tr("초록 PASS 13/13 이면 통과 — 그대로 진행",
                    "Green PASS 13/13 = pass — carry on")),
        ("warn", tr("빨강 FAIL 이면 그 단계 줄을 보고 해당 명령만 따로 재실행",
                    "Red FAIL? read that step's line and rerun just that command")),
    ], settle=2.8)
    return m


# ===========================================================================
# Chapter 5 — Deploy
# ===========================================================================

def m5() -> Module:
    m = Module("05-deploy")
    ctx = Ctx(5, TOTAL, lbl_deploy(),
              caption=tr("배포 진입점은 scripts/deploy.sh — 모드를 골라 실행합니다.",
                         "The deploy entry point is scripts/deploy.sh — pick a mode and run."),
              caption_sub="bash scripts/deploy.sh --help")
    res = S.terminal_scene(
        m, ctx, "$ ", "bash scripts/deploy.sh --help",
        lines(
            "Usage: bash scripts/deploy.sh [options]",
            [("  --mode <mode>     ", INK), ("byo-fabric | mcp-only | full", GREEN)],
            [("  --env-name <name> ", INK),
             (tr("azd 환경 선택/생성 (→ rg-<name>)", "select/create azd env (→ rg-<name>)"), DIM)],
            [("  --location <reg>  ", INK), ("eastus · koreacentral · swedencentral", DIM)],
            [("  --fabric-location ", INK),
             (tr("full 모드 Fabric 용량 리전", "Fabric capacity region (full mode)"), DIM)],
            "",
            [("Examples:", BLUE, True)],
            "  bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus",
            "  bash scripts/deploy.sh --mode full --env-name liveks-full --fabric-location westus3",
        ),
        term_title="bash — deploy.sh --help", font_size=23, lh=36, settle=2.0,
        explains=[
            (tr("배포는 이 한 스크립트로 끝 — 모드·환경이름·리전만 정하면 됩니다.",
                "One script does the deploy — just choose mode, env name, region."),
             tr("--env-name 값이 그대로 리소스 그룹 rg-<name> 이 됩니다.",
                "The --env-name value becomes the resource group rg-<name>.")),
            (tr("처음이라면 Examples 의 mcp-only 한 줄을 그대로 복사해 쓰면 됩니다.",
                "New here? Copy the mcp-only line from Examples verbatim."),
             tr("full 모드는 Fabric 용량까지 만들기에 권한·쿼터가 필요합니다.",
                "full mode also creates Fabric capacity — needs permissions & quota.")),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 250, 1500, 320),
        tr("세 가지 모드 — 가장 빠른 시작은 mcp-only(Fabric 없이) 입니다.",
           "Three modes — the fastest start is mcp-only (no Fabric)."),
        sub="--mode  byo-fabric | mcp-only | full",
        settle=2.6, font_size=23, lh=36,
    )

    # three deployment modes — what each uses + when to pick (short intro)
    ctx_modes = Ctx(5, TOTAL, lbl_deploy(),
                    caption=tr("세 모드는 모두 같은 Knowledge Base 위에서 동작 — 라이브 소스 구성만 다릅니다.",
                               "All three modes share one Knowledge Base — only the live sources differ."))
    S.kv_card(m, ctx_modes, tr("세 가지 배포 모드 — 무엇을 쓰나", "Three deploy modes — what each uses"), [
        ("mcp-only", "Microsoft Learn MCP Server KS",
         tr("Fabric 없이 가장 빠른 라이브 검증", "fastest live check, no Fabric")),
        ("byo-fabric", tr("MCP + 내 Fabric Ontology KS", "MCP + your Fabric Ontology KS"),
         tr("이미 있는 Fabric workspace·ontology 연결", "connect your existing Fabric workspace")),
        ("full", tr("MCP + 자동 생성 Fabric Ontology KS", "MCP + auto-created Fabric Ontology KS"),
         tr("greenfield: 샘플 Fabric 자산까지 생성", "greenfield: also creates sample Fabric")),
    ], note=tr("공통 기반: Azure AI Search Knowledge Base + Azure OpenAI — 모드는 소스 구성만 다릅니다.",
               "Shared base: Azure AI Search Knowledge Base + Azure OpenAI — modes differ only in sources."),
       settle=3.0)

    # required inputs
    ctx_in = Ctx(5, TOTAL, lbl_deploy(),
                 caption=tr("배포 전 준비: 로그인하고 아래 값들을 정합니다.",
                            "Before deploying: log in and set the values below."))
    S.kv_card(m, ctx_in, tr("배포에 입력하는 값", "Values you provide to deploy"), [
        ("azd auth login", tr("Azure Developer CLI 로그인", "Azure Developer CLI login"),
         tr("최초 1회", "one time")),
        ("az login --tenant", "<tenant-id>", tr("Azure 테넌트", "Azure tenant")),
        ("--location", "eastus / koreacentral", tr("리소스 리전", "resource region")),
        ("--env-name", "liveks-mcp",
         tr("azd 환경 = 리소스 그룹 rg-liveks-mcp", "azd env = resource group rg-liveks-mcp")),
        ("--mode", "mcp-only",
         tr("배포 모드 (byo-fabric / full 도 가능)", "deploy mode (byo-fabric / full too)")),
    ], note=tr("구독·테넌트는 az login 계정에서 자동 사용 · 키/토큰은 절대 커밋 금지",
               "Subscription & tenant come from your az login · never commit keys/tokens"), settle=2.8)

    # dry-run
    ctx_dry = Ctx(5, TOTAL, lbl_deploy(),
                  caption=tr("실제 생성 전: dry-run 으로 템플릿·페이로드·설정을 점검합니다.",
                             "Before creating anything: dry-run checks the template, payloads, settings."),
                  caption_sub="az bicep build  →  postprovision.py --dry-run")
    res_dry = S.terminal_scene(
        m, ctx_dry, "$ ", "python3 scripts/postprovision.py --dry-run",
        lines(
            [("Postprovision settings loaded", INK)],
            '{ "DEPLOYMENT_MODE": "mcp-only",',
            '  "AZURE_SEARCH_API_VERSION": "2026-05-01-preview",',
            '  "AZURE_OPENAI_MODEL_NAME": "gpt-4o-mini",',
            '  "MCP_KNOWLEDGE_SOURCE_NAME": "microsoft-learn-mcp-ks",',
            '  "KNOWLEDGE_BASE_NAME": "live-knowledge-sources-kb",',
            '  "AIRLINE_OPS_INDEX_NAME": "airline-ops-regulatory-docs" }',
            [("Dry run complete. Summary written to", GREEN), (" deployments/<env>/", INK)],
            [("deployment-summary.md", INK)],
        ),
        term_title="bash — dry-run", font_size=23, lh=35, settle=2.0,
        explains=[
            (tr("dry-run 은 실제 리소스를 만들지 않고 설정값만 출력합니다 — 비용 0.",
                "dry-run creates no resources — it just prints settings — $0 cost."),
             tr("여기서 모드·API 버전·KS/KB 이름을 미리 확인합니다.",
                "Check mode, API version, KS/KB names here first.")),
            (tr("같은 단계가 deployment-summary.md 도 미리 생성해 둡니다.",
                "The same step pre-generates deployment-summary.md too."),
             tr("값이 이상하면 .env / 모드를 고치고 다시 dry-run.",
                "If values look off, fix .env / mode and dry-run again.")),
        ],
    )
    S.zoom_term(
        m, res_dry, (E.MARGIN, 560, 1560, 700),
        tr("에러 없이 'Dry run complete' 가 나오면 실제 배포 준비 OK.",
           "'Dry run complete' with no errors = ready for the real deploy."),
        sub=tr("요약 파일이 미리 생성됩니다 → deployment-summary.md",
               "A summary file is pre-generated → deployment-summary.md"),
        settle=2.6, font_size=23, lh=35,
    )

    # deploy progress (guide — shows what deploy.sh prints; azd up not run here)
    ctx_prog = Ctx(5, TOTAL, lbl_deploy(),
                   caption=tr("실제 실행 시 deploy.sh 가 8단계를 차례로 출력합니다 (guide).",
                              "On a real run, deploy.sh prints 8 steps in sequence (guide)."),
                   caption_sub="bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus")
    res_prog = S.terminal_scene(
        m, ctx_prog, "$ ",
        "bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus",
        [
            [("+-------------------------------------------------------+", DIM)],
            [("| Live Knowledge Sources — One-command demo deployment  |", INK)],
            [("+-------------------------------------------------------+", DIM)],
            [("[###---------------------] 1/8 ", BLUE), ("Preflight: local tools", INK, True)],
            [("[OK] ", GREEN, True),
             (tr("az · azd · python3 · node 확인됨", "az · azd · python3 · node found"), DIM)],
            [("[######------------------] 2/8 ", BLUE), ("Preflight: Azure session", INK, True)],
            [("[OK] ", GREEN, True),
             (tr("subscription · tenant 로그인 확인", "subscription · tenant login verified"), DIM)],
            [("[#########---------------] 3/8 ", BLUE), ("Validate infrastructure template", INK, True)],
            [("[OK] ", GREEN, True),
             (tr("az bicep build 성공", "az bicep build succeeded"), DIM)],
            [("[##################------] 6/8 ", BLUE), ("Provision Azure resources", INK, True)],
            [("$ azd up  ", DIM),
             (tr("← 여기서부터 실제 리소스/비용 발생", "← real resources/cost start here"), YELLOW, True)],
        ],
        term_title="bash — deploy.sh", font_size=22, lh=33, line_reveal=0.14, settle=2.2,
        explains=[
            (tr("1~5단계는 점검·검증·빌드라 비용이 들지 않습니다 — 안심하고 실행.",
                "Steps 1–5 are checks/validation/builds — no cost, run with confidence."),
             tr("[OK] 표시를 따라가며 어디까지 통과했는지 확인합니다.",
                "Follow the [OK] marks to see how far it passed.")),
            (tr("6단계 azd up 부터 실제 Azure 리소스가 생성됩니다 (권한·쿼터 필요).",
                "From step 6 (azd up), real Azure resources are created (perms & quota)."),
             tr("이 영상은 여기까지 명령만 안내(guide)하고 실제 생성은 생략합니다.",
                "This video only guides the command here — it skips the real creation.")),
        ],
    )
    S.zoom_term(
        m, res_prog, (E.MARGIN, 470, 1560, 545),
        tr("6/8 Provision 단계의 azd up 부터 과금 시작 — 그 전 단계는 무료 점검.",
           "Billing starts at azd up in step 6/8 — earlier steps are free checks."),
        sub=tr("$ azd up  ← 실제 리소스/비용 발생 지점", "$ azd up  ← where real resources/cost begin"),
        settle=2.8, font_size=22, lh=33,
    )

    # real deploy (guide) + cleanup
    ctx_go = Ctx(5, TOTAL, lbl_deploy(),
                 caption=tr("실제 배포와 정리 — 비용/권한 때문에 여기서는 명령만 안내(guide)합니다.",
                            "Real deploy and cleanup — for cost/permission reasons we only guide the commands here."))
    S.note_card(m, ctx_go, tr("실제 배포 → 확인 → 정리", "Real deploy → verify → cleanup"), [
        ("step", tr("실제 배포:  bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus",
                    "Real deploy:  bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus")),
        ("info", tr("8단계: 사전점검 → Bicep 검증 → dry-run → 앱 빌드 → azd up → 사후설정",
                    "8 steps: preflight → Bicep validate → dry-run → app build → azd up → postprovision")),
        ("warn", tr("azd up 부터 실제 Azure 리소스/비용 발생 — 권한·쿼터 있을 때만 진행",
                    "azd up onward creates real Azure resources/cost — only with perms & quota")),
        ("step", tr("정리:  bash scripts/destroy.sh --env-name liveks-mcp",
                    "Cleanup:  bash scripts/destroy.sh --env-name liveks-mcp")),
        ("bad",  tr("destroy 는 'delete' 입력 확인 후 azd down --purge --force 실행",
                    "destroy asks you to type 'delete', then runs azd down --purge --force")),
    ], settle=3.0)
    return m


# ===========================================================================
# Chapter 6 — Verify
# ===========================================================================

def m6() -> Module:
    m = Module("06-verify")
    ctx = Ctx(6, TOTAL, lbl_verify(),
              caption=tr("배포 후 가장 먼저 볼 파일: 생성된 deployment-summary.md.",
                         "The first file to open after deploy: the generated deployment-summary.md."))
    res = S.file_view(m, ctx, "deployments/<env>/deployment-summary.md", [
        ("# Deployment Summary", WHITE),
        ("## Endpoints", BLUE),
        ("- Deployment mode: mcp-only", INK),
        ("- App URL: https://<app>.azurestaticapps.net", GREEN),
        ("- Azure AI Search endpoint: https://<svc>.search.windows.net", GREEN),
        ("## Knowledge Sources And Knowledge Bases", BLUE),
        ("- MCP KS: microsoft-learn-mcp-ks", INK),
        ("- MCP-only KB: live-knowledge-sources-mcp-kb", INK),
        ("- Combined KB: live-knowledge-sources-kb", INK),
        ("- Airline Ops Search index: airline-ops-regulatory-docs", INK),
        ("## Smoke Test", BLUE),
        ('  { "dryRun": false, "steps": [ "mcp-retrieve: ok" ] }', GREEN),
    ], highlights={4, 5, 7, 8, 9}, start_no=1, settle=1.8, font_size=24, lh=33)
    S.zoom_callout(
        m, S.compose(Ctx(1, 1, ""), "deployment-summary.md",
                     lines("- App URL: https://<app>.azurestaticapps.net",
                           "- Search endpoint: https://<svc>.search.windows.net",
                           "- Combined KB: live-knowledge-sources-kb"),
                     chrome=False, font_size=30, lh=58),
        (E.MARGIN, 250, 1740, 470),
        tr("App URL · 엔드포인트 · KB/KS 이름이 채워졌으면 정상입니다.",
           "App URL · endpoints · KB/KS names filled in = healthy."),
        sub=tr("비어 있으면 azd env get-values 후 postprovision.py 재실행",
               "If blank: run azd env get-values, then re-run postprovision.py"),
        settle=2.8,
    )

    # static web app showcase — what the deployed demo app actually lets you do
    ctx_app = Ctx(6, TOTAL, lbl_verify(),
                  caption=tr("App URL 을 열면 — 질문 → KB → 라이브 소스 → trace 를 브라우저에서 직접 봅니다.",
                             "Open the App URL — see query → KB → live sources → trace right in the browser."))
    S.webapp_showcase(m, ctx_app, settle=3.8)

    ctx2 = Ctx(6, TOTAL, lbl_verify(),
               caption=tr("데모 앱은 서버 라우트로 같은 trace 계약을 보여줍니다.",
                          "The demo app exposes the same trace contract via server routes."))
    S.kv_card(m, ctx2, tr("데모 앱 API 라우트", "Demo app API routes"), [
        ("GET  /api/status", tr("런타임 설정(시크릿 없이)", "runtime config (no secrets)"), ""),
        ("GET  /api/deployment-summary", tr("배포 리소스 메타데이터", "deployed resource metadata"), ""),
        ("POST /api/retrieve/mcp", tr("MCP 실시간 / 오프라인 대체", "MCP live / offline fallback"), ""),
        ("POST /api/retrieve/fabric", tr("Fabric 검색(권한 있을 때)", "Fabric search (when permitted)"), ""),
        ("POST /api/retrieve/combined", tr("두 소스 통합 라우팅", "unified routing across both"), ""),
    ], settle=2.6)

    ctx_curl = Ctx(6, TOTAL, lbl_verify(),
                   caption=tr("앱이 살아있는지 1초 점검: /api/status 를 호출합니다.",
                              "A one-second liveness check: call /api/status."),
                   caption_sub="curl https://<app>.azurestaticapps.net/api/status")
    res_curl = S.terminal_scene(
        m, ctx_curl, "$ ",
        "curl -s https://<app>.azurestaticapps.net/api/status | python3 -m json.tool",
        lines(
            '{ "deploymentMode": "mcp-only",',
            '  "searchEndpointConfigured": true,',
            '  "knowledgeBase": "live-knowledge-sources-mcp-kb",',
            '  "mcpKnowledgeSource": "microsoft-learn-mcp-ks",',
            '  "offlineFallback": true,',
            '  "secretsExposed": false }',
        ),
        term_title="bash — verify /api/status", font_size=23, lh=35, settle=2.0,
        explains=[
            (tr("status 가 200 으로 JSON 을 돌려주면 앱·런타임 설정이 정상입니다.",
                "A 200 with JSON means the app and runtime config are healthy."),
             tr("secretsExposed:false — 키는 절대 노출되지 않습니다.",
                "secretsExposed:false — keys are never exposed.")),
            (tr("searchEndpointConfigured:true 면 검색 연결까지 준비된 상태.",
                "searchEndpointConfigured:true means the search link is ready too."),
             tr("false 면 azd env get-values 로 값이 채워졌는지 확인.",
                "If false, check the values via azd env get-values.")),
        ],
    )
    S.zoom_term(
        m, res_curl, (E.MARGIN, 250, 1560, 430),
        tr("deploymentMode 와 knowledgeBase 이름이 보이면 배포 설정이 살아있는 것.",
           "Seeing deploymentMode and the knowledgeBase name = the deploy config is alive."),
        sub='"deploymentMode": "mcp-only"   "secretsExposed": false',
        settle=2.6, font_size=23, lh=35,
    )

    # live trace via the retrieve route — the real "is it working" proof
    ctx_ret = Ctx(6, TOTAL, lbl_verify(),
                  caption=tr("진짜 동작 증거: retrieve 라우트가 라이브 trace 를 그대로 돌려줍니다.",
                             "The real proof: the retrieve route returns the live trace itself."),
                  caption_sub="POST /api/retrieve/combined")
    res_ret = S.terminal_scene(
        m, ctx_ret, "$ ",
        "curl -s -X POST .../api/retrieve/combined -d '{\"query\":\"airline ops exposure\"}'",
        lines(
            [("Activity", BLUE, True)],
            '  { "type": "fabricOntology", "count": 5 }',
            '  { "type": "mcpServer", "count": 2 }',
            [("References", BLUE, True)],
            '  { "title": "Alpine Air — customer-care exposure",',
            '    "hasSourceData": true }',
            [("Source Data Preview", BLUE, True)],
            '  "fabricAnswer": "Alpine Air ranks first by exposure…"',
        ),
        term_title="bash — verify retrieve", font_size=23, lh=35, settle=2.0,
        explains=[
            (tr("로컬 mock 에서 본 것과 같은 activity·references·sourceData 가 라이브로 옵니다.",
                "The same activity·references·sourceData you saw in the mock — now live."),
             tr("두 소스(fabricOntology+mcpServer)가 함께 보이면 통합 라우팅 정상.",
                "Both sources (fabricOntology+mcpServer) together = unified routing works.")),
            (tr("권한/네트워크 문제로 라이브가 안 되면 offlineFallback 으로 같은 형태를 반환.",
                "If perms/network block live, offlineFallback returns the same shape."),
             tr("그래서 데모는 어떤 환경에서도 trace 형태를 보여줄 수 있습니다.",
                "So the demo can show the trace shape in any environment.")),
        ],
    )
    S.zoom_term(
        m, res_ret, (E.MARGIN, 250, 1500, 360),
        tr("activity 에 fabricOntology + mcpServer 둘 다 — 라이브 통합의 결정적 증거.",
           "fabricOntology + mcpServer both in activity — decisive proof of live unification."),
        sub='"type":"fabricOntology"  +  "type":"mcpServer"',
        settle=2.8, font_size=23, lh=35,
    )

    ctx3 = Ctx(6, TOTAL, lbl_verify(),
               caption=tr("무엇을 보면 '정상'인가 — 체크리스트.",
                          "What 'healthy' looks like — a checklist."))
    S.note_card(m, ctx3, tr("정상 동작 확인 체크리스트", "Healthy-operation checklist"), [
        ("ok",   tr("deployment-summary.md 에 App URL·엔드포인트·KS/KB 이름이 채워짐",
                    "deployment-summary.md has App URL · endpoints · KS/KB names filled in")),
        ("ok",   tr("앱을 열면 query → answer → activity → references → sourceData 노출",
                    "Open the app: query → answer → activity → references → sourceData show")),
        ("info", tr("클라우드가 없어도 오프라인 샘플로 동일한 trace 형태 확인 가능",
                    "No cloud? the offline samples show the same trace shape")),
        ("warn", tr("값이 비면: azd env get-values · python3 scripts/postprovision.py",
                    "If values are blank: azd env get-values · python3 scripts/postprovision.py")),
    ], settle=2.8)
    return m


# ===========================================================================
# Chapter 7 — Summary
# ===========================================================================

def m7() -> Module:
    m = Module("07-summary")
    final_path = tr("video-guide/repo-quickstart-guide.mp4",
                    "video-guide/repo-quickstart-guide-en.mp4")
    clips_glob = tr("video-guide/clips/01-intro … 07-summary.mp4",
                    "video-guide/clips/en/01-intro … 07-summary.mp4")
    rebuild_cmd = tr("cd video-guide && python3 build_guide_video.py",
                     "cd video-guide && python3 build_guide_video.py --lang en")

    ctx = Ctx(7, TOTAL, lbl_summary())
    S.pipeline_card(
        m, ctx, tr("30초 요약 — 전체 흐름", "30-second recap — the whole flow"),
        steps=[
            ("CLONE", tr("내려받기", "Get the code"), BLUE),
            ("LOCAL MOCK", tr("오프라인 체험", "Offline trial"), GREEN),
            ("TEST", tr("검증 13개", "13 checks"), YELLOW),
            ("DEPLOY", tr("배포", "Ship it"), ORANGE),
            ("VERIFY", tr("동작 확인", "Confirm it"), BLUE),
            ("CLEANUP", tr("정리", "Tear down"), RED),
        ],
        footer=[
            (tr("최종 영상   ", "Final video  "), final_path),
            (tr("모듈 클립   ", "Module clips "), clips_glob),
            (tr("재생 방법   ", "How to play "), "open " + final_path),
        ],
        settle=3.8,
    )
    ctx_recap = Ctx(7, TOTAL, lbl_summary(),
                    caption=tr("산출물과 재생 방법 — 이 파일들만 기억하면 됩니다.",
                               "Deliverables and playback — just remember these files."))
    S.note_card(m, ctx_recap, tr("산출물 · 재생 방법", "Deliverables · playback"), [
        ("ok",   tr("최종 영상: video-guide/repo-quickstart-guide.mp4 (이 영상 하나면 충분)",
                    "Final video: video-guide/repo-quickstart-guide-en.mp4 (this one is enough)")),
        ("info", tr("모듈 클립: video-guide/clips/01-intro … 07-summary.mp4",
                    "Module clips: video-guide/clips/en/01-intro … 07-summary.mp4")),
        ("step", tr("재생: open video-guide/repo-quickstart-guide.mp4",
                    "Play: open video-guide/repo-quickstart-guide-en.mp4")),
        ("step", rebuild_cmd),
        ("info", tr("실제 따라하기: README.md → validate-local.sh → deploy.sh 순서",
                    "To follow for real: README.md → validate-local.sh → deploy.sh")),
    ], settle=3.6)
    S.title_card(
        m, Ctx(7, TOTAL, lbl_summary()),
        tr("따라하기 10분이면 충분합니다", "10 minutes is all it takes"),
        subtitle="clone → mock → test → deploy → verify → cleanup",
        bullets=[tr("mock 으로 먼저 이해하고, 준비되면 deploy.sh 한 줄로 라이브 전환",
                    "Understand it with the mock first, then go live with one deploy.sh line")],
        hold=3.6,
    )
    return m


# ===========================================================================
# Orchestration
# ===========================================================================

BUILDERS = {"m1": m1, "m2": m2, "m3": m3, "m4": m4, "m5": m5, "m6": m6, "m7": m7}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma list e.g. m2,m4")
    ap.add_argument("--no-final", action="store_true")
    ap.add_argument("--lang", default="ko", choices=["ko", "en"],
                    help="caption/label language (terminal output stays identical)")
    args = ap.parse_args()

    E.LANG = args.lang
    work, clips, final = out_paths(args.lang)

    keys = [k.strip() for k in args.only.split(",") if k.strip()] or list(BUILDERS)
    clips.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    built = []
    for k in keys:
        mod = BUILDERS[k]()
        dur = sum(d for _, d in mod.slides)
        print(f"[build:{args.lang}] {k} -> {mod.key}  slides={len(mod.slides)}  ~{dur:0.1f}s")
        out = E.render_module(mod, work, clips)
        built.append(out)
        print(f"        wrote {out}")

    if not args.no_final and len(built) == len(BUILDERS):
        ordered = sorted(clips.glob("0*.mp4"))
        E.concat_modules(ordered, final)
        print(f"[final:{args.lang}] {final}")


if __name__ == "__main__":
    main()
