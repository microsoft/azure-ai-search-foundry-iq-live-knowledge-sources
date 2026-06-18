#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE=""
ENV_NAME="ext-liveks-e2e-20260616"
LOCATION="eastus"
FABRIC_LOCATION=""
DEPLOYMENT_MODE="byo-fabric"
CLEANUP=false
KEEP_RESOURCES=false
NO_COLOR="${NO_COLOR:-}"
export AZD_SKIP_FIRST_RUN="${AZD_SKIP_FIRST_RUN:-true}"
LOG_DIR=".deployment"
LOG_FILE=""
REPORT_PATH=""
EXPECTED_SUBSCRIPTION_NAME="${EXPECTED_SUBSCRIPTION_NAME:-}"
EXPECTED_TENANT_ID="${EXPECTED_TENANT_ID:-}"
APP_URL=""
SEARCH_ENDPOINT=""
RESOURCE_GROUP=""
SEARCH_SERVICE_NAME=""
HOSTING_MODE=""
STATIC_WEB_APP_LOCATION=""
STATIC_WEB_APP_NAME=""
WEBAPP_NAME=""
STORAGE_ACCOUNT_NAME=""
OPENAI_ENDPOINT=""
OPENAI_ACCOUNT_NAME=""
FAILED=false
CLEANUP_STARTED=false

CHECK_IDS=(
  "external_login"
  "subscription"
  "tools"
  "bicep"
  "postprovision_dry_run"
  "npm_ci"
  "app_build"
  "azd_up"
  "resource_group"
  "azure_resources"
  "deployment_summary"
  "mcp_ks"
  "fabric_ks"
  "mcp_kb"
  "combined_kb"
  "airline_index"
  "mcp_retrieve"
  "fabric_live_retrieve"
  "app_http_200"
  "api_status"
  "api_mcp"
  "api_fabric"
  "api_combined"
  "cleanup"
  "resource_group_deleted"
)

CHECK_LABELS=(
  "External tenant login is active"
  "Expected subscription is selected"
  "Required local tools are available"
  "Bicep template builds"
  "postprovision dry-run passes"
  "static demo app dependencies install"
  "static demo app builds"
  "azd up completes"
  "Resource group exists"
  "Azure resources exist"
  "Deployment summary exists"
  "Microsoft Learn MCP Knowledge Source exists"
  "Fabric Ontology Knowledge Source exists when configured"
  "MCP-only Knowledge Base exists"
  "Combined Knowledge Base exists"
  "Airline Ops Search index exists and has documents"
  "MCP retrieve returns activity/reference evidence"
  "Fabric live retrieve returns ontology activity when token is provided"
  "Demo app root returns HTTP 200"
  "GET /api/status returns non-secret config"
  "POST /api/retrieve/mcp works"
  "POST /api/retrieve/fabric returns expected offline/live response"
  "POST /api/retrieve/combined returns expected offline/live response"
  "destroy.sh cleanup completes"
  "Resource group is deleted or not found"
)

CHECK_STATUS=()
CHECK_NOTES=()

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/e2e-test.sh --env-file .env.external.local --cleanup [options]

Options:
  --mode <mode>          Deployment mode. Default: byo-fabric
                         Values: byo-fabric, mcp-only, full
  --env-file <path>      Load local env settings, including isolated Azure CLI profile.
  --env-name <name>      azd environment name. Default: ext-liveks-e2e-20260616
  --location <region>    Azure region. Default: eastus
  --fabric-location <region>
                         Fabric capacity region for --mode full. Example: westus3
  --cleanup              Run destroy.sh after tests and verify resource deletion.
  --keep-resources       Leave Azure resources after tests. Explicit opt-out from cleanup.
  --no-color             Disable ANSI color output.
  -h, --help             Show this help.

Default test command:
  bash scripts/e2e-test.sh \
    --mode byo-fabric \
    --env-file .env.external.local \
    --env-name ext-liveks-e2e-20260616 \
    --location eastus \
    --cleanup
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      DEPLOYMENT_MODE="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --env-name)
      ENV_NAME="${2:-}"
      shift 2
      ;;
    --location)
      LOCATION="${2:-}"
      shift 2
      ;;
    --fabric-location)
      FABRIC_LOCATION="${2:-}"
      shift 2
      ;;
    --cleanup)
      CLEANUP=true
      shift
      ;;
    --keep-resources)
      KEEP_RESOURCES=true
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

if [[ "$CLEANUP" == "true" && "$KEEP_RESOURCES" == "true" ]]; then
  echo "Choose either --cleanup or --keep-resources, not both." >&2
  exit 2
fi

case "$DEPLOYMENT_MODE" in
  byo-fabric|mcp-only|full) ;;
  *)
    echo "Invalid --mode: $DEPLOYMENT_MODE. Allowed values: byo-fabric, mcp-only, full." >&2
    exit 2
    ;;
esac

if [[ "$CLEANUP" != "true" && "$KEEP_RESOURCES" != "true" ]]; then
  echo "Pass --cleanup for full lifecycle validation or --keep-resources for debugging." >&2
  exit 2
fi

