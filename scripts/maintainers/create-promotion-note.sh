#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_REMOTE="microsoft"
REVIEW_PACKET=""
E2E_SUMMARY=""
OUTPUT=""
NO_COLOR="${NO_COLOR:-}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/maintainers/create-promotion-note.sh [options]

Options:
  --target-remote <name>  Target organization remote. Default: microsoft
  --review-packet <path>  Ignored local review packet path to reference.
  --e2e-summary <path>    Ignored sanitized E2E summary path to reference.
  --output <path>         Output markdown path.
                          Default: scratch/review-packets/promotion-note-<timestamp>.local.md
  --no-color              Disable ANSI color output.
  -h, --help              Show this help.

This script writes a local-only promotion note for target organization review.
It never pushes, changes remotes, or copies raw deployment report contents.
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
    --e2e-summary)
      E2E_SUMMARY="${2:-}"
      shift 2
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
  OUTPUT="scratch/review-packets/promotion-note-${timestamp}.local.md"
fi
mkdir -p "$(dirname "$OUTPUT")"

branch="$(git branch --show-current 2>/dev/null || true)"
commit="$(git rev-parse --short HEAD)"
commit_full="$(git rev-parse HEAD)"
origin_url="$(git remote get-url origin 2>/dev/null || true)"
target_url="$(git remote get-url "$TARGET_REMOTE" 2>/dev/null || true)"

if [[ -n "$(git status --short --untracked-files=no)" ]]; then
  worktree_state="dirty tracked changes present"
else
  worktree_state="clean"
fi

review_packet_status="not provided"
if [[ -n "$REVIEW_PACKET" ]]; then
  if [[ -f "$REVIEW_PACKET" ]]; then
    review_packet_status="provided; local file exists"
  else
    review_packet_status="provided but file was not found"
  fi
fi

e2e_summary_status="not provided"
if [[ -n "$E2E_SUMMARY" ]]; then
  if [[ -f "$E2E_SUMMARY" ]]; then
    e2e_summary_status="provided; sanitized local file exists"
  else
    e2e_summary_status="provided but file was not found"
  fi
fi

actions_result="not checked"
actions_url=""
if command -v gh >/dev/null 2>&1 && [[ -n "$origin_url" ]]; then
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
    print("not found for current commit||")
PY
)"
    IFS='|' read -r actions_result actions_conclusion actions_url <<< "$actions_summary"
    if [[ -n "${actions_conclusion:-}" ]]; then
      actions_result="${actions_result} / ${actions_conclusion}"
    fi
  fi
fi

push_branch="${branch:-main}"
review_branch="review/live-knowledge-sources"

cat > "$OUTPUT" <<EOF
# Promotion Note

Generated: $(date '+%Y-%m-%d %H:%M %Z')

> Local ignored promotion note. Do not commit this file. It is a handoff aid for target organization private review.

## Current Source

- Source branch: \`${branch:-unknown}\`
- Source commit: \`${commit}\`
- Worktree state: ${worktree_state}
- Origin remote: \`${origin_url:-not configured}\`
- Target remote name: \`${TARGET_REMOTE}\`
- Target remote URL: \`${target_url:-not configured}\`
- GitHub Actions Validate: ${actions_result}
- GitHub Actions URL: ${actions_url:-not available}

## Local Evidence References

- Review packet: \`${REVIEW_PACKET:-not provided}\`
- Review packet status: ${review_packet_status}
- Sanitized E2E summary: \`${E2E_SUMMARY:-not provided}\`
- Sanitized E2E summary status: ${e2e_summary_status}

These paths are local and ignored. Do not paste raw deployment reports, app URLs, Search endpoints, resource group names, subscription IDs, tenant IDs, tokens, keys, or private screenshots into a PR or reviewer message.

## Required Preflight Before Push

Run:

\`\`\`bash
git status -sb
bash scripts/maintainers/check-promotion-readiness.sh \\
  --target-remote ${TARGET_REMOTE} \\
  --run-validation \\
  --review-packet ${REVIEW_PACKET:-<packet.local.md>} \\
  --promotion-note ${OUTPUT}
\`\`\`

Expected:

\`\`\`text
Promotion readiness: PASS
\`\`\`

If it reports warnings, review them before pushing. If it reports failures, do not push.

## Manual Promotion Command

Only after the preflight passes and the target remote is confirmed:

\`\`\`bash
git push ${TARGET_REMOTE} ${push_branch}:${review_branch}
\`\`\`

Use a review branch first unless the maintainers explicitly ask for direct \`main\` seeding.

## Reviewer Message Draft

\`\`\`text
Hi team,

I have a private-review candidate for the Azure AI Search Foundry IQ Live Knowledge Sources sample accelerator.

Scope:
- Two public preview Knowledge Source paths: MCP Server KS and Fabric Ontology KS
- Three deployment modes: mcp-only, byo-fabric, full
- Demo app, notebooks, REST samples, synthetic Airline Ops data, offline replay, validation workflow, and E2E evidence workflow

Current evidence:
- Commit: ${commit}
- Local validation: <paste promotion readiness preflight result>
- GitHub Actions Validate: ${actions_result}
- Sanitized E2E evidence summary: ${E2E_SUMMARY:-not provided}
- Local review packet: ${REVIEW_PACKET:-not provided}

Reviewer asks:
- Azure AI Search Knowledge Source terminology and REST shape
- MCP Server KS request/response shape and trace wording
- Fabric Ontology KS setup and delegated source authorization wording
- Deployment-mode clarity: mcp-only, byo-fabric, full
- Public-preview caveats and safe claims
- Security posture for generated outputs and tokens

Suggested routing:
- Azure AI Search / Knowledge Source: KS/KB REST shape, API version, retrieve trace wording
- Fabric / Ontology: workspace and ontology prerequisites, delegated source authorization, full-mode Fabric setup language
- Field / workshop owner: first-five-minutes flow, notebooks, offline replay, failure fallback story
- Security / release hygiene: ignored generated outputs, env handling, no-secret posture, synthetic data boundary
- Blog / presentation reviewer: claims vs evidence, screenshots, architecture wording, customer-safe phrasing

Notes:
- No customer data or tenant-specific values are included in tracked files.
- Generated deployment reports, local env files, and screenshots remain ignored.
- This is review-only and not a public release request.
\`\`\`

## Final Human Checklist

\`\`\`text
[ ] Worktree clean
[ ] Promotion readiness preflight PASS
[ ] GitHub Actions Validate PASS for current source commit
[ ] Local review packet regenerated from current commit
[ ] Sanitized E2E summary available if deployment claims are included
[ ] Target remote URL manually confirmed
[ ] Review branch push used instead of direct main push
[ ] Reviewer message includes only sanitized facts
\`\`\`
EOF

printf '%sPromotion note written:%s %s\n' "$C_GREEN" "$C_RESET" "$OUTPUT"
printf '%sReminder:%s this script never pushes. Run the preflight before any target-org push.\n' "$C_YELLOW" "$C_RESET"
