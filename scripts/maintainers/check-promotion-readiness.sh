#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_REMOTE="microsoft"
RUN_VALIDATION=false
REVIEW_PACKET=""
PROMOTION_NOTE=""
NO_COLOR="${NO_COLOR:-}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/maintainers/check-promotion-readiness.sh [options]

Options:
  --target-remote <name>   Target organization remote to inspect. Default: microsoft
  --review-packet <path>   Optional local ignored review packet to verify.
  --promotion-note <path>  Optional local ignored promotion note to verify.
  --run-validation         Run local validation, no-secret scan, and whitespace checks.
                           Without this flag, the script reports commands to run.
  --no-color               Disable ANSI color output.
  -h, --help               Show this help.

This script is a non-pushing preflight for Microsoft org or target-org review.
It does not modify remotes, create commits, or push branches.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-remote)
      TARGET_REMOTE="${2:-}"
      shift 2
      ;;
    --review-packet)
      REVIEW_PACKET="${2:-}"
      shift 2
      ;;
    --promotion-note)
      PROMOTION_NOTE="${2:-}"
      shift 2
      ;;
    --run-validation)
      RUN_VALIDATION=true
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
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_RESET=$'\033[0m'
else
  C_GREEN=""
  C_YELLOW=""
  C_RED=""
  C_RESET=""
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Run this script from inside the git repository." >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"

FAILURES=0
WARNINGS=0

pass() {
  printf '%sPASS%s %s\n' "$C_GREEN" "$C_RESET" "$1"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf '%sWARN%s %s\n' "$C_YELLOW" "$C_RESET" "$1"
}

fail() {
  FAILURES=$((FAILURES + 1))
  printf '%sFAIL%s %s\n' "$C_RED" "$C_RESET" "$1"
}

info() {
  printf 'INFO %s\n' "$1"
}