if [[ -t 1 && -z "$NO_COLOR" ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_BLUE=$'\033[34m'
else
  C_RESET=""
  C_BOLD=""
  C_DIM=""
  C_GREEN=""
  C_YELLOW=""
  C_RED=""
  C_BLUE=""
fi

for _id in "${CHECK_IDS[@]}"; do
  CHECK_STATUS+=("PENDING")
  CHECK_NOTES+=("")
done

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/e2e-${ENV_NAME}-$(date +%Y%m%d-%H%M%S).log"
REPORT_PATH="deployments/${ENV_NAME}/test-report.md"
mkdir -p "$(dirname "$REPORT_PATH")"

log() {
  printf '%s\n' "$*" | tee -a "$LOG_FILE"
}

plain_log() {
  printf '%s\n' "$*" >> "$LOG_FILE"
}

bar_for() {
  local done_count="$1"
  local total="$2"
  local width=28
  local filled=$(( done_count * width / total ))
  local empty=$(( width - filled ))
  printf '['
  printf '%*s' "$filled" '' | tr ' ' '#'
  printf '%*s' "$empty" '' | tr ' ' '-'
  printf '] %d/%d' "$done_count" "$total"
}

status_icon() {
  case "$1" in
    PASS) printf 'PASS' ;;
    FAIL) printf 'FAIL' ;;
    SKIP) printf 'SKIP' ;;
    RUNNING) printf 'RUNNING' ;;
    *) printf 'PENDING' ;;
  esac
}

