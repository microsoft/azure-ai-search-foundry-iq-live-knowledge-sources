#!/usr/bin/env python3
"""Build the "clone -> mock -> test -> deploy -> verify -> cleanup" guide video.

Produces one MP4 per chapter under video-guide/clips/ and a single merged
video-guide/repo-quickstart-guide.mp4. Content uses outputs that were actually
run against this repo (offline mock, local validation gate, dry-run, generated
deployment summary). Captions are Korean; terminal text is real command output.

Usage:
    python3 build_guide_video.py                 # build everything
    python3 build_guide_video.py --only m2,m4    # build selected chapters
    python3 build_guide_video.py --no-final      # skip the merge step
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import engine as E
import scenes as S
from engine import (
    Ctx, Module, INK, DIM, FAINT, BLUE, GREEN, ORANGE, RED, YELLOW, WHITE,
)

HERE = Path(__file__).resolve().parent
WORK = Path("/tmp/vg_work")
CLIPS = HERE / "clips"
FINAL = HERE / "repo-quickstart-guide.mp4"

REPO_URL = "https://github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources.git"
REPO_DIR = "azure-ai-search-foundry-iq-live-knowledge-sources"
TOTAL = 7


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
    ctx = Ctx(1, TOTAL, "소개 · Overview")
    S.title_card(
        m, ctx, "Live Knowledge Sources",
        subtitle="Azure AI Search · Foundry IQ — Clone → Deploy 가이드",
        bullets=[
            "MCP Server + Fabric Ontology를 하나의 Knowledge Base로 라우팅",
            "응답에서 activity · references · sourceData 추적을 직접 확인",
        ],
        code="clone → mock → test → deploy → verify → cleanup",
        big=True, hold=3.4,
    )
    ctx2 = Ctx(1, TOTAL, "소개 · Overview",
               caption="이 레포가 하는 일: 라이브 소스가 '무엇을 근거로' 답했는지 추적으로 증명합니다.")
    S.note_card(m, ctx2, "이 영상에서 다루는 6개 모듈", [
        ("step", "Clone & 폴더 구조 — 무엇을 보고 어떤 값을 넣는지"),
        ("step", "로컬 mock 실행 — Azure 없이 30초 만에 trace 체험"),
        ("step", "테스트 — validate-local.sh 로 13개 항목 검증"),
        ("step", "배포 — deploy.sh (dry-run → 실제 → cleanup)"),
        ("step", "동작 확인 — deployment-summary.md · 데모 앱 라우트"),
        ("ok",   "10분이면 따라할 수 있게 핵심만 순서대로 보여줍니다"),
    ], settle=3.6)
    ctx3 = Ctx(1, TOTAL, "소개 · Overview",
               caption="왜 이 레포인가 — 문서가 아니라 '실행 추적'을 직접 봅니다.")
    S.note_card(m, ctx3, "이 레포를 쓰는 이유", [
        ("info", "See the trace, not just docs — 어떤 소스·도구가 실행됐는지 응답에서 확인"),
        ("info", "Run in 30s with zero setup — 키·테넌트·Fabric 없이 오프라인 체험"),
        ("info", "Go live with one command — 준비되면 deploy.sh 로 라이브 전환"),
    ], settle=3.4)
    return m


# ===========================================================================
# Chapter 2 — Clone & folder structure
# ===========================================================================

def m2() -> Module:
    m = Module("02-clone")
    ctx = Ctx(2, TOTAL, "Clone & 폴더 구조",
              caption="GitHub에서 clone — 모든 것은 이 한 줄에서 시작합니다.",
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
            ("git clone 으로 레포 전체를 로컬에 복사 — 추가 설정은 필요 없습니다.",
             "복제가 끝나면 cd 로 폴더에 들어갑니다."),
            ("이후 모든 명령은 이 레포 루트 폴더에서 실행합니다.",
             "cd azure-ai-search-foundry-iq-live-knowledge-sources"),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 250, 1620, 320),
        "원본은 microsoft 조직 레포지토리 — 여기를 clone 합니다.",
        sub="github.com/microsoft/azure-ai-search-foundry-iq-live-knowledge-sources",
        settle=2.6,
    )

    # cd + folder tree
    ctx_tree = Ctx(2, TOTAL, "Clone & 폴더 구조",
                   caption="폴더 구조 한눈에 — 어디에 무엇이 있는지부터 익힙니다.")
    S.tree_view(m, ctx_tree, "azure-ai-search-foundry-iq-live-knowledge-sources/", [
        {"indent": 0, "name": REPO_DIR, "kind": "root"},
        {"indent": 1, "name": "README.md", "kind": "emph", "comment": "시작 지점 · 무엇을/왜/30초 체험"},
        {"indent": 1, "name": ".env.sample", "kind": "emph", "comment": "배포 입력값 템플릿"},
        {"indent": 1, "name": "docs", "kind": "dir", "comment": "개념 · 배포 · 문제해결 · FAQ"},
        {"indent": 1, "name": "scripts", "kind": "dir", "comment": "deploy · destroy · validate 스크립트"},
        {"indent": 1, "name": "infra", "kind": "dir", "comment": "Azure 리소스 Bicep"},
        {"indent": 1, "name": "static-app", "kind": "dir", "comment": "데모 앱 (SWA + Functions)"},
        {"indent": 1, "name": "samples", "kind": "dir", "comment": "오프라인 응답 · 페이로드 · 데이터"},
        {"indent": 1, "name": "notebooks", "kind": "dir", "comment": "MCP · Fabric 튜토리얼"},
        {"indent": 1, "name": "src/ks_factory", "kind": "dir", "comment": "재사용 Python 빌더"},
    ], settle=2.8)

    # README one-liner
    ctx_rm = Ctx(2, TOTAL, "Clone & 폴더 구조",
                 caption="README.md — 이 레포가 하는 일을 한 줄로 요약해 둡니다.")
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
        "핵심 한 줄: 응답이 activity · references · sourceData 를 돌려줍니다.",
        sub="이 세 가지가 '무엇을 근거로 답했는가'를 증명하는 trace 계약입니다.",
        settle=2.8,
    )

    # .env.sample
    ctx_env = Ctx(2, TOTAL, "Clone & 폴더 구조",
                  caption=".env.sample — 배포에 넣을 값들의 템플릿. 복사해서 채웁니다.")
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
        ("# Fabric Ontology (byo-fabric / full 에서 필요)", DIM),
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
        "DEPLOYMENT_MODE 와 Fabric ID 가 핵심 입력값입니다.",
        sub="mcp-only 는 Fabric 값이 필요 없습니다 — 가장 빠른 시작 경로.",
        settle=2.8,
    )

    # key files to read
    ctx_kf = Ctx(2, TOTAL, "Clone & 폴더 구조",
                 caption="처음 열어볼 파일은 이 다섯 개면 충분합니다.")
    S.note_card(m, ctx_kf, "꼭 봐야 할 파일", [
        ("info", "README.md — 무엇을 · 왜 · 30초 체험 · 배포 모드 표"),
        ("info", "docs/10-one-command-deployment.md — 배포 전 과정"),
        ("info", ".env.sample — 배포에 넣을 값(모드·엔드포인트·Fabric ID)"),
        ("info", "scripts/deploy.sh · destroy.sh — 배포 · 정리 진입점"),
        ("info", "scripts/validate-local.sh — 클라우드 없이 로컬 검증"),
    ], settle=2.6)
    return m


# ===========================================================================
# Chapter 3 — Local mock run
# ===========================================================================

def m3() -> Module:
    m = Module("03-local")
    ctx0 = Ctx(3, TOTAL, "로컬 mock 실행",
               caption="설치가 필요할까? — python3 하나면 됩니다. 추가 의존성 없음.")
    res0 = S.terminal_scene(
        m, ctx0, "$ ", "python3 --version",
        lines([("Python 3.11.9", GREEN)]),
        term_title="bash — live-knowledge-sources", settle=1.6,
        explains=[
            ("로컬 mock 은 pip install 도, 가상환경도 필요 없습니다 — python3 만 있으면 OK.",
             "Python 3.9 이상이면 그대로 진행합니다."),
        ],
    )

    # MCP mock
    ctx1 = Ctx(3, TOTAL, "로컬 mock 실행",
               caption="mock 모드: 저장된 오프라인 응답을 그대로 검사합니다.",
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
            ("Activity[] = 이 질의에서 '실제로 실행된' 소스/도구 목록입니다.",
             "여기선 mcpServer 가 microsoft_docs_search 도구를 호출했습니다."),
            ("References[] = 답의 근거가 된 항목 — 제목과 sourceData 키를 가집니다.",
             "Source Data Preview = 그 근거의 실제 내용 미리보기."),
        ],
    )
    S.zoom_term(
        m, res1, (E.MARGIN, 470, 1500, 640),
        "references[] — 어떤 근거가 돌아왔는지와 sourceData 키를 보여줍니다.",
        sub='hasSourceData: true   sourceDataKeys: ["content","title"]',
        settle=2.8, font_size=24, lh=34,
    )

    # Combined mock
    ctx2 = Ctx(3, TOTAL, "로컬 mock 실행",
               caption="combined 샘플: Fabric(업무 데이터) + MCP(문서)를 한 번에.")
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
            ("한 번의 질의가 Fabric(업무 데이터)과 MCP(문서) 둘 다로 라우팅됩니다.",
             "activity 에 fabricOntology · mcpServer 가 함께 보입니다."),
            ("fabricAnswer/fabricRawData = 업무 데이터 근거, MCP = 문서 근거.",
             "이것이 '하나의 KB가 라이브로 통합'한다는 의미입니다."),
        ],
    )
    S.zoom_term(
        m, res2, (E.MARGIN, 250, 1560, 470),
        "activity[] 에 두 소스가 모두 — 하나의 KB가 라이브로 라우팅한 증거.",
        sub="type: fabricOntology  +  type: mcpServer",
        settle=2.8, font_size=24, lh=34,
    )

    ctx3 = Ctx(3, TOTAL, "로컬 mock 실행",
               caption="출력에서 볼 것 / 실패하면 어디를 보는지 정리.")
    S.note_card(m, ctx3, "출력 읽는 법 & 문제 해결", [
        ("ok",   "Activity = 실행된 소스, References = 근거, Source Data = 미리보기"),
        ("ok",   "combined 샘플엔 fabricOntology 와 mcpServer 가 함께 보이면 정상"),
        ("warn", "실패 시: 파일 경로 확인 — samples/responses/*.json 가 맞는지"),
        ("warn", "Traceback 이면 repo 루트에서 실행했는지 · python3 버전 확인"),
    ], settle=2.8)
    return m


# ===========================================================================
# Chapter 4 — Tests / validation
# ===========================================================================

def m4() -> Module:
    m = Module("04-test")
    ctx = Ctx(4, TOTAL, "테스트 · 검증",
              caption="한 번의 명령으로 전부 검증 — 13개 항목을 차례로 통과시킵니다.",
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
            ("스크립트가 13개 검증을 순서대로 실행 — 셸 문법부터 Bicep 빌드까지.",
             "각 줄 끝의 초록 PASS 가 그 단계 통과를 뜻합니다."),
            ("중간에 contract 테스트 11개(unittest)도 함께 돌아갑니다.",
             "Ran 11 tests … OK 가 보이면 계약 테스트도 통과."),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 690, 1100, 760),
        "마지막 줄이 초록 'Local validation: PASS' 이면 끝 — 공유/PR 준비 완료.",
        sub="Local validation: PASS  (13/13)",
        settle=2.8, font_size=24, lh=37,
    )

    ctx2 = Ctx(4, TOTAL, "테스트 · 검증",
               caption="원하면 개별 검증 명령도 그대로 사용할 수 있습니다.")
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
            ("점 하나가 통과한 테스트 1개 — 11개가 모두 통과하면 마지막에 OK.",
             "FAIL/ERROR 가 보이면 그 테스트 이름으로 원인을 좁힙니다."),
        ],
    )

    # atomic checks the user explicitly asked about: py_compile + bash -n
    ctx_atom = Ctx(4, TOTAL, "테스트 · 검증",
                   caption="가장 기초 점검: 파이썬 컴파일과 셸 문법 — 출력이 없으면 통과입니다.",
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
            ("py_compile 은 파이썬 파일이 문법적으로 import 가능한지 검사합니다.",
             "아무 메시지 없이 종료코드 0 이면 정상 — 출력이 곧 성공 신호."),
            ("bash -n 은 셸 스크립트를 '실행하지 않고' 문법만 확인합니다.",
             "배포 전에 deploy.sh / destroy.sh 를 안전하게 점검하는 방법."),
        ],
    )

    ctx3 = Ctx(4, TOTAL, "테스트 · 검증",
               caption="무엇을 보고, 실패하면 어떻게 좁히는지.")
    S.note_card(m, ctx3, "의미 있는 검증 명령들", [
        ("step", "bash -n scripts/*.sh — 셸 문법    ·    py_compile — 파이썬 컴파일"),
        ("step", "python3 -m unittest discover -s tests — 계약 테스트 11개"),
        ("step", "no-secret scan · Static app build · Bicep build"),
        ("ok",   "초록 PASS 13/13 이면 통과 — 그대로 진행"),
        ("warn", "빨강 FAIL 이면 그 단계 줄을 보고 해당 명령만 따로 재실행"),
    ], settle=2.8)
    return m


# ===========================================================================
# Chapter 5 — Deploy
# ===========================================================================

def m5() -> Module:
    m = Module("05-deploy")
    ctx = Ctx(5, TOTAL, "배포 · Deploy",
              caption="배포 진입점은 scripts/deploy.sh — 모드를 골라 실행합니다.",
              caption_sub="bash scripts/deploy.sh --help")
    res = S.terminal_scene(
        m, ctx, "$ ", "bash scripts/deploy.sh --help",
        lines(
            "Usage: bash scripts/deploy.sh [options]",
            [("  --mode <mode>     ", INK), ("byo-fabric | mcp-only | full", GREEN)],
            [("  --env-name <name> ", INK), ("azd 환경 선택/생성 (→ rg-<name>)", DIM)],
            [("  --location <reg>  ", INK), ("eastus · koreacentral · swedencentral", DIM)],
            [("  --fabric-location ", INK), ("full 모드 Fabric 용량 리전", DIM)],
            "",
            [("Examples:", BLUE, True)],
            "  bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus",
            "  bash scripts/deploy.sh --mode full --env-name liveks-full --fabric-location westus3",
        ),
        term_title="bash — deploy.sh --help", font_size=23, lh=36, settle=2.0,
        explains=[
            ("배포는 이 한 스크립트로 끝 — 모드·환경이름·리전만 정하면 됩니다.",
             "--env-name 값이 그대로 리소스 그룹 rg-<name> 이 됩니다."),
            ("처음이라면 Examples 의 mcp-only 한 줄을 그대로 복사해 쓰면 됩니다.",
             "full 모드는 Fabric 용량까지 만들기에 권한·쿼터가 필요합니다."),
        ],
    )
    S.zoom_term(
        m, res, (E.MARGIN, 250, 1500, 320),
        "세 가지 모드 — 가장 빠른 시작은 mcp-only(파브릭 없이) 입니다.",
        sub="--mode  byo-fabric | mcp-only | full",
        settle=2.6, font_size=23, lh=36,
    )

    # required inputs
    ctx_in = Ctx(5, TOTAL, "배포 · Deploy",
                 caption="배포 전 준비: 로그인하고 아래 값들을 정합니다.")
    S.kv_card(m, ctx_in, "배포에 입력하는 값", [
        ("azd auth login", "Azure Developer CLI 로그인", "최초 1회"),
        ("az login --tenant", "<tenant-id>", "Azure 테넌트"),
        ("--location", "eastus / koreacentral", "리소스 리전"),
        ("--env-name", "liveks-mcp", "azd 환경 = 리소스 그룹 rg-liveks-mcp"),
        ("--mode", "mcp-only", "배포 모드 (byo-fabric / full 도 가능)"),
    ], note="구독·테넌트는 az login 계정에서 자동 사용 · 키/토큰은 절대 커밋 금지", settle=2.8)

    # dry-run
    ctx_dry = Ctx(5, TOTAL, "배포 · Deploy",
                  caption="실제 생성 전: dry-run 으로 템플릿·페이로드·설정을 점검합니다.",
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
            ("dry-run 은 실제 리소스를 만들지 않고 설정값만 출력합니다 — 비용 0.",
             "여기서 모드·API 버전·KS/KB 이름을 미리 확인합니다."),
            ("같은 단계가 deployment-summary.md 도 미리 생성해 둡니다.",
             "값이 이상하면 .env / 모드를 고치고 다시 dry-run."),
        ],
    )
    S.zoom_term(
        m, res_dry, (E.MARGIN, 560, 1560, 700),
        "에러 없이 'Dry run complete' 가 나오면 실제 배포 준비 OK.",
        sub="요약 파일이 미리 생성됩니다 → deployment-summary.md",
        settle=2.6, font_size=23, lh=35,
    )

    # deploy progress (guide — shows what deploy.sh prints; azd up not run here)
    ctx_prog = Ctx(5, TOTAL, "배포 · Deploy",
                   caption="실제 실행 시 deploy.sh 가 8단계를 차례로 출력합니다 (guide).",
                   caption_sub="bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus")
    res_prog = S.terminal_scene(
        m, ctx_prog, "$ ",
        "bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus",
        [
            [("+-------------------------------------------------------+", DIM)],
            [("| Live Knowledge Sources — One-command demo deployment  |", INK)],
            [("+-------------------------------------------------------+", DIM)],
            [("[###---------------------] 1/8 ", BLUE), ("Preflight: local tools", INK, True)],
            [("[OK] ", GREEN, True), ("az · azd · python3 · node 확인됨", DIM)],
            [("[######------------------] 2/8 ", BLUE), ("Preflight: Azure session", INK, True)],
            [("[OK] ", GREEN, True), ("subscription · tenant 로그인 확인", DIM)],
            [("[#########---------------] 3/8 ", BLUE), ("Validate infrastructure template", INK, True)],
            [("[OK] ", GREEN, True), ("az bicep build 성공", DIM)],
            [("[##################------] 6/8 ", BLUE), ("Provision Azure resources", INK, True)],
            [("$ azd up  ", DIM), ("← 여기서부터 실제 리소스/비용 발생", YELLOW, True)],
        ],
        term_title="bash — deploy.sh", font_size=22, lh=33, line_reveal=0.14, settle=2.2,
        explains=[
            ("1~5단계는 점검·검증·빌드라 비용이 들지 않습니다 — 안심하고 실행.",
             "[OK] 표시를 따라가며 어디까지 통과했는지 확인합니다."),
            ("6단계 azd up 부터 실제 Azure 리소스가 생성됩니다 (권한·쿼터 필요).",
             "이 영상은 여기까지 명령만 안내(guide)하고 실제 생성은 생략합니다."),
        ],
    )
    S.zoom_term(
        m, res_prog, (E.MARGIN, 470, 1560, 545),
        "6/8 Provision 단계의 azd up 부터 과금 시작 — 그 전 단계는 무료 점검.",
        sub="$ azd up  ← 실제 리소스/비용 발생 지점",
        settle=2.8, font_size=22, lh=33,
    )

    # real deploy (guide) + cleanup
    ctx_go = Ctx(5, TOTAL, "배포 · Deploy",
                 caption="실제 배포와 정리 — 비용/권한 때문에 여기서는 명령만 안내(guide)합니다.")
    S.note_card(m, ctx_go, "실제 배포 → 확인 → 정리", [
        ("step", "실제 배포:  bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus"),
        ("info", "8단계: 사전점검 → Bicep 검증 → dry-run → 앱 빌드 → azd up → 사후설정"),
        ("warn", "azd up 부터 실제 Azure 리소스/비용 발생 — 권한·쿼터 있을 때만 진행"),
        ("step", "정리:  bash scripts/destroy.sh --env-name liveks-mcp"),
        ("bad",  "destroy 는 'delete' 입력 확인 후 azd down --purge --force 실행"),
    ], settle=3.0)
    return m


# ===========================================================================
# Chapter 6 — Verify
# ===========================================================================

def m6() -> Module:
    m = Module("06-verify")
    ctx = Ctx(6, TOTAL, "동작 확인 · Verify",
              caption="배포 후 가장 먼저 볼 파일: 생성된 deployment-summary.md.")
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
        "App URL · 엔드포인트 · KB/KS 이름이 채워졌으면 정상입니다.",
        sub="비어 있으면 azd env get-values 후 postprovision.py 재실행",
        settle=2.8,
    )

    ctx2 = Ctx(6, TOTAL, "동작 확인 · Verify",
               caption="데모 앱은 서버 라우트로 같은 trace 계약을 보여줍니다.")
    S.kv_card(m, ctx2, "데모 앱 API 라우트", [
        ("GET  /api/status", "런타임 설정(시크릿 없이)", ""),
        ("GET  /api/deployment-summary", "배포 리소스 메타데이터", ""),
        ("POST /api/retrieve/mcp", "MCP 실시간 / 오프라인 대체", ""),
        ("POST /api/retrieve/fabric", "Fabric 검색(권한 있을 때)", ""),
        ("POST /api/retrieve/combined", "두 소스 통합 라우팅", ""),
    ], settle=2.6)

    ctx_curl = Ctx(6, TOTAL, "동작 확인 · Verify",
                   caption="앱이 살아있는지 1초 점검: /api/status 를 호출합니다.",
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
            ("status 가 200 으로 JSON 을 돌려주면 앱·런타임 설정이 정상입니다.",
             "secretsExposed:false — 키는 절대 노출되지 않습니다."),
            ("searchEndpointConfigured:true 면 검색 연결까지 준비된 상태.",
             "false 면 azd env get-values 로 값이 채워졌는지 확인."),
        ],
    )
    S.zoom_term(
        m, res_curl, (E.MARGIN, 250, 1560, 430),
        "deploymentMode 와 knowledgeBase 이름이 보이면 배포 설정이 살아있는 것.",
        sub='"deploymentMode": "mcp-only"   "secretsExposed": false',
        settle=2.6, font_size=23, lh=35,
    )

    # live trace via the retrieve route — the real "is it working" proof
    ctx_ret = Ctx(6, TOTAL, "동작 확인 · Verify",
                  caption="진짜 동작 증거: retrieve 라우트가 라이브 trace 를 그대로 돌려줍니다.",
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
            ("로컬 mock 에서 본 것과 같은 activity·references·sourceData 가 라이브로 옵니다.",
             "두 소스(fabricOntology+mcpServer)가 함께 보이면 통합 라우팅 정상."),
            ("권한/네트워크 문제로 라이브가 안 되면 offlineFallback 으로 같은 형태를 반환.",
             "그래서 데모는 어떤 환경에서도 trace 형태를 보여줄 수 있습니다."),
        ],
    )
    S.zoom_term(
        m, res_ret, (E.MARGIN, 250, 1500, 360),
        "activity 에 fabricOntology + mcpServer 둘 다 — 라이브 통합의 결정적 증거.",
        sub='"type":"fabricOntology"  +  "type":"mcpServer"',
        settle=2.8, font_size=23, lh=35,
    )

    ctx3 = Ctx(6, TOTAL, "동작 확인 · Verify",
               caption="무엇을 보면 '정상'인가 — 체크리스트.")
    S.note_card(m, ctx3, "정상 동작 확인 체크리스트", [
        ("ok",   "deployment-summary.md 에 App URL·엔드포인트·KS/KB 이름이 채워짐"),
        ("ok",   "앱을 열면 query → answer → activity → references → sourceData 노출"),
        ("info", "클라우드가 없어도 오프라인 샘플로 동일한 trace 형태 확인 가능"),
        ("warn", "값이 비면: azd env get-values · python3 scripts/postprovision.py"),
    ], settle=2.8)
    return m


# ===========================================================================
# Chapter 7 — Summary
# ===========================================================================

def m7() -> Module:
    m = Module("07-summary")
    ctx = Ctx(7, TOTAL, "요약 · Summary")
    S.pipeline_card(
        m, ctx, "30초 요약 — 전체 흐름",
        steps=[
            ("CLONE", "내려받기", BLUE),
            ("LOCAL MOCK", "오프라인 체험", GREEN),
            ("TEST", "검증 13개", YELLOW),
            ("DEPLOY", "배포", ORANGE),
            ("VERIFY", "동작 확인", BLUE),
            ("CLEANUP", "정리", RED),
        ],
        footer=[
            ("최종 영상   ", "video-guide/repo-quickstart-guide.mp4"),
            ("모듈 클립   ", "video-guide/clips/01-intro … 07-summary.mp4"),
            ("재생 방법   ", "open video-guide/repo-quickstart-guide.mp4"),
        ],
        settle=3.8,
    )
    ctx_recap = Ctx(7, TOTAL, "요약 · Summary",
                    caption="산출물과 재생 방법 — 이 파일들만 기억하면 됩니다.")
    S.note_card(m, ctx_recap, "산출물 · 재생 방법", [
        ("ok",   "최종 영상: video-guide/repo-quickstart-guide.mp4 (이 영상 하나면 충분)"),
        ("info", "모듈 클립: video-guide/clips/01-intro … 07-summary.mp4"),
        ("step", "재생: open video-guide/repo-quickstart-guide.mp4"),
        ("step", "재생성: cd video-guide && python3 build_guide_video.py"),
        ("info", "실제 따라하기: README.md → validate-local.sh → deploy.sh 순서"),
    ], settle=3.6)
    S.title_card(
        m, Ctx(7, TOTAL, "요약 · Summary"),
        "따라하기 10분이면 충분합니다",
        subtitle="clone → mock → test → deploy → verify → cleanup",
        bullets=["mock 으로 먼저 이해하고, 준비되면 deploy.sh 한 줄로 라이브 전환"],
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
    args = ap.parse_args()

    keys = [k.strip() for k in args.only.split(",") if k.strip()] or list(BUILDERS)
    CLIPS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    built = []
    for k in keys:
        mod = BUILDERS[k]()
        dur = sum(d for _, d in mod.slides)
        print(f"[build] {k} -> {mod.key}  slides={len(mod.slides)}  ~{dur:0.1f}s")
        out = E.render_module(mod, WORK, CLIPS)
        built.append(out)
        print(f"        wrote {out}")

    if not args.no_final and len(built) == len(BUILDERS):
        ordered = sorted(CLIPS.glob("0*.mp4"))
        E.concat_modules(ordered, FINAL)
        print(f"[final] {FINAL}")


if __name__ == "__main__":
    main()