run_check() {
  local label="$1"
  shift
  if "$@"; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_local_artifact() {
  local label="$1"
  local path="$2"
  local commit="$3"

  if [[ -z "$path" ]]; then
    info "${label} was not provided; skipped local artifact freshness check."
    return
  fi

  if [[ -f "$path" ]]; then
    pass "${label} exists: ${path}"
  else
    fail "${label} was provided but does not exist: ${path}"
    return
  fi

  if git check-ignore -q "$path" 2>/dev/null; then
    pass "${label} is ignored by git."
  else
    fail "${label} is not ignored by git: ${path}"
  fi

  if grep -q "$commit" "$path"; then
    pass "${label} references current commit ${commit}."
  else
    fail "${label} does not reference current commit ${commit}. Regenerate it after the latest source commit."
  fi
}

cat <<'BANNER'

+---------------------------------------------------------------+
| Foundry IQ Live Knowledge Sources                             |
| promotion readiness preflight                                 |
+---------------------------------------------------------------+
BANNER

branch="$(git branch --show-current 2>/dev/null || true)"
commit="$(git rev-parse --short HEAD)"
origin_url="$(git remote get-url origin 2>/dev/null || true)"
target_url="$(git remote get-url "$TARGET_REMOTE" 2>/dev/null || true)"

info "Branch: ${branch:-unknown}"
info "Commit: ${commit}"
info "Origin: ${origin_url:-not configured}"
info "Target remote (${TARGET_REMOTE}): ${target_url:-not configured}"

if [[ -z "$branch" ]]; then
  fail "Current branch is detached or unknown."
else
  pass "Current branch detected: ${branch}"
fi

if [[ -z "$target_url" ]]; then
  fail "Target remote '${TARGET_REMOTE}' is not configured."
elif [[ "$TARGET_REMOTE" == "origin" ]]; then
  fail "Target remote should not be origin for org promotion."
else
  pass "Target remote '${TARGET_REMOTE}' is configured."
fi

if [[ -n "$(git status --short --untracked-files=no)" ]]; then
  fail "Tracked worktree changes are present. Commit or discard intentional changes before promotion."
else
  pass "No tracked worktree changes."
fi

untracked="$(git ls-files --others --exclude-standard)"
if [[ -n "$untracked" ]]; then
  warn "Untracked non-ignored files exist. Review before promotion."
  printf '%s\n' "$untracked" | sed 's/^/  - /'
else
  pass "No untracked non-ignored files."
fi

ignored_paths=(
  ".env"
  ".env.external.local"
  ".deployment/main.bicep.validate.json"
  "deployments"
  "scratch"
)
for path in "${ignored_paths[@]}"; do
  if git check-ignore -q "$path" 2>/dev/null; then
    pass "Ignored path is protected: ${path}"
  else
    fail "Expected ignored path is not protected: ${path}"
  fi
done

check_local_artifact "Review packet" "$REVIEW_PACKET" "$commit"
check_local_artifact "Promotion note" "$PROMOTION_NOTE" "$commit"

if [[ "$RUN_VALIDATION" == "true" ]]; then
  run_check "Local validation" bash scripts/validate-local.sh --no-color
  run_check "No-secret scan" bash scripts/no-secret-scan.sh
  run_check "Whitespace diff check" git diff --check
else
  warn "Local validation was not run. Use --run-validation before promotion."
  info "Run: bash scripts/validate-local.sh"
  info "Run: bash scripts/no-secret-scan.sh"
  info "Run: git diff --check"
fi

if command -v gh >/dev/null 2>&1 && [[ -n "$origin_url" ]]; then
  commit_full="$(git rev-parse HEAD)"
  gh_json="$(gh run list --workflow Validate --limit 10 --json conclusion,headSha,status,url,name 2>/dev/null || true)"
  if [[ -n "$gh_json" ]]; then
    actions_summary="$(GH_JSON="$gh_json" HEAD_SHA="$commit_full" python3 - <<'PY'
import json
import os

runs = json.loads(os.environ["GH_JSON"])
head = os.environ["HEAD_SHA"]
for run in runs:
    if run.get("headSha") == head:
        print(f"{run.get('status', 'unknown')}|{run.get('conclusion') or 'pending'}|{run.get('url', '')}")
        break
else:
    print("not-found||")
PY
)"
    IFS='|' read -r actions_status actions_conclusion actions_url <<< "$actions_summary"
    if [[ "$actions_status" == "completed" && "$actions_conclusion" == "success" ]]; then
      pass "GitHub Actions Validate is green for current commit."
      info "Actions URL: ${actions_url}"
    elif [[ "$actions_status" == "not-found" ]]; then
      warn "No GitHub Actions Validate run found for current commit."
    else
      fail "GitHub Actions Validate is not green for current commit: ${actions_status}/${actions_conclusion}"
      [[ -n "$actions_url" ]] && info "Actions URL: ${actions_url}"
    fi
  else
    warn "Could not query GitHub Actions Validate runs."
  fi
else
  warn "gh CLI unavailable or origin missing; skipped GitHub Actions check."
fi

cat <<EOF

Manual promotion commands, only after PASS:

  git status -sb
  git remote get-url ${TARGET_REMOTE}
  bash scripts/maintainers/check-promotion-readiness.sh --target-remote ${TARGET_REMOTE} --run-validation --review-packet <packet.local.md> --promotion-note <promotion-note.local.md>
  git push ${TARGET_REMOTE} ${branch:-main}:review/live-knowledge-sources

Do not push raw deployment reports, .env files, scratch notes, local screenshots,
or private tenant artifacts. Prefer a review branch unless maintainers explicitly
ask for a direct main seed.
EOF

if [[ "$FAILURES" -gt 0 ]]; then
  printf '\n%sPromotion readiness: FAIL%s (%d failure(s), %d warning(s))\n' "$C_RED" "$C_RESET" "$FAILURES" "$WARNINGS"
  exit 1
fi

if [[ "$WARNINGS" -gt 0 ]]; then
  printf '\n%sPromotion readiness: PASS with warnings%s (%d warning(s))\n' "$C_YELLOW" "$C_RESET" "$WARNINGS"
  exit 0
fi

printf '\n%sPromotion readiness: PASS%s\n' "$C_GREEN" "$C_RESET"