check_index() {
  local id="$1"
  local i
  for (( i=0; i<${#CHECK_IDS[@]}; i++ )); do
    if [[ "${CHECK_IDS[$i]}" == "$id" ]]; then
      printf '%s' "$i"
      return 0
    fi
  done
  echo "Unknown check id: $id" >&2
  exit 2
}

set_check() {
  local id="$1"
  local status="$2"
  local note="${3:-}"
  local i
  i="$(check_index "$id")"
  CHECK_STATUS[$i]="$status"
  CHECK_NOTES[$i]="$note"
  write_report
  print_progress "$id" "$status" "$note"
}

completed_count() {
  local count=0
  local status
  for status in "${CHECK_STATUS[@]}"; do
    case "$status" in
      PASS|FAIL|SKIP) count=$(( count + 1 )) ;;
    esac
  done
  printf '%s' "$count"
}

pass_count() {
  local count=0
  local status
  for status in "${CHECK_STATUS[@]}"; do
    [[ "$status" == "PASS" ]] && count=$(( count + 1 ))
  done
  printf '%s' "$count"
}

fail_count() {
  local count=0
  local status
  for status in "${CHECK_STATUS[@]}"; do
    [[ "$status" == "FAIL" ]] && count=$(( count + 1 ))
  done
  printf '%s' "$count"
}

escape_md() {
  printf '%s' "$1" | tr '\n' ' ' | sed 's/|/\\|/g'
}

write_report() {
  local completed total pass fail progress now
  completed="$(completed_count)"
  total="${#CHECK_IDS[@]}"
  pass="$(pass_count)"
  fail="$(fail_count)"
  progress="$(bar_for "$completed" "$total")"
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  {
    printf '# Live E2E Test Report\n\n'
    printf 'Generated by `scripts/e2e-test.sh`. This file is ignored by git.\n\n'
    printf '## Run\n\n'
    printf -- '- Environment: `%s`\n' "$ENV_NAME"
    printf -- '- Deployment mode: `%s`\n' "$DEPLOYMENT_MODE"
    printf -- '- Location: `%s`\n' "$LOCATION"
    [[ -n "$FABRIC_LOCATION" ]] && printf -- '- Fabric location: `%s`\n' "$FABRIC_LOCATION"
    printf -- '- Cleanup requested: `%s`\n' "$CLEANUP"
    printf -- '- Generated: `%s`\n' "$now"
    printf -- '- Log file: `%s`\n' "$LOG_FILE"
    [[ -n "$RESOURCE_GROUP" ]] && printf -- '- Resource group: `%s`\n' "$RESOURCE_GROUP"
    [[ -n "$HOSTING_MODE" ]] && printf -- '- Hosting mode: `%s`\n' "$HOSTING_MODE"
    [[ -n "$STATIC_WEB_APP_LOCATION" ]] && printf -- '- Static Web Apps region: `%s`\n' "$STATIC_WEB_APP_LOCATION"
    [[ -n "$STATIC_WEB_APP_NAME" ]] && printf -- '- Static Web App: `%s`\n' "$STATIC_WEB_APP_NAME"
    [[ -n "$WEBAPP_NAME" ]] && printf -- '- App Service: `%s`\n' "$WEBAPP_NAME"
    [[ -n "$APP_URL" ]] && printf -- '- App URL: `%s`\n' "$APP_URL"
    [[ -n "$SEARCH_ENDPOINT" ]] && printf -- '- Search endpoint: `%s`\n' "$SEARCH_ENDPOINT"
    printf '\n## Progress\n\n'
    printf '`%s`\n\n' "$progress"
    printf -- '- Passed: `%s`\n' "$pass"
    printf -- '- Failed: `%s`\n' "$fail"
    printf -- '- Completed: `%s/%s`\n\n' "$completed" "$total"
    printf '## Checklist\n\n'
    printf '| Status | Check | Notes |\n'
    printf '| --- | --- | --- |\n'
    local i
    for (( i=0; i<${#CHECK_IDS[@]}; i++ )); do
      printf '| `%s` | %s | %s |\n' "$(status_icon "${CHECK_STATUS[$i]}")" "${CHECK_LABELS[$i]}" "$(escape_md "${CHECK_NOTES[$i]}")"
    done
  } > "$REPORT_PATH"
}

print_progress() {
  local id="$1"
  local status="$2"
  local note="${3:-}"
  local completed total
  completed="$(completed_count)"
  total="${#CHECK_IDS[@]}"
  local color="$C_BLUE"
  [[ "$status" == "PASS" ]] && color="$C_GREEN"
  [[ "$status" == "FAIL" ]] && color="$C_RED"
  [[ "$status" == "SKIP" ]] && color="$C_YELLOW"
  log "${color}$(bar_for "$completed" "$total") [$status]${C_RESET} $id ${C_DIM}${note}${C_RESET}"
}

run_required() {
  local check_id="$1"
  local description="$2"
  shift 2
  set_check "$check_id" "RUNNING" "$description"
  log "${C_DIM}$ $*${C_RESET}"
  plain_log ""
  plain_log ">>> $description"
  plain_log ">>> $*"

  set +e
  "$@" 2>&1 | tee -a "$LOG_FILE"
  local status=${PIPESTATUS[0]}
  set -e

  if [[ "$status" -ne 0 ]]; then
    set_check "$check_id" "FAIL" "$description failed with exit code $status"
    FAILED=true
    return "$status"
  fi

  set_check "$check_id" "PASS" "$description"
  return 0
}

ensure_azd_environment() {
  local subscription_id
  local run_salt
  subscription_id="$(az account show --query id -o tsv)"
  run_salt="${ENV_NAME}-$(date +%Y%m%d%H%M%S)"

  log "${C_DIM}$ azd env select $ENV_NAME || azd env new $ENV_NAME${C_RESET}"
  if azd env select "$ENV_NAME" >/dev/null 2>&1; then
    plain_log "Selected existing azd environment: $ENV_NAME"
  else
    azd env new "$ENV_NAME" 2>&1 | tee -a "$LOG_FILE"
    azd env select "$ENV_NAME" >/dev/null
  fi

  log "${C_DIM}$ azd env set AZURE_SUBSCRIPTION_ID $subscription_id${C_RESET}"
  azd env set AZURE_SUBSCRIPTION_ID "$subscription_id" 2>&1 | tee -a "$LOG_FILE"

  log "${C_DIM}$ azd env set DEPLOYMENT_MODE $DEPLOYMENT_MODE${C_RESET}"
  azd env set DEPLOYMENT_MODE "$DEPLOYMENT_MODE" 2>&1 | tee -a "$LOG_FILE"

  log "${C_DIM}$ azd env set AZURE_RESOURCE_GROUP rg-$ENV_NAME${C_RESET}"
  azd env set AZURE_RESOURCE_GROUP "rg-$ENV_NAME" 2>&1 | tee -a "$LOG_FILE"

  log "${C_DIM}$ azd env set AZURE_LOCATION $LOCATION${C_RESET}"
  azd env set AZURE_LOCATION "$LOCATION" 2>&1 | tee -a "$LOG_FILE"

  if [[ -n "$FABRIC_LOCATION" ]]; then
    log "${C_DIM}$ azd env set FABRIC_LOCATION $FABRIC_LOCATION${C_RESET}"
    azd env set FABRIC_LOCATION "$FABRIC_LOCATION" 2>&1 | tee -a "$LOG_FILE"
  fi

  log "${C_DIM}$ azd env set AZURE_NAME_SALT $run_salt${C_RESET}"
  azd env set AZURE_NAME_SALT "$run_salt" 2>&1 | tee -a "$LOG_FILE"
}

load_env_file() {
  if [[ -z "$ENV_FILE" ]]; then
    log "${C_RED}Missing --env-file. Use .env.external.local for this external tenant run.${C_RESET}"
    exit 2
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    log "${C_RED}Env file not found: $ENV_FILE${C_RESET}"
    exit 2
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  if [[ -n "${EXTERNAL_AZURE_CONFIG_DIR:-}" ]]; then
    local az_cfg="${EXTERNAL_AZURE_CONFIG_DIR/#\~/$HOME}"
    mkdir -p "$az_cfg"
    export AZURE_CONFIG_DIR="$az_cfg"
  fi
}

json_value() {
  local expr="$1"
  python3 -c "import json,sys; d=json.load(sys.stdin); v=$expr; print('' if v is None else v)"
}

azd_value() {
  local key="$1"
  azd env get-values 2>/dev/null | awk -F= -v k="$key" '$1 == k {gsub(/^"|"$/, "", $2); print $2; exit}'
}

load_deployment_values() {
  RESOURCE_GROUP="$(azd_value AZURE_RESOURCE_GROUP)"
  SEARCH_SERVICE_NAME="$(azd_value AZURE_SEARCH_SERVICE_NAME)"
  SEARCH_ENDPOINT="$(azd_value AZURE_SEARCH_ENDPOINT)"
  HOSTING_MODE="$(azd_value AZURE_HOSTING_MODE)"
  STATIC_WEB_APP_LOCATION="$(azd_value AZURE_STATIC_WEB_APP_LOCATION)"
  STATIC_WEB_APP_NAME="$(azd_value AZURE_STATIC_WEB_APP_NAME)"
  APP_URL="$(azd_value AZURE_WEBAPP_URL)"
  WEBAPP_NAME="$(azd_value AZURE_WEBAPP_NAME)"
  STORAGE_ACCOUNT_NAME="$(azd_value AZURE_STORAGE_ACCOUNT_NAME)"
  OPENAI_ENDPOINT="$(azd_value AZURE_OPENAI_ENDPOINT)"
  OPENAI_ACCOUNT_NAME="$(azd_value AZURE_OPENAI_ACCOUNT_NAME)"
  FABRIC_WORKSPACE_ID="$(azd_value FABRIC_WORKSPACE_ID)"
  FABRIC_ONTOLOGY_ID="$(azd_value FABRIC_ONTOLOGY_ID)"
  if [[ -z "$OPENAI_ACCOUNT_NAME" ]]; then
    OPENAI_ACCOUNT_NAME="$(printf '%s' "$OPENAI_ENDPOINT" | sed -E 's#^https://##; s#/$##; s#\\.openai\\.azure\\.com$##')"
  fi
  write_report
}

install_static_app_dependencies() {
  if [[ -f static-app/package-lock.json ]]; then
    npm --prefix static-app ci
  else
    npm --prefix static-app install
  fi
}

build_static_app() {
  npm --prefix static-app run build
}

search_key() {
  az search admin-key show \
    --service-name "$SEARCH_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query primaryKey \
    -o tsv
}

search_get() {
  local path="$1"
  local key="$2"
  curl -fsS \
    -H "api-key: $key" \
    "${SEARCH_ENDPOINT%/}${path}?api-version=2026-05-01-preview"
}

search_post() {
  local path="$1"
  local key="$2"
  local payload="$3"
  curl -fsS \
    -H "api-key: $key" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "${SEARCH_ENDPOINT%/}${path}?api-version=2026-05-01-preview"
}

search_post_with_fabric_token() {
  local path="$1"
  local key="$2"
  local query="$3"
  python3 - "$query" <<'PY' | curl -fsS \
    -H "api-key: $key" \
    -H "x-ms-query-source-authorization: $FABRIC_USER_SEARCH_TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary @- \
    "${SEARCH_ENDPOINT%/}${path}?api-version=2026-05-01-preview"
import json
import sys

query = sys.argv[1]
print(json.dumps({
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": query,
                }
            ],
        }
    ],
    "includeActivity": True,
    "knowledgeSourceParams": [
        {
            "kind": "fabricOntology",
            "knowledgeSourceName": "fabric-ontology-ks",
            "includeReferences": True,
            "includeReferenceSourceData": True,
        }
    ],
    "outputMode": "answerSynthesis",
    "retrievalReasoningEffort": {
        "kind": "low",
    },
    "maxRuntimeInSeconds": 90,
}))
PY
}

search_post_with_fabric_token_capture() {
  local path="$1"
  local key="$2"
  local query="$3"
  local body_file="$4"
  local status_file="$5"
  local payload_file="$LOG_DIR/fabric-live-retrieve-payload.json"
  local http_code

  python3 - "$query" > "$payload_file" <<'PY'
import json
import sys

query = sys.argv[1]
print(json.dumps({
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": query,
                }
            ],
        }
    ],
    "includeActivity": True,
    "knowledgeSourceParams": [
        {
            "kind": "fabricOntology",
            "knowledgeSourceName": "fabric-ontology-ks",
            "includeReferences": True,
            "includeReferenceSourceData": True,
        }
    ],
    "outputMode": "answerSynthesis",
    "retrievalReasoningEffort": {
        "kind": "low",
    },
    "maxRuntimeInSeconds": 90,
}))
PY

  http_code="$(curl -sS \
    -o "$body_file" \
    -w "%{http_code}" \
    -H "api-key: $key" \
    -H "x-ms-query-source-authorization: $FABRIC_USER_SEARCH_TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary @"$payload_file" \
    "${SEARCH_ENDPOINT%/}${path}?api-version=2026-05-01-preview" 2>>"$LOG_FILE" || true)"
  printf '%s' "$http_code" > "$status_file"
  [[ "$http_code" =~ ^2[0-9][0-9]$ ]]
}

