#!/usr/bin/env bash
set -Eeuo pipefail

LOG_DIR=".deployment"
LOG_FILE=""
ENV_FILE=""
ENV_NAME=""
YES=false
NO_COLOR="${NO_COLOR:-}"
export AZD_SKIP_FIRST_RUN="${AZD_SKIP_FIRST_RUN:-true}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/destroy.sh [options]

Options:
  --env-file <path>   Load local env settings before cleanup.
  --env-name <name>   Select the azd environment to destroy.
  --yes               Do not ask for confirmation. Intended for CI only.
  --no-color          Disable ANSI color output.
  -h, --help          Show this help.

Examples:
  bash scripts/destroy.sh --env-name liveks-dev
  bash scripts/destroy.sh --env-file .env.external.local --env-name ext-liveks-dev
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --env-name)
      ENV_NAME="${2:-}"
      shift 2
      ;;
    --yes)
      YES=true
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
  C_BOLD=$'\033[1m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_BLUE=$'\033[34m'
else
  C_RESET=""
  C_BOLD=""
  C_GREEN=""
  C_YELLOW=""
  C_RED=""
  C_BLUE=""
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/destroy-$(date +%Y%m%d-%H%M%S).log"

log() {
  printf '%s\n' "$*" | tee -a "$LOG_FILE"
}

ok() {
  log "${C_GREEN}[OK]${C_RESET} $*"
}

warn() {
  log "${C_YELLOW}[WARN]${C_RESET} $*"
}

fail() {
  log "${C_RED}[FAIL]${C_RESET} $*"
}

run_cmd() {
  local description="$1"
  shift
  log "$ $*"

  set +e
  "$@" 2>&1 | tee -a "$LOG_FILE"
  local status=${PIPESTATUS[0]}
  set -e

  if [[ "$status" -ne 0 ]]; then
    fail "$description"
    log "Exit code: $status"
    log "See log: $LOG_FILE"
    exit "$status"
  fi

  ok "$description"
}

run_fabric_cleanup_best_effort() {
  local description="Delete generated Fabric assets when present"
  local command=(python3 scripts/fabric-destroy.py --yes)
  if [[ -n "$ENV_NAME" ]]; then
    command=(python3 scripts/fabric-destroy.py --env-name "$ENV_NAME" --yes)
  fi

  log "$ ${command[*]}"

  set +e
  "${command[@]}" 2>&1 | tee -a "$LOG_FILE"
  local status=${PIPESTATUS[0]}
  set -e

  if [[ "$status" -ne 0 ]]; then
    warn "$description failed with exit code $status; continuing to azd down so core Azure resources are removed."
    warn "After azd cleanup, inspect generated Fabric assets manually if needed."
    return 0
  fi

  ok "$description"
}

show_azd_env_safe() {
  set +e
  local output
  output="$(azd env get-values 2>&1)"
  local status=$?
  set -e

  if [[ "$status" -ne 0 ]]; then
    warn "Unable to read azd environment values."
    printf '%s\n' "$output" >> "$LOG_FILE"
    return 0
  fi

  while IFS= read -r line; do
    if [[ "$line" == *KEY* || "$line" == *TOKEN* || "$line" == *SECRET* || "$line" == *PASSWORD* ]]; then
      log "${line%%=*}=<redacted>"
    else
      log "$line"
    fi
  done <<< "$output"
}

load_env_file() {
  if [[ -z "$ENV_FILE" ]]; then
    return 0
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    fail "Env file not found: $ENV_FILE"
    exit 1
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

  ok "Loaded env file: $ENV_FILE"
}

confirm_destroy() {
  if [[ "$YES" == "true" ]]; then
    return 0
  fi

  log ""
  warn "This will delete Azure resources for the selected azd environment."
  log "Type 'delete' to continue:"
  read -r answer
  if [[ "$answer" != "delete" ]]; then
    fail "Cleanup cancelled."
    exit 1
  fi
}

cat <<'BANNER' | tee -a "$LOG_FILE"

+---------------------------------------------------------------------+
| Azure AI Search Foundry IQ Live Knowledge Sources                   |
| Demo cleanup                                                        |
+---------------------------------------------------------------------+
BANNER
log "Log file: $LOG_FILE"

load_env_file

if ! command -v azd >/dev/null 2>&1; then
  fail "azd is required."
  exit 1
fi

if [[ -n "$ENV_NAME" ]]; then
  run_cmd "Select azd environment $ENV_NAME" azd env select "$ENV_NAME"
else
  warn "No --env-name provided. azd may use the currently selected environment."
fi

show_azd_env_safe
confirm_destroy
run_fabric_cleanup_best_effort
run_cmd "Delete provisioned resources" azd down --purge --force

log ""
log "${C_BLUE}+---------------------------------------------------------------------+${C_RESET}"
log "${C_BLUE}| Cleanup complete                                                    |${C_RESET}"
log "${C_BLUE}+---------------------------------------------------------------------+${C_RESET}"
log "Log: $LOG_FILE"
