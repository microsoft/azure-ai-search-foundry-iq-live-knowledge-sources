#!/usr/bin/env bash
set -Eeuo pipefail

STRICT=false
NO_COLOR="${NO_COLOR:-}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/validate-local.sh [options]

Options:
  --strict      Fail instead of skip when optional local tools such as az are missing.
  --no-color    Disable ANSI color output.
  -h, --help    Show this help.

This script performs local, non-deploying validation:
- shell syntax
- LiveKS CLI dependencies, profile schema, and safe dev container contract
- documented first-success execution contract
- Python compile
- Python contract tests
- notebook JSON parse
- GitHub issue template structure check
- Markdown local link check
- sample packaging hygiene check
- repository size check
- sample payload generation
- offline response inspection
- no-secret scan
- Static Web Apps demo build
- Bicep build when Azure CLI is available
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=true
      shift
      ;;
    --no-color)
      NO_COLOR=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -t 1 && -z "$NO_COLOR" ]]; then
  C_RESET=$'\033[0m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_BLUE=$'\033[34m'
else
  C_RESET=""
  C_GREEN=""
  C_YELLOW=""
  C_RED=""
  C_BLUE=""
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Run this script from inside the git repository." >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  venv_root="${LIVEKS_VENV:-.liveks/venv}"
  for candidate in "$venv_root/bin/python" "$venv_root/Scripts/python.exe" python3 python; do
    if [[ "$candidate" == */* ]]; then
      if [[ -x "$candidate" ]]; then
        PYTHON_BIN="$candidate"
        break
      fi
    elif command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v "$candidate")"
      break
    fi
  done
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3.11 or newer is required." >&2
  exit 2
fi

TOTAL=20
CURRENT=0
FAILED=false
SKIPPED=0

bar() {
  local done_count="$1"
  local width=24
  local filled=$(( done_count * width / TOTAL ))
  local empty=$(( width - filled ))
  printf '['
  printf '%*s' "$filled" '' | tr ' ' '#'
  printf '%*s' "$empty" '' | tr ' ' '-'
  printf '] %d/%d' "$done_count" "$TOTAL"
}

step() {
  CURRENT=$(( CURRENT + 1 ))
  printf '\n%s %s\n' "$(bar "$CURRENT")" "$1"
}

pass() {
  printf '%sPASS%s %s\n' "$C_GREEN" "$C_RESET" "$1"
}

skip() {
  SKIPPED=$(( SKIPPED + 1 ))
  printf '%sSKIP%s %s\n' "$C_YELLOW" "$C_RESET" "$1"
}

fail() {
  FAILED=true
  printf '%sFAIL%s %s\n' "$C_RED" "$C_RESET" "$1"
}

run_required() {
  local label="$1"
  shift
  step "$label"
  if "$@"; then
    pass "$label"
  else
    fail "$label"
    return 1
  fi
}

cat <<'BANNER'

+---------------------------------------------------------------+
| Foundry IQ Live Knowledge Sources                             |
| local validation                                              |
+---------------------------------------------------------------+
BANNER

run_required "Shell syntax" \
  bash -n \
    liveks \
    scripts/deploy.sh \
    scripts/e2e-test.sh \
    scripts/destroy.sh \
    scripts/postprovision.sh \
    scripts/deploy-static-webapp-api.sh \
    .devcontainer/post-create.sh \
    .devcontainer/welcome.sh \
    scripts/no-secret-scan.sh \
    scripts/fabric-e2e-test.sh \
    scripts/maintainers/create-review-packet.sh \
    scripts/maintainers/create-promotion-note.sh \
    scripts/maintainers/check-promotion-readiness.sh \
    scripts/validate-local.sh

run_required "LiveKS CLI profiles" \
  bash -c 'PYTHONPATH=src "$1" -m liveks.cli profiles --format json >/dev/null && PYTHONPATH=src "$1" scripts/generate_env_examples.py --check >/dev/null && bash -n .env.sample env/*.env.example' _ "$PYTHON_BIN"

run_required "Compatibility and documentation contract" \
  "$PYTHON_BIN" scripts/check_compatibility.py --check

run_required "Release and workflow policy contract" \
  "$PYTHON_BIN" scripts/release.py check

run_required "Scenario packs and replay cases" \
  bash -c 'PYTHONPATH=src "$1" -m liveks.scenarios validate --run-all --format json >/dev/null && PYTHONPATH=src "$1" -m liveks.scenarios catalog --check' _ "$PYTHON_BIN"

run_required "Dev container contract" \
  "$PYTHON_BIN" scripts/check-devcontainer.py

run_required "Python compile" \
  "$PYTHON_BIN" -m py_compile \
    scripts/check-doc-links.py \
    scripts/postprovision.py \
    scripts/fabric-provision.py \
    scripts/fabric-destroy.py \
    scripts/check-sample-hygiene.py \
    scripts/check-repo-size.py \
    scripts/check-devcontainer.py \
    scripts/ensure_azd_defaults.py \
    scripts/azd_postprovision.py \
    scripts/deploy_static_webapp_api.py \
    scripts/generate_env_examples.py \
    scripts/check_compatibility.py \
    scripts/release.py \
    scripts/protected_canary.py \
    scripts/maintainers/summarize-e2e-evidence.py \
    scripts/maintainers/extract-review-evidence.py \
    tools/validate.py \
    tools/doctor.py \
    tools/try_offline.py \
    tools/scenarios.py \
    samples/python/build_payloads.py \
    samples/python/inspect_retrieve_response.py \
    src/liveks/runtime.py \
    src/liveks/compatibility.py \
    src/liveks/evidence.py \
    src/liveks/canary.py \
    src/liveks/search_index.py \
    src/liveks/mcp_search_index.py \
    src/liveks/scenarios.py \
    src/liveks/cli.py

run_required "Python contract tests" \
  "$PYTHON_BIN" -m unittest discover -s tests

run_required "Notebook JSON parse" \
  "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

for path in sorted(Path("notebooks").glob("*.ipynb")):
    json.loads(path.read_text(encoding="utf-8"))
    print(f"ok {path}")
PY

run_required "GitHub issue template structure" \
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path

paths = sorted(Path(".github/ISSUE_TEMPLATE").glob("*.yml"))
paths += sorted(Path(".github/ISSUE_TEMPLATE").glob("*.yaml"))
for path in paths:
    text = path.read_text(encoding="utf-8")
    if "\t" in text:
        raise SystemExit(f"{path}: tabs are not allowed in GitHub issue templates")
    if path.name != "config.yml":
        required = ("name:", "description:", "title:", "body:")
        missing = [key for key in required if key not in text]
        if missing:
            raise SystemExit(f"{path}: missing required keys: {', '.join(missing)}")
    print(f"ok {path}")
PY

run_required "Markdown links" \
  "$PYTHON_BIN" scripts/check-doc-links.py

run_required "Sample packaging hygiene" \
  "$PYTHON_BIN" scripts/check-sample-hygiene.py

run_required "Repository size hygiene" \
  "$PYTHON_BIN" scripts/check-repo-size.py

run_required "Documented first-success contract" \
  ./liveks try --evidence-out .deployment/first-run-evidence.json

run_required "Sample payload generation" \
  bash -c '"$1" samples/python/build_payloads.py >/dev/null' _ "$PYTHON_BIN"

step "Offline response inspection"
for response in samples/responses/*.json; do
  "$PYTHON_BIN" samples/python/inspect_retrieve_response.py "$response" >/dev/null
done
pass "Offline response inspection"

run_required "No-secret scan" \
  bash scripts/no-secret-scan.sh

step "Static app dependencies"
if [[ -d static-app/node_modules ]]; then
  pass "Static app dependencies already installed"
else
  npm --prefix static-app ci
  pass "Static app dependencies installed"
fi

run_required "Static app build" \
  npm --prefix static-app run build

step "Bicep build"
if command -v az >/dev/null 2>&1; then
  mkdir -p .deployment
  if az bicep build --file infra/main.bicep --outfile .deployment/main.bicep.validate.json; then
    pass "Bicep build"
  else
    fail "Bicep build"
  fi
elif [[ "$STRICT" == "true" ]]; then
  fail "Azure CLI is required for Bicep build in --strict mode"
else
  skip "Azure CLI not found; Bicep build skipped"
fi

printf '\n%s\n' "$(bar "$CURRENT")"
if [[ "$FAILED" == "true" ]]; then
  printf '%sLocal validation: FAIL%s\n' "$C_RED" "$C_RESET"
  exit 1
fi

if [[ "$SKIPPED" -gt 0 ]]; then
  printf '%sLocal validation: PASS with %d skipped check(s)%s\n' "$C_YELLOW" "$SKIPPED" "$C_RESET"
else
  printf '%sLocal validation: PASS%s\n' "$C_GREEN" "$C_RESET"
fi