retry_fabric_live_retrieve() {
  local path="$1"
  local key="$2"
  local query="$3"
  local attempts="${4:-10}"
  local delay_seconds="${5:-30}"
  local attempt=1
  local tmp_file="$LOG_DIR/fabric-live-retrieve-response.json"
  local status_file="$LOG_DIR/fabric-live-retrieve-status.txt"
  local http_status=""

  set_check "fabric_live_retrieve" "RUNNING" "Waiting for Fabric ontology retrieve evidence"

  while [[ "$attempt" -le "$attempts" ]]; do
    if search_post_with_fabric_token_capture "$path" "$key" "$query" "$tmp_file" "$status_file" \
      && validate_json_expr 'any(x.get("type") == "fabricOntology" for x in d.get("activity", [])) and "No relevant content was found" not in json.dumps(d.get("response", ""))' < "$tmp_file"; then
      set_check "fabric_live_retrieve" "PASS" "Fabric live retrieve returned fabricOntology activity."
      return 0
    fi
    http_status="$(cat "$status_file" 2>/dev/null || printf 'unknown')"
    log "${C_YELLOW}Waiting for Fabric retrieve readiness ($attempt/$attempts, HTTP $http_status). Body: $tmp_file${C_RESET}"
    sleep "$delay_seconds"
    attempt=$(( attempt + 1 ))
  done

  http_status="$(cat "$status_file" 2>/dev/null || printf 'unknown')"
  set_check "fabric_live_retrieve" "FAIL" "Fabric live retrieve did not return expected ontology evidence. Last HTTP status: $http_status. Body: $tmp_file"
  FAILED=true
  return 1
}

