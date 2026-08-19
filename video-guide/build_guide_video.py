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
        ("step", tr("테스트 — validate-local.sh 로 15개 항목 검증",
                    "Tests — validate 15 checks with validate-local.sh")),
        ("step", tr("배포 — LiveKS (doctor → plan → up → down)",
                    "Deploy — LiveKS (doctor → plan → up → down)")),
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
        ("info", tr("Go live with one command — plan 확인 후 liveks up 으로 전환",
                    "Go live with one command — review the plan, then run liveks up")),
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
        {"indent": 1, "name": "liveks · liveks.ps1", "kind": "emph",
         "comment": tr("배포 수명주기 진입점", "Lifecycle entry points")},
        {"indent": 1, "name": "config · profiles", "kind": "dir",
         "comment": tr("YAML 원장 스키마 · 모드 기본값", "YAML schema · profile defaults")},
        {"indent": 1, "name": "docs", "kind": "dir",
         "comment": tr("개념 · 배포 · 문제해결 · FAQ", "Concepts · deploy · troubleshooting · FAQ")},
        {"indent": 1, "name": "scripts", "kind": "dir",
         "comment": tr("배포 hook · Fabric · validate", "hooks · Fabric · validation")},
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
        ("# Foundry IQ Live Knowledge Sources Accelerator", WHITE),
        ("", INK),
        ("One Knowledge Base can route a query to live MCP tools and", INK),
        ("governed Fabric semantics, then return the trace contract:", INK),
        ('  activity, references, and sourceData.', GREEN),
        ("", INK),
        ("## Try It In 30 Seconds", BLUE),
        ("No Azure subscription, keys, tenant, or Fabric workspace required:", DIM),
        ("", INK),
        ("$ ./liveks try", INK),
        ("Answer → Sources → Trace", GREEN),
    ], highlights={3, 4, 5, 10, 11}, start_no=1, settle=1.8, font_size=25, lh=33)
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

    # Canonical YAML ledger
    ctx_env = Ctx(2, TOTAL, lbl_clone(),
                  caption=tr(".liveks YAML — 사람이 관리하는 배포 원장. azd env 는 자동 생성됩니다.",
                             ".liveks YAML — the human-managed ledger; azd env is generated."))
    res_env = S.file_view(m, ctx_env, ".liveks/liveks-byo.yaml", [
        ("version: 2", INK),
        ("profile: byo-fabric", GREEN),
        ("environment: liveks-byo", INK),
        ("azure:", BLUE),
        ("  location: eastus", INK),
        ("fabric:", BLUE),
        ("  workspace_id: 11111111-1111-1111-1111-111111111111", INK),
        ("  ontology_id: 22222222-2222-2222-2222-222222222222", INK),
        ("  user_search_token:", INK),
        ("    env: FABRIC_USER_SEARCH_TOKEN", YELLOW),
    ], highlights={2, 7, 8, 10}, start_no=1, settle=1.6, font_size=24, lh=34)
    S.zoom_callout(
        m, S.compose(Ctx(1, 1, ""), ".liveks/liveks-byo.yaml",
                     lines("profile: byo-fabric",
                           "fabric:",
                           "  workspace_id: <guid>",
                           "  ontology_id: <guid>",
                           "  user_search_token: {env: FABRIC_USER_SEARCH_TOKEN}"),
                     chrome=False, font_size=30, lh=58),
        (E.MARGIN, 250, 1700, 520),
        tr("프로필과 Fabric ID 는 YAML, 토큰은 환경변수 참조로 분리합니다.",
           "Keep profile and Fabric IDs in YAML; reference tokens by environment name."),
        sub=tr("mcp-only 는 Fabric 값 없이 바로 계획할 수 있습니다.",
               "mcp-only can be planned immediately with no Fabric values."),
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
        ("info", tr("config/schema.yaml · profiles/ — YAML 계약과 기본값",
                    "config/schema.yaml · profiles/ — YAML contract and defaults")),
        ("info", tr("liveks · liveks.ps1 — plan · 배포 · 검증 · 정리 진입점",
                    "liveks · liveks.ps1 — plan · deploy · verify · cleanup")),
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
               caption=tr("첫 replay 는 Python 하나면 됩니다. 배포 CLI 는 bootstrap 으로 격리 설치합니다.",
                          "The first replay needs only Python; bootstrap isolates deploy dependencies."))
    res0 = S.terminal_scene(
        m, ctx0, "$ ", "python3 --version",
        lines([("Python 3.11.9", GREEN)]),
        term_title="bash — live-knowledge-sources", settle=1.6,
        explains=[
            (tr("liveks try 는 pip install 없이 바로 실행됩니다.",
                "liveks try runs immediately without pip install."),
             tr("배포 명령은 Python 3.11 이상에서 ./liveks bootstrap 을 먼저 실행합니다.",
                "For deployment commands, run ./liveks bootstrap on Python 3.11+.")),
        ],
    )

    # MCP mock
    ctx1 = Ctx(3, TOTAL, lbl_local(),
               caption=tr("offline replay: 저장된 응답을 답변부터 읽고 trace 를 검사합니다.",
                          "Offline replay: read the answer first, then inspect its trace."),
               caption_sub="./liveks try --sample mcp --details")
    res1 = S.terminal_scene(
        m, ctx1, "$ ",
        "./liveks try --sample mcp --details",
        lines(
            [("Answer", BLUE, True)],
            "Azure AI Search MCP Server Knowledge Sources connect remote",
            "HTTPS MCP tools to Knowledge Base retrieval…",
            [("Sources", BLUE, True)],
            "microsoft-learn-mcp-ks",
            [("Trace: 1 activity items, 1 references (offline replay)", GREEN, True)],
            [("Full response", BLUE, True)],
            '  { "type": "mcpServer",',
            '    "toolName": "microsoft_docs_search" }',
        ),
        font_size=24, lh=34, settle=2.0,
        explains=[
            (tr("답변을 먼저 읽고, Sources 와 Trace 로 근거 유무를 바로 확인합니다.",
                "Read the answer first, then confirm evidence in Sources and Trace."),
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
               caption=tr("combined replay: Fabric(업무 데이터) + MCP(문서)를 한 번에.",
                          "Combined replay: Fabric (business data) + MCP (docs) in one call."))
    res2 = S.terminal_scene(
        m, ctx2, "$ ",
        "./liveks try --sample combined --details",
        lines(
            [("Answer", BLUE, True)],
            "The sample ontology identifies Alpine Air as the highest",
            "customer-care exposure carrier…",
            [("Sources", BLUE, True)],
            "fabric-ontology-ks",
            "microsoft-learn-mcp-ks",
            [("Trace: 2 activity items, 2 references (offline replay)", GREEN, True)],
            [("Full response", BLUE, True)],
            '  { "type": "fabricOntology",',
            '    "knowledgeSourceName": "fabric-ontology-ks", "count": 5 }',
            '  { "type": "mcpServer",',
            '    "toolName": "microsoft_docs_search", "count": 2 }',
        ),
        font_size=24, lh=34, settle=2.0,
        explains=[
            (tr("이 체크인 replay에서는 한 번의 질의가 Fabric과 MCP 둘 다로 라우팅됐습니다.",
                "In this checked-in replay, one query routed to both Fabric and MCP."),
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
        tr("오프라인 replay의 activity[] 에 두 소스가 모두 — 이상적인 통합 trace 예시.",
           "Both sources in the offline replay activity[] — an ideal combined trace example."),
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

    # Real footage — notebook 01 actually executed offline (jupyter nbconvert --execute)
    ctx_nbr = Ctx(3, TOTAL, lbl_local(),
                  caption=tr("말이 아니라 실제 실행 화면 — 노트북 01 을 dry-run 으로 돌린 결과입니다.",
                             "Not slides — the real run: notebook 01 executed in dry-run."),
                  caption_sub="jupyter nbconvert --execute · 01-mcp-server-ks-quickstart.ipynb")
    S.real_hero(m, ctx_nbr, "assets/real/nb-hero.png", kind="editor",
                win_title="Jupyter · notebooks/01-mcp-server-ks-quickstart.ipynb", settle=2.8)
    nbtag = tr("실제 실행 · NOTEBOOK", "NOTEBOOK RUN")
    S.real_zoom(m, Ctx(3, TOTAL, lbl_local()), "assets/real/nb-run.png",
                explain=tr("셀 출력: 기본값 RUN_LIVE_CALLS=False → 오프라인 dry-run 으로 동작.",
                           "Cell output: default RUN_LIVE_CALLS=False → runs as an offline dry-run."),
                sub="MCP = learn.microsoft.com/api/mcp · tool = microsoft_docs_search",
                tag=nbtag, settle=3.0)
    S.real_zoom(m, Ctx(3, TOTAL, lbl_local()), "assets/real/nb-build.png",
                explain=tr("코드가 MCP KS·KB 페이로드를 생성 — 출력 JSON 이 그대로 찍힙니다.",
                           "The code builds the MCP KS·KB payloads — printed straight as output JSON."),
                sub="create_mcp_server_knowledge_source() · create_knowledge_base()",
                tag=nbtag, settle=3.0)
    S.real_zoom(m, Ctx(3, TOTAL, lbl_local()), "assets/real/nb-dryrun.png",
                explain=tr("핵심 분기: RUN_LIVE_CALLS 이면 실제 Azure 호출, 아니면 dry-run 출력.",
                           "The key gate: if RUN_LIVE_CALLS → real Azure call, else dry-run output."),
                sub=tr("RUN_LIVE_CALLS=true + 키를 넣는 순간 실제 retrieve 가 실행됩니다.",
                       "The moment you set RUN_LIVE_CALLS=true + keys, a real retrieve runs."),
                tag=nbtag, settle=3.4)

    ctx_modes = Ctx(3, TOTAL, lbl_local(),
                    caption=tr("세 모드의 차이 = retrieve 때 '어떤 라이브 소스가 답하나' 입니다.",
                               "The 3 modes differ in which live source answers at retrieve time."))
    S.note_card(m, ctx_modes, tr("세 모드는 retrieve 때 무엇이 다른가", "What differs at retrieve across the 3 modes"), [
        ("info", tr("mcp-only — MCP(Microsoft Learn 문서) 한 소스만 응답",
                    "mcp-only — only MCP (Microsoft Learn docs) answers")),
        ("info", tr("byo-fabric — 플래너가 내 Fabric 또는 MCP 소스를 선택",
                    "byo-fabric — the planner selects your Fabric or MCP source")),
        ("info", tr("full — 플래너가 생성된 Fabric 또는 MCP 소스를 선택",
                    "full — the planner selects generated Fabric or MCP sources")),
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
              caption=tr("한 번의 명령으로 전부 검증 — 15개 항목을 차례로 통과시킵니다.",
                         "Validate everything with one command — 15 checks pass in sequence."),
              caption_sub="bash scripts/validate-local.sh")
    res = S.terminal_scene(
        m, ctx, "$ ", "bash scripts/validate-local.sh",
        [
            [("[##----------------------] 1/15 Shell syntax", DIM)],
            [("PASS", GREEN, True), (" Shell syntax", INK)],
            [("[###---------------------] 2/15 LiveKS CLI profiles", DIM), ("PASS", GREEN, True)],
            [("[#####-------------------] 3/15 Python compile  ", DIM), ("PASS", GREEN, True)],
            [("[######------------------] 4/15 Python contract tests", DIM)],
            [("Contract tests  ", INK), ("OK   ", GREEN), ("PASS", GREEN, True)],
            [("[########----------------] 5/15 Notebook JSON parse   ", DIM), ("PASS", GREEN, True)],
            [("[###########-------------] 7/15 Markdown links        ", DIM), ("PASS", GREEN, True)],
            [("[################--------] 10/15 Sample payload gen   ", DIM), ("PASS", GREEN, True)],
            [("[##################------] 11/15 Offline responses    ", DIM), ("PASS", GREEN, True)],
            [("[###################-----] 12/15 No-secret scan       ", DIM), ("PASS", GREEN, True)],
            [("[######################--] 14/15 Static app build     ", DIM), ("PASS", GREEN, True)],
            [("[########################] 15/15 Bicep build          ", DIM), ("PASS", GREEN, True)],
            [("Local validation: PASS", GREEN, True)],
        ],
        term_title="bash — validate-local.sh", font_size=24, lh=37,
        line_reveal=0.16, settle=2.0,
        explains=[
            (tr("스크립트가 15개 검증을 순서대로 실행 — CLI 프로필부터 Bicep 빌드까지.",
                "The script runs 15 checks in order — from CLI profiles to Bicep build."),
             tr("각 줄 끝의 초록 PASS 가 그 단계 통과를 뜻합니다.",
                "The green PASS at each line end means that step passed.")),
            (tr("중간에 v2 contract 테스트(unittest)도 함께 돌아갑니다.",
                "Along the way, the v2 contract test suite (unittest) runs too."),
             tr("Contract tests … OK 가 보이면 계약 테스트도 통과.",
                "'Contract tests … OK' means the contract tests passed.")),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 690, 1100, 760),
        tr("마지막 줄이 초록 'Local validation: PASS' 이면 끝 — 공유/PR 준비 완료.",
           "Green 'Local validation: PASS' on the last line = done — ready to share/PR."),
        sub="Local validation: PASS  (15/15)",
        settle=2.8, font_size=24, lh=37,
    )

    ctx2 = Ctx(4, TOTAL, lbl_test(),
               caption=tr("원하면 개별 검증 명령도 그대로 사용할 수 있습니다.",
                          "You can also run each individual check on its own."))
    S.terminal_scene(
        m, ctx2, "$ ", "python3 -m unittest discover -s tests",
        lines(
            [("........................", DIM)],
            [("Contract tests: PASS", INK)],
            [("", INK)],
            [("OK", GREEN, True)],
        ),
        term_title="bash — unit tests", settle=2.2,
        explains=[
            (tr("점 하나가 통과한 테스트 1개 — 전체가 통과하면 마지막에 OK.",
                "Each dot is one passing test — the suite ends with OK when all pass."),
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
        "python3 -m py_compile tools/try_offline.py",
        lines(
            [("$ echo $?", DIM)],
            [("0", GREEN, True)],
            [("$ bash -n liveks", INK)],
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
             tr("배포 전에 LiveKS launcher 와 호환 wrapper 를 안전하게 점검합니다.",
                "This safely checks the LiveKS launcher and compatibility wrappers.")),
        ],
    )

    ctx3 = Ctx(4, TOTAL, lbl_test(),
               caption=tr("무엇을 보고, 실패하면 어떻게 좁히는지.",
                          "What to look at, and how to narrow down a failure."))
    S.note_card(m, ctx3, tr("의미 있는 검증 명령들", "Validation commands that matter"), [
        ("step", tr("bash -n scripts/*.sh — 셸 문법    ·    py_compile — 파이썬 컴파일",
                    "bash -n scripts/*.sh — shell syntax    ·    py_compile — Python compile")),
        ("step", tr("python3 -m unittest discover -s tests — 계약 테스트",
                    "python3 -m unittest discover -s tests — contract tests")),
        ("step", tr("no-secret scan · Static app build · Bicep build",
                    "no-secret scan · Static app build · Bicep build")),
        ("ok",   tr("초록 PASS 15/15 이면 통과 — 그대로 진행",
                    "Green PASS 15/15 = pass — carry on")),
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
              caption=tr("배포 진입점은 LiveKS — profile 을 고르고 YAML 원장을 만듭니다.",
                         "The deploy entry point is LiveKS — choose a profile and create its YAML ledger."),
              caption_sub="./liveks profiles")
    res = S.terminal_scene(
        m, ctx, "$ ", "./liveks profiles",
        lines(
            [("offline:", GREEN, True), (" inspect checked-in retrieve responses", DIM)],
            [("mcp-only:", GREEN, True), (" fastest live Search + MCP path", DIM)],
            [("byo-fabric:", GREEN, True), (" connect an existing ontology", DIM)],
            [("full:", YELLOW, True), (" create Fabric F2 + sample assets", DIM)],
            "",
            [("Next:", BLUE, True)],
            "  ./liveks init --profile mcp-only --env liveks-mcp",
            "  ./liveks doctor --env liveks-mcp",
            "  ./liveks plan --env liveks-mcp",
        ),
        term_title="bash — liveks profiles", font_size=23, lh=36, settle=2.0,
        explains=[
            (tr("처음이라면 mcp-only 로 YAML 원장을 만들고 doctor 를 실행합니다.",
                "Start with mcp-only: create the YAML ledger, then run doctor."),
             tr("환경 이름은 리소스 그룹과 redacted lock 의 기준이 됩니다.",
                "The environment name anchors resource naming and the redacted lock.")),
            (tr("full 모드는 Fabric F2 용량까지 만들기에 별도 승인 flag 가 필요합니다.",
                "full creates Fabric F2 capacity and requires a separate acknowledgement flag."),
             tr("byo-fabric 은 기존 Fabric 자산을 재사용하고 삭제하지 않습니다.",
                "byo-fabric reuses existing Fabric assets and never deletes them.")),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 250, 1500, 320),
        tr("네 profile — offline 다음 가장 빠른 live 시작은 mcp-only 입니다.",
           "Four profiles — after offline, mcp-only is the fastest live start."),
        sub="offline | mcp-only | byo-fabric | full",
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
        ("azure.location", "eastus", tr("YAML 의 Azure 리전", "Azure region in YAML")),
        ("environment", "liveks-mcp",
         tr("YAML · azd · 리소스 그룹 기준", "YAML · azd · resource-group identity")),
        ("profile", "mcp-only",
         tr("offline / byo-fabric / full 도 가능", "offline / byo-fabric / full also available")),
    ], note=tr("구독·테넌트는 az login 계정에서 자동 사용 · 키/토큰은 절대 커밋 금지",
               "Subscription & tenant come from your az login · never commit keys/tokens"), settle=2.8)

    # plan
    ctx_dry = Ctx(5, TOTAL, lbl_deploy(),
                  caption=tr("실제 생성 전: plan 이 도구·로그인·Bicep·페이로드·앱을 점검합니다.",
                             "Before creating anything, plan checks tools, auth, Bicep, payloads, and app."),
                  caption_sub="./liveks plan --env liveks-mcp")
    res_dry = S.terminal_scene(
        m, ctx_dry, "$ ", "./liveks plan --env liveks-mcp",
        lines(
            [("LiveKS plan: WARN", YELLOW, True)],
            [("[PASS] python: 3.11.9", INK)],
            [("[PASS] azd-version: 1.27.0", INK)],
            [("[PASS] bicep-build: completed", INK)],
            [("[PASS] payload-dry-run: completed", INK)],
            [("[PASS] app-build: completed", INK)],
            [("- Azure AI Search Basic", DIM)],
            [("- Azure OpenAI model deployment", DIM)],
            [("Artifact: .liveks/liveks-mcp.lock.json", GREEN)],
        ),
        term_title="bash — dry-run", font_size=23, lh=35, settle=2.0,
        explains=[
            (tr("plan 은 cloud resource 를 만들지 않고 local build 와 read-only 진단만 수행합니다.",
                "plan creates no cloud resources; it runs local builds and read-only diagnostics."),
             tr("리소스·비용·경고·소유권을 확인한 뒤에만 up 으로 이동합니다.",
                "Review resources, cost, warnings, and ownership before moving to up.")),
            (tr("redacted lock 은 어떤 값을 썼고 무엇을 소유하는지 기록합니다.",
                "The redacted lock records resolved values and ownership."),
             tr("값이 이상하면 YAML 을 고치고 plan 을 다시 실행합니다.",
                "If anything looks wrong, edit YAML and rerun plan.")),
        ],
    )
    S.zoom_term(
        m, res_dry, (E.MARGIN, 560, 1560, 700),
        tr("FAIL 없이 plan 이 끝나고 예상 리소스가 맞으면 배포 준비 완료.",
           "No FAIL and the expected resources match means the deployment is ready."),
        sub=tr("redacted 원장 → .liveks/liveks-mcp.lock.json",
               "Redacted record → .liveks/liveks-mcp.lock.json"),
        settle=2.6, font_size=23, lh=35,
    )

    # deploy progress (guide — shows the plan-first sequence; cloud creation is not run here)
    ctx_prog = Ctx(5, TOTAL, lbl_deploy(),
                   caption=tr("up 은 plan 을 반복하고 Azure preview 뒤에 정확한 확인 문구를 요구합니다.",
                              "up repeats plan and requires an exact confirmation after Azure preview."),
                   caption_sub="./liveks up --env liveks-mcp")
    res_prog = S.terminal_scene(
        m, ctx_prog, "$ ",
        "./liveks up --env liveks-mcp",
        [
            [("+-------------------------------------------------------+", DIM)],
            [("| Foundry IQ Live Knowledge Sources — plan-first up      |", INK)],
            [("+-------------------------------------------------------+", DIM)],
            [("[PASS] ", GREEN, True), ("doctor · Bicep · payload · app plan", DIM)],
            [("[PASS] ", GREEN, True), ("azd provision --preview", DIM)],
            [("Cost: Search Basic + OpenAI + Storage + app hosting", YELLOW)],
            [("Type 'create liveks-mcp' to continue:", BLUE, True)],
            [("> create liveks-mcp", INK)],
            [("$ azd up --environment liveks-mcp", DIM)],
            [("[PASS] ", GREEN, True), ("MCP retrieve evidence returned", DIM)],
        ],
        term_title="bash — liveks up", font_size=22, lh=33, line_reveal=0.14, settle=2.2,
        explains=[
            (tr("plan 과 Azure preview 까지는 resource 를 만들지 않습니다.",
                "The plan and Azure preview do not create resources."),
             tr("리소스와 비용을 읽고 정확한 환경 이름으로 확인합니다.",
                "Read the resources and cost, then confirm the exact environment.")),
            (tr("확인 문구 뒤 azd up 부터 실제 Azure 리소스가 생성됩니다.",
                "Real Azure resources are created only after confirmation when azd up begins."),
             tr("이 영상은 여기까지 명령만 안내(guide)하고 실제 생성은 생략합니다.",
                "This video only guides the command here — it skips the real creation.")),
        ],
    )
    S.zoom_term(
        m, res_prog, (E.MARGIN, 470, 1560, 545),
        tr("정확한 create 확인 뒤 azd up 부터 과금 가능 — 그 전에는 plan/preview.",
           "Costs can begin at azd up after exact confirmation; everything before is plan/preview."),
        sub=tr("> create liveks-mcp  →  $ azd up", "> create liveks-mcp  →  $ azd up"),
        settle=2.8, font_size=22, lh=33,
    )

    # real deploy (guide) + cleanup
    ctx_go = Ctx(5, TOTAL, lbl_deploy(),
                 caption=tr("실제 배포와 정리 — 비용/권한 때문에 여기서는 명령만 안내(guide)합니다.",
                            "Real deploy and cleanup — for cost/permission reasons we only guide the commands here."))
    S.note_card(m, ctx_go, tr("실제 배포 → 확인 → 정리", "Real deploy → verify → cleanup"), [
        ("step", tr("설정:  ./liveks init --profile mcp-only --env liveks-mcp",
                    "Configure:  ./liveks init --profile mcp-only --env liveks-mcp")),
        ("info", tr("계획:  ./liveks doctor --env liveks-mcp → ./liveks plan --env liveks-mcp",
                    "Plan:  ./liveks doctor --env liveks-mcp → ./liveks plan --env liveks-mcp")),
        ("warn", tr("배포:  ./liveks up --env liveks-mcp — 확인 뒤 실제 비용 발생 가능",
                    "Deploy:  ./liveks up --env liveks-mcp — costs can start after confirmation")),
        ("step", tr("검증:  ./liveks verify --env liveks-mcp",
                    "Verify:  ./liveks verify --env liveks-mcp")),
        ("bad",  tr("정리:  ./liveks down --env liveks-mcp — 소유권 확인 후 삭제",
                    "Cleanup:  ./liveks down --env liveks-mcp — ownership checked before delete")),
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

    # Real footage — the actual demo app (captured screenshots of the running UI)
    apptabs = [tr("개요", "Overview"), "MCP Live", "Fabric", "Combined", tr("배포", "Deploy")]
    ctx_appr = Ctx(6, TOTAL, lbl_verify(),
                   caption=tr("개념도 그대로 — 이번엔 실제로 실행되는 데모 앱 화면입니다.",
                              "The same concept map — now the actual running demo app."),
                   caption_sub="static-app · Azure Static Web Apps + managed Functions API")
    S.real_hero(m, ctx_appr, "assets/real/app-hero.png", kind="browser",
                url="<app>.azurestaticapps.net", tabs=apptabs, active=0, settle=2.8)
    apptag = tr("실제 앱 · LIVE APP", "LIVE APP")
    S.real_zoom(m, Ctx(6, TOTAL, lbl_verify()), "assets/real/app-modes.png",
                explain=tr("mcp-only로 첫 live를 증명한 뒤 byo-fabric 또는 full로 확장합니다.",
                           "Prove the first live path with mcp-only, then expand to byo-fabric or full."),
                sub=tr("mcp-only=첫 live · byo-fabric=기존 Fabric · full=승인된 greenfield",
                       "mcp-only=first live · byo-fabric=existing Fabric · full=approved greenfield"),
                tag=apptag, settle=3.0)
    S.real_zoom(m, Ctx(6, TOTAL, lbl_verify()), "assets/real/app-mcp-answer.png",
                explain=tr("MCP Live: 답변과 함께 'Source Trace' 배지가 어떤 소스가 답했는지 보여줍니다.",
                           "MCP Live: the answer plus 'Source Trace' badges show which source answered."),
                sub="MCP Server KS · activity · references · offline replay",
                tag=apptag, settle=3.0)
    S.real_zoom(m, Ctx(6, TOTAL, lbl_verify()), "assets/real/app-mcp-json.png",
                explain=tr("activity·references = 실행된 소스와 근거 계약을 그대로 노출합니다.",
                           "activity·references expose the exact sources-that-ran + grounding contract."),
                sub='type:"mcpServer" · toolName:"microsoft_docs_search" · sourceData',
                tag=apptag, settle=3.0)
    S.real_zoom(m, Ctx(6, TOTAL, lbl_verify()), "assets/real/app-combined.png",
                explain=tr("Combined replay: 이 체크인 예시는 두 소스가 함께 보입니다.",
                           "Combined replay: this checked-in example shows both sources."),
                sub=tr("라이브에서는 플래너가 질의에 따라 하나 또는 둘을 선택합니다.",
                       "Live, the planner selects one or both for each query."),
                tag=apptag, settle=3.4)
    S.real_zoom(m, Ctx(6, TOTAL, lbl_verify()), "assets/real/app-deploy.png",
                explain=tr("Deploy 탭: 런타임 상태·요약 JSON — 설정만 보이고 시크릿은 없습니다.",
                           "Deploy tab: runtime status + summary JSON — config only, never secrets."),
                sub="hasSearchKey:false · reachabilityStatus · KB/KS names",
                tag=apptag, settle=3.0)

    ctx2 = Ctx(6, TOTAL, lbl_verify(),
               caption=tr("데모 앱은 서버 라우트로 같은 trace 계약을 보여줍니다.",
                          "The demo app exposes the same trace contract via server routes."))
    S.kv_card(m, ctx2, tr("데모 앱 API 라우트", "Demo app API routes"), [
        ("GET  /api/status", tr("런타임 설정(시크릿 없이)", "runtime config (no secrets)"), ""),
        ("GET  /api/deployment-summary", tr("배포 리소스 메타데이터", "deployed resource metadata"), ""),
        ("POST /api/retrieve/mcp", tr("MCP 실시간 / 오프라인 대체", "MCP live / offline fallback"), ""),
        ("POST /api/retrieve/fabric", tr("Fabric 검색(권한 있을 때)", "Fabric search (when permitted)"), ""),
        ("POST /api/retrieve/combined", tr("플래너 기반 통합 라우팅", "planner-selected unified routing"), ""),
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
            ("TEST", tr("검증 15개", "15 checks"), YELLOW),
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
        ("info", tr("실제 따라하기: README.md → liveks try → doctor → plan → up 순서",
                    "To follow for real: README.md → liveks try → doctor → plan → up")),
    ], settle=3.6)
    S.title_card(
        m, Ctx(7, TOTAL, lbl_summary()),
        tr("따라하기 10분이면 충분합니다", "10 minutes is all it takes"),
        subtitle="clone → mock → test → deploy → verify → cleanup",
        bullets=[tr("replay 로 먼저 이해하고, plan 확인 후 liveks up 으로 전환",
                    "Start with replay, review the plan, then go live with liveks up")],
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
