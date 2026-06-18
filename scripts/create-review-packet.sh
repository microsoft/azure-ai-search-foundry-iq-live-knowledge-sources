#!/usr/bin/env bash
set -Eeuo pipefail

MODE=""
INTENT="private review"
E2E_REPORT=""
OUTPUT=""
RUN_LOCAL_VALIDATION=false
LOCAL_VALIDATION_LOG=""
NO_COLOR="${NO_COLOR:-}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/create-review-packet.sh [options]

Options:
  --mode <mode>          Deployment mode reviewed.
                         Values: mcp-only, byo-fabric, full
  --intent <text>        Review intent. Default: private review
  --e2e-report <path>    Ignored local E2E report path to reference.
                         The script records only the path, not report contents.
  --run-local-validation Run bash scripts/validate-local.sh --no-color and record
                         only PASS/FAIL and the ignored log path in the packet.
  --output <path>        Output markdown path.
                         Default: scratch/review-packets/review-packet-<timestamp>.local.md
  --no-color             Disable ANSI color output.
  -h, --help             Show this help.

The generated packet is a local ignored markdown file. It should be reviewed,
sanitized, and summarized before copying anything into a PR, blog draft, or
review email.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --intent)
      INTENT="${2:-}"
      shift 2
      ;;
    --e2e-report)
      E2E_REPORT="${2:-}"
      shift 2
      ;;
    --run-local-validation)
      RUN_LOCAL_VALIDATION=true
      shift
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
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

case "$MODE" in
  ""|mcp-only|byo-fabric|full)
    ;;
  *)
    echo "Invalid --mode: $MODE. Allowed values: mcp-only, byo-fabric, full." >&2
    exit 2
    ;;
esac

if [[ -t 1 && -z "$NO_COLOR" ]]; then
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RESET=$'\033[0m'
else
  C_GREEN=""
  C_YELLOW=""
  C_RESET=""
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Run this script from inside the git repository." >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"

timestamp="$(date +%Y%m%d-%H%M%S)"
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="scratch/review-packets/review-packet-${timestamp}.local.md"
fi
mkdir -p "$(dirname "$OUTPUT")"

local_validation_result="not run"
if [[ "$RUN_LOCAL_VALIDATION" == "true" ]]; then
  mkdir -p .deployment
  LOCAL_VALIDATION_LOG=".deployment/review-packet-validation-${timestamp}.log"
  printf '%sRunning local validation:%s bash scripts/validate-local.sh --no-color\n' "$C_YELLOW" "$C_RESET"
  set +e
  bash scripts/validate-local.sh --no-color >"$LOCAL_VALIDATION_LOG" 2>&1
  validation_status=$?
  set -e

  if [[ "$validation_status" -eq 0 ]] && grep -q "Local validation: PASS" "$LOCAL_VALIDATION_LOG"; then
    local_validation_result="PASS"
  else
    local_validation_result="FAIL"
  fi
fi

branch="$(git branch --show-current 2>/dev/null || true)"
commit="$(git rev-parse --short HEAD)"
commit_full="$(git rev-parse HEAD)"
origin_url="$(git remote get-url origin 2>/dev/null || true)"
target_url="$(git remote get-url microsoft 2>/dev/null || git remote get-url target 2>/dev/null || true)"

if [[ -n "$(git status --short --untracked-files=no)" ]]; then
  worktree_state="dirty tracked changes present"
else
  worktree_state="clean"
fi

mode_label="${MODE:-not selected}"
e2e_label="${E2E_REPORT:-not provided}"
e2e_state="not checked"
if [[ -n "$E2E_REPORT" ]]; then
  if [[ -f "$E2E_REPORT" ]]; then
    e2e_state="local report path exists; contents intentionally not copied"
  else
    e2e_state="local report path was provided but file was not found"
  fi
fi

actions_result="not checked"
actions_url=""
if command -v gh >/dev/null 2>&1 && [[ -n "$origin_url" ]]; then
  gh_json="$(gh run list --workflow Validate --limit 10 --json conclusion,headSha,status,url,name 2>/dev/null || true)"
  if [[ -n "$gh_json" ]]; then
    actions_result="$(GH_JSON="$gh_json" HEAD_SHA="$commit_full" python3 - <<'PY'
import json
import os

runs = json.loads(os.environ["GH_JSON"])
head = os.environ["HEAD_SHA"]
for run in runs:
    if run.get("headSha") == head:
        print(f"{run.get('status', 'unknown')} / {run.get('conclusion') or 'pending'}")
        break
else:
    print("not found for current commit")
PY
)"
    actions_url="$(GH_JSON="$gh_json" HEAD_SHA="$commit_full" python3 - <<'PY'
import json
import os

runs = json.loads(os.environ["GH_JSON"])
head = os.environ["HEAD_SHA"]
for run in runs:
    if run.get("headSha") == head:
        print(run.get("url", ""))
        break
PY
)"
  fi
fi

cat > "$OUTPUT" <<EOF
# Review Packet

Generated: $(date '+%Y-%m-%d %H:%M %Z')

> Local ignored review packet. Do not commit this file. Copy only sanitized facts into PRs, reviewer emails, blog drafts, or presentation notes.

## Review Scope

- Repo/branch: \`${branch:-unknown}\`
- Commit: \`${commit}\`
- Origin: \`${origin_url:-not configured}\`
- Target org remote: \`${target_url:-not configured}\`
- Deployment mode reviewed: \`${mode_label}\`
- Review intent: ${INTENT}
- Worktree state when generated: ${worktree_state}

## Validation

- Local validation: ${local_validation_result}
- Local validation log, local only: \`${LOCAL_VALIDATION_LOG:-not generated}\`
- GitHub Actions Validate: ${actions_result}
- GitHub Actions URL: ${actions_url:-not available}
- E2E report path, local only: \`${e2e_label}\`
- E2E report status: ${e2e_state}
- Cleanup: PASS / FAIL / skipped, with reason

## Evidence Summary

- MCP KS:
- Fabric KS:
- Knowledge Base:
- Retrieve evidence:
- App load:
- Offline replay used: yes/no, with reason

## Known Caveats

- Preview API:
- Fabric quota or tenant settings:
- Delegated auth/token:
- Region/model availability:

## Reviewer Asks

- Azure AI Search Knowledge Source terminology and REST shape
- MCP Server KS request/response shape and trace wording
- Fabric Ontology KS setup and delegated source authorization wording
- Deployment-mode clarity: \`mcp-only\`, \`byo-fabric\`, \`full\`
- Public-preview caveats and safe claims
- Security posture for generated outputs and tokens

## Do Not Include

- API keys
- bearer tokens
- tenant-specific IDs
- customer data
- private endpoints or service URLs from generated reports
- raw deployment reports
- local screenshots with sensitive values

## Helpful Links

- [Reviewer Evidence Guide](../../docs/12-reviewer-evidence.md)
- [Public Preview Limitations and Caveats](../../docs/13-public-preview-limitations.md)
- [Storyline And Safe Claims](../../docs/17-storyline-and-safe-claims.md)
- [Repository Promotion Guide](../../docs/15-repository-promotion.md)
EOF

printf '%sReview packet written:%s %s\n' "$C_GREEN" "$C_RESET" "$OUTPUT"
printf '%sReminder:%s keep this local file ignored and copy only sanitized facts.\n' "$C_YELLOW" "$C_RESET"