json_payload_with_fabric_token() {
  local query="$1"
  python3 - "$query" <<'PY'
import json
import os
import sys

print(json.dumps({
    "query": sys.argv[1],
    "fabricUserSearchToken": os.environ["FABRIC_USER_SEARCH_TOKEN"],
}))
PY
}

fabric_configured() {
  [[ -n "${FABRIC_WORKSPACE_ID:-}" && -n "${FABRIC_ONTOLOGY_ID:-}" && "${FABRIC_WORKSPACE_ID:-}" != 00000000-* && "${FABRIC_ONTOLOGY_ID:-}" != 00000000-* ]]
}

fabric_live_expected() {
  [[ "$DEPLOYMENT_MODE" != "mcp-only" ]] && fabric_configured
}

http_json() {
  local method="$1"
  local url="$2"
  local payload="${3:-}"
  if [[ "$method" == "GET" ]]; then
    curl -fsS "$url"
  else
    curl -fsS -X "$method" -H "Content-Type: application/json" -d "$payload" "$url"
  fi
}

http_json_capture() {
  local method="$1"
  local url="$2"
  local payload="$3"
  local body_file="$4"
  local status_file="$5"
  local http_code

  if [[ "$method" == "GET" ]]; then
    http_code="$(curl -sS -o "$body_file" -w "%{http_code}" "$url" 2>>"$LOG_FILE" || true)"
  else
    http_code="$(curl -sS -X "$method" \
      -H "Content-Type: application/json" \
      -d "$payload" \
      -o "$body_file" \
      -w "%{http_code}" \
      "$url" 2>>"$LOG_FILE" || true)"
  fi

  printf '%s' "$http_code" > "$status_file"
  [[ "$http_code" =~ ^2[0-9][0-9]$ ]]
}

validate_json_expr() {
  local expr="$1"
  python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if ($expr) else 1)"
}

retry_url_200() {
  local check_id="$1"
  local url="$2"
  local attempts="${3:-24}"
  local delay_seconds="${4:-10}"
  local attempt=1
  set_check "$check_id" "RUNNING" "Waiting for $url"

  while [[ "$attempt" -le "$attempts" ]]; do
    if curl -fsS -o /dev/null "$url" 2>>"$LOG_FILE"; then
      set_check "$check_id" "PASS" "$url"
      return 0
    fi
    log "${C_YELLOW}Waiting for app response ($attempt/$attempts)...${C_RESET}"
    sleep "$delay_seconds"
    attempt=$(( attempt + 1 ))
  done

  set_check "$check_id" "FAIL" "Timed out waiting for HTTP 200: $url"
  FAILED=true
  return 1
}

retry_json_check() {
  local check_id="$1"
  local method="$2"
  local url="$3"
  local payload="$4"
  local expr="$5"
  local note="$6"
  local attempts="${7:-18}"
  local delay_seconds="${8:-10}"
  local attempt=1
  local tmp_file="$LOG_DIR/${check_id}-response.json"
  local status_file="$LOG_DIR/${check_id}-status.txt"
  local http_status=""

  set_check "$check_id" "RUNNING" "$note"

  while [[ "$attempt" -le "$attempts" ]]; do
    if http_json_capture "$method" "$url" "$payload" "$tmp_file" "$status_file" && validate_json_expr "$expr" < "$tmp_file"; then
      set_check "$check_id" "PASS" "$note"
      return 0
    fi
    http_status="$(cat "$status_file" 2>/dev/null || printf 'unknown')"
    log "${C_YELLOW}Waiting for API response ($check_id $attempt/$attempts, HTTP $http_status). Body: $tmp_file${C_RESET}"
    sleep "$delay_seconds"
    attempt=$(( attempt + 1 ))
  done

  http_status="$(cat "$status_file" 2>/dev/null || printf 'unknown')"
  set_check "$check_id" "FAIL" "$note failed. Last HTTP status: $http_status. Body: $tmp_file"
  FAILED=true
  return 1
}

run_cleanup() {
  if [[ "$CLEANUP_STARTED" == "true" ]]; then
    return 0
  fi
  CLEANUP_STARTED=true

  if [[ "$CLEANUP" != "true" ]]; then
    set_check "cleanup" "SKIP" "Resources kept for debugging."
    set_check "resource_group_deleted" "SKIP" "Resources kept for debugging."
    return 0
  fi

  if ! azd env select "$ENV_NAME" >/dev/null 2>&1; then
    set_check "cleanup" "SKIP" "azd environment was not created."
    set_check "resource_group_deleted" "SKIP" "No azd environment to clean up."
    return 0
  fi

  load_deployment_values
  if [[ -z "$RESOURCE_GROUP" ]]; then
    set_check "cleanup" "SKIP" "No resource group output was created."
    set_check "resource_group_deleted" "SKIP" "No resource group output was created."
    return 0
  fi

  if bash scripts/destroy.sh --env-file "$ENV_FILE" --env-name "$ENV_NAME" --yes 2>&1 | tee -a "$LOG_FILE"; then
    set_check "cleanup" "PASS" "destroy.sh completed"
  else
    set_check "cleanup" "FAIL" "destroy.sh failed"
    FAILED=true
    return 1
  fi

  if [[ -z "$RESOURCE_GROUP" ]]; then
    set_check "resource_group_deleted" "SKIP" "Resource group name was not available."
    return 0
  fi

  set +e
  az group show --name "$RESOURCE_GROUP" --query name -o tsv >/tmp/foundry-iq-liveks-rg-check.$$ 2>/dev/null
  local rg_status=$?
  rm -f /tmp/foundry-iq-liveks-rg-check.$$
  set -e

  if [[ "$rg_status" -ne 0 ]]; then
    set_check "resource_group_deleted" "PASS" "Resource group no longer exists."
  else
    log "${C_YELLOW}Resource group still exists after azd down; deleting empty group directly.${C_RESET}"
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>&1 | tee -a "$LOG_FILE"
    local attempt=1
    while [[ "$attempt" -le 12 ]]; do
      if ! az group show --name "$RESOURCE_GROUP" --query name -o tsv >/dev/null 2>&1; then
        set_check "resource_group_deleted" "PASS" "Resource group deleted after direct cleanup."
        return 0
      fi
      sleep 10
      attempt=$(( attempt + 1 ))
    done
    set_check "resource_group_deleted" "FAIL" "Resource group still exists after direct cleanup: $RESOURCE_GROUP"
    FAILED=true
    return 1
  fi
}

