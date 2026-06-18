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
- Python compile
- notebook JSON parse
- Markdown local link check
- sample payload generation
- offline response inspection
- no-secret scan
- Static Web Apps demo build
- optional Next.js demo app build
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

TOTAL=12
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
    scripts/deploy.sh \
    scripts/e2e-test.sh \
    scripts/destroy.sh \
    scripts/postprovision.sh \
    scripts/deploy-static-webapp-api.sh \
    scripts/no-secret-scan.sh \
    scripts/fabric-e2e-test.sh \
    scripts/create-review-packet.sh \
    scripts/validate-local.sh

run_required "Python compile" \
  python3 -m py_compile \
    scripts/check-doc-links.py \
    scripts/postprovision.py \
    scripts/fabric-provision.py \
    scripts/fabric-destroy.py \
    samples/python/build_payloads.py \
    samples/python/inspect_retrieve_response.py

run_required "Notebook JSON parse" \
  python3 - <<'PY'
import json
from pathlib import Path

for path in sorted(Path("notebooks").glob("*.ipynb")):
    json.loads(path.read_text(encoding="utf-8"))
    print(f"ok {path}")
PY

run_required "Markdown links" \
  python3 scripts/check-doc-links.py

run_required "Sample payload generation" \
  bash -c 'python3 samples/python/build_payloads.py >/dev/null'

step "Offline response inspection"
for response in samples/responses/*.json; do
  python3 samples/python/inspect_retrieve_response.py "$response" >/dev/null
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

step "Demo app dependencies"
if [[ -d demo-app/node_modules ]]; then
  pass "Demo app dependencies already installed"
else
  npm --prefix demo-app ci
  pass "Demo app dependencies installed"
fi

run_required "Demo app build" \
  npm --prefix demo-app run build

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