on_exit() {
  local exit_code=$?
  if [[ "$exit_code" -ne 0 ]]; then
    FAILED=true
  fi
  if [[ "$CLEANUP" == "true" && "$CLEANUP_STARTED" != "true" ]]; then
    log "${C_YELLOW}Attempting cleanup after interruption or failure.${C_RESET}"
    run_cleanup || true
  fi
  write_report
}
trap on_exit EXIT

cat <<'BANNER' | tee -a "$LOG_FILE"

+---------------------------------------------------------------------+
| Azure AI Search Foundry IQ Live Knowledge Sources                   |
| Live E2E deployment test                                            |
+---------------------------------------------------------------------+
BANNER

log "Log file: $LOG_FILE"
log "Report: $REPORT_PATH"
write_report

load_env_file

if [[ "$DEPLOYMENT_MODE" == "byo-fabric" ]] && ! fabric_configured; then
  log "${C_RED}BYO Fabric E2E requires FABRIC_WORKSPACE_ID and FABRIC_ONTOLOGY_ID in $ENV_FILE.${C_RESET}"
  exit 2
fi

if bash scripts/external-tenant-login.sh --env-file "$ENV_FILE" --check-only 2>&1 | tee -a "$LOG_FILE"; then
  set_check "external_login" "PASS" "External tenant session active."
else
  set_check "external_login" "FAIL" "External tenant login is not active."
  exit 1
fi

EXPECTED_SUBSCRIPTION_NAME="${EXPECTED_SUBSCRIPTION_NAME:-${E2E_EXPECTED_SUBSCRIPTION_NAME:-}}"
EXPECTED_TENANT_ID="${EXPECTED_TENANT_ID:-${E2E_EXPECTED_TENANT_ID:-}}"
ACCOUNT_JSON="$(az account show --only-show-errors)"
ACCOUNT_NAME="$(printf '%s' "$ACCOUNT_JSON" | json_value 'd.get("name","")')"
TENANT_ID="$(printf '%s' "$ACCOUNT_JSON" | json_value 'd.get("tenantId","")')"
if [[ -z "$EXPECTED_SUBSCRIPTION_NAME" && -z "$EXPECTED_TENANT_ID" ]]; then
  set_check "subscription" "PASS" "$ACCOUNT_NAME / $TENANT_ID (no expected account constraint configured)"
elif [[ "$ACCOUNT_NAME" == "$EXPECTED_SUBSCRIPTION_NAME" && "$TENANT_ID" == "$EXPECTED_TENANT_ID" ]]; then
  set_check "subscription" "PASS" "$ACCOUNT_NAME / $TENANT_ID"
else
  set_check "subscription" "FAIL" "Expected ${EXPECTED_SUBSCRIPTION_NAME:-<any-subscription>} / ${EXPECTED_TENANT_ID:-<any-tenant>} but got $ACCOUNT_NAME / $TENANT_ID"
  exit 1
fi

missing_tools=""
for tool in azd az python3 node npm curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing_tools="$missing_tools $tool"
  fi
done
if [[ -z "$missing_tools" ]]; then
  set_check "tools" "PASS" "azd, az, python3, node, npm, curl"
else
  set_check "tools" "FAIL" "Missing:$missing_tools"
  exit 1
fi

ensure_azd_environment

run_required "bicep" "Bicep template builds" az bicep build --file infra/main.bicep --outfile "$LOG_DIR/e2e-main.bicep.validate.json"
run_required "postprovision_dry_run" "postprovision dry-run passes" python3 scripts/postprovision.py --dry-run
run_required "npm_ci" "static demo app dependencies install" install_static_app_dependencies
run_required "app_build" "static demo app builds" build_static_app

DEPLOY_CAPTURE="$LOG_DIR/azd-up-${ENV_NAME}.log"
DEPLOY_COMMAND=(bash scripts/deploy.sh --mode "$DEPLOYMENT_MODE" --env-file "$ENV_FILE" --env-name "$ENV_NAME" --location "$LOCATION" --skip-app-build --skip-dry-run)
if [[ -n "$FABRIC_LOCATION" ]]; then
  DEPLOY_COMMAND+=(--fabric-location "$FABRIC_LOCATION")
fi
set +e
"${DEPLOY_COMMAND[@]}" 2>&1 | tee -a "$LOG_FILE" | tee "$DEPLOY_CAPTURE"
deploy_status=${PIPESTATUS[0]}
set -e

if [[ "$deploy_status" -eq 0 ]]; then
  set_check "azd_up" "PASS" "azd up completed through deploy.sh"
else
  deploy_note="deploy.sh failed"
  if grep -q "Current Limit (Total VMs): 0" "$DEPLOY_CAPTURE"; then
    deploy_note="App Service Plan quota blocked: Total VMs limit is 0"
  fi
  set_check "azd_up" "FAIL" "$deploy_note"
  exit 1
fi

load_deployment_values

if [[ "$DEPLOYMENT_MODE" != "mcp-only" && -z "${FABRIC_USER_SEARCH_TOKEN:-}" && "$(fabric_configured && echo yes || echo no)" == "yes" ]]; then
  FABRIC_USER_SEARCH_TOKEN="$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv 2>/dev/null || true)"
  export FABRIC_USER_SEARCH_TOKEN
fi

if [[ -n "$RESOURCE_GROUP" ]] && az group show --name "$RESOURCE_GROUP" --query name -o tsv >/dev/null; then
  set_check "resource_group" "PASS" "$RESOURCE_GROUP"
else
  set_check "resource_group" "FAIL" "Resource group not found."
  exit 1
fi

resource_failures=""
az search service show --name "$SEARCH_SERVICE_NAME" --resource-group "$RESOURCE_GROUP" --query name -o tsv >/dev/null 2>&1 || resource_failures="$resource_failures search"
if [[ "${HOSTING_MODE:-staticwebapp}" == "staticwebapp" ]]; then
  az staticwebapp show --name "$STATIC_WEB_APP_NAME" --resource-group "$RESOURCE_GROUP" --query name -o tsv >/dev/null 2>&1 || resource_failures="$resource_failures staticwebapp"
else
  az webapp show --name "$WEBAPP_NAME" --resource-group "$RESOURCE_GROUP" --query name -o tsv >/dev/null 2>&1 || resource_failures="$resource_failures webapp"
fi
az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query name -o tsv >/dev/null 2>&1 || resource_failures="$resource_failures storage"
az cognitiveservices account show --name "$OPENAI_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query name -o tsv >/dev/null 2>&1 || resource_failures="$resource_failures openai"

if [[ -z "$resource_failures" ]]; then
  set_check "azure_resources" "PASS" "Search, Azure OpenAI, demo hosting, and Storage found."
else
  set_check "azure_resources" "FAIL" "Missing:$resource_failures"
  exit 1
fi

if [[ -f "deployments/${ENV_NAME}/deployment-summary.md" ]]; then
  set_check "deployment_summary" "PASS" "deployments/${ENV_NAME}/deployment-summary.md"
else
  set_check "deployment_summary" "FAIL" "Deployment summary missing."
  exit 1
fi

SEARCH_KEY="$(search_key)"

if search_get "/knowledgesources/microsoft-learn-mcp-ks" "$SEARCH_KEY" | validate_json_expr 'd.get("name") == "microsoft-learn-mcp-ks"'; then
  set_check "mcp_ks" "PASS" "microsoft-learn-mcp-ks"
else
  set_check "mcp_ks" "FAIL" "MCP Knowledge Source not found."
  exit 1
fi

if [[ "$DEPLOYMENT_MODE" == "mcp-only" ]]; then
  set_check "fabric_ks" "SKIP" "Deployment mode is mcp-only."
elif fabric_configured; then
  if search_get "/knowledgesources/fabric-ontology-ks" "$SEARCH_KEY" | validate_json_expr 'd.get("name") == "fabric-ontology-ks" and d.get("kind") == "fabricOntology"'; then
    set_check "fabric_ks" "PASS" "fabric-ontology-ks"
  else
    set_check "fabric_ks" "FAIL" "Fabric Ontology Knowledge Source not found."
    exit 1
  fi
elif [[ "$DEPLOYMENT_MODE" == "full" ]]; then
  set_check "fabric_ks" "SKIP" "Full Fabric provisioning did not produce Fabric IDs."
else
  set_check "fabric_ks" "FAIL" "BYO Fabric mode requires FABRIC_WORKSPACE_ID and FABRIC_ONTOLOGY_ID."
  exit 1
fi

if search_get "/knowledgebases/live-knowledge-sources-mcp-kb" "$SEARCH_KEY" | validate_json_expr 'd.get("name") == "live-knowledge-sources-mcp-kb"'; then
  set_check "mcp_kb" "PASS" "live-knowledge-sources-mcp-kb"
else
  set_check "mcp_kb" "FAIL" "MCP-only Knowledge Base not found."
  exit 1
fi

if search_get "/knowledgebases/live-knowledge-sources-kb" "$SEARCH_KEY" | validate_json_expr 'd.get("name") == "live-knowledge-sources-kb"'; then
  set_check "combined_kb" "PASS" "live-knowledge-sources-kb"
else
  set_check "combined_kb" "FAIL" "Combined Knowledge Base not found."
  exit 1
fi

if search_post "/indexes/airline-ops-regulatory-docs/docs/search" "$SEARCH_KEY" '{"search":"*","top":10}' | validate_json_expr 'len(d.get("value", [])) >= 4'; then
  set_check "airline_index" "PASS" "At least four Airline Ops docs indexed."
else
  set_check "airline_index" "FAIL" "Airline Ops index missing or empty."
  exit 1
fi

MCP_PAYLOAD='{"messages":[{"role":"user","content":[{"type":"text","text":"What must be configured to create an Azure AI Search MCP Server knowledge source?"}]}],"includeActivity":true,"knowledgeSourceParams":[{"kind":"mcpServer","knowledgeSourceName":"microsoft-learn-mcp-ks","includeReferences":true,"includeReferenceSourceData":true}],"outputMode":"answerSynthesis","retrievalReasoningEffort":{"kind":"low"},"maxRuntimeInSeconds":60}'
if search_post "/knowledgebases/live-knowledge-sources-mcp-kb/retrieve" "$SEARCH_KEY" "$MCP_PAYLOAD" | validate_json_expr 'any((x.get("type") == "mcpServer" or x.get("toolName") == "microsoft_docs_search") for x in d.get("activity", [])) or len(d.get("references", [])) > 0'; then
  set_check "mcp_retrieve" "PASS" "MCP retrieve returned activity or references."
else
  set_check "mcp_retrieve" "FAIL" "MCP retrieve did not return expected evidence."
  exit 1
fi

if [[ -n "${FABRIC_USER_SEARCH_TOKEN:-}" && "$(fabric_live_expected && echo yes || echo no)" == "yes" ]]; then
  if ! retry_fabric_live_retrieve "/knowledgebases/live-knowledge-sources-kb/retrieve" "$SEARCH_KEY" "list all airlines from our airline ontology"; then
    log "${C_YELLOW}Continuing after Fabric live retrieve failure to collect demo app diagnostics.${C_RESET}"
  fi
else
  set_check "fabric_live_retrieve" "SKIP" "FABRIC_USER_SEARCH_TOKEN, Fabric IDs, or Fabric-enabled mode not configured."
fi

if [[ -z "$APP_URL" ]]; then
  set_check "app_http_200" "FAIL" "App URL missing."
  exit 1
fi

retry_url_200 "app_http_200" "$APP_URL"
if ! retry_json_check "api_status" "GET" "$APP_URL/api/status" "" 'd.get("hasSearchKey") is True and "searchApiKey" not in d and "azureSearchApiKey" not in d and "apiKey" not in d' "/api/status returns non-secret runtime config"; then
  log "${C_YELLOW}Continuing after /api/status failure to collect remaining app diagnostics.${C_RESET}"
fi
if ! retry_json_check "api_mcp" "POST" "$APP_URL/api/retrieve/mcp" '{"query":"What must be configured to create an Azure AI Search MCP Server knowledge source?"}' 'd.get("mode") in ("live","offline") and (len(d.get("references", [])) > 0 or any(x.get("type") == "mcpServer" for x in d.get("activity", [])))' "/api/retrieve/mcp returns retrieve evidence"; then
  log "${C_YELLOW}Continuing after /api/retrieve/mcp failure to collect remaining app diagnostics.${C_RESET}"
fi
if [[ -n "${FABRIC_USER_SEARCH_TOKEN:-}" && "$(fabric_live_expected && echo yes || echo no)" == "yes" ]]; then
  FABRIC_API_PAYLOAD="$(json_payload_with_fabric_token "list all airlines from our airline ontology")"
  COMBINED_API_PAYLOAD="$(json_payload_with_fabric_token "list all airlines from our airline ontology and cite Microsoft Learn guidance for validating retrieve activity")"
  if ! retry_json_check "api_fabric" "POST" "$APP_URL/api/retrieve/fabric" "$FABRIC_API_PAYLOAD" 'd.get("mode") == "live" and any(x.get("type") == "fabricOntology" for x in d.get("activity", [])) and "No relevant content was found" not in json.dumps(d.get("response", ""))' "/api/retrieve/fabric returns live Fabric evidence"; then
    log "${C_YELLOW}Continuing after /api/retrieve/fabric failure to collect combined route diagnostics.${C_RESET}"
  fi
  if ! retry_json_check "api_combined" "POST" "$APP_URL/api/retrieve/combined" "$COMBINED_API_PAYLOAD" 'd.get("mode") == "live" and len(d.get("activity", [])) > 0 and "No relevant content was found" not in json.dumps(d.get("response", ""))' "/api/retrieve/combined returns live combined evidence"; then
    log "${C_YELLOW}Continuing after /api/retrieve/combined failure; final report will retain the failure.${C_RESET}"
  fi
else
  if ! retry_json_check "api_fabric" "POST" "$APP_URL/api/retrieve/fabric" '{"query":"Which airlines have the highest customer-care exposure this month?"}' 'd.get("mode") in ("offline","live") and len(d.get("references", [])) > 0' "/api/retrieve/fabric returns offline or live Fabric evidence"; then
    log "${C_YELLOW}Continuing after /api/retrieve/fabric failure to collect combined route diagnostics.${C_RESET}"
  fi
  if ! retry_json_check "api_combined" "POST" "$APP_URL/api/retrieve/combined" '{"query":"Identify the top customer-care exposure carrier and cite implementation guidance."}' 'd.get("mode") in ("offline","live") and len(d.get("references", [])) > 0' "/api/retrieve/combined returns combined evidence"; then
    log "${C_YELLOW}Continuing after /api/retrieve/combined failure; final report will retain the failure.${C_RESET}"
  fi
fi

run_cleanup

if [[ "$(fail_count)" -gt 0 ]]; then
  exit 1
fi

log ""
log "${C_GREEN}+---------------------------------------------------------------------+${C_RESET}"
log "${C_GREEN}| Live E2E test completed                                             |${C_RESET}"
log "${C_GREEN}+---------------------------------------------------------------------+${C_RESET}"
log "Report: $REPORT_PATH"
log "Log: $LOG_FILE"
