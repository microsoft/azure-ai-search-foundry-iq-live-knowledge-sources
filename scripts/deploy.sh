#!/usr/bin/env bash
set -Eeuo pipefail

TOTAL_STEPS=8
CURRENT_STEP=0
LOG_DIR=".deployment"
LOG_FILE=""
ENV_FILE=""
ENV_NAME=""
LOCATION=""
FABRIC_LOCATION_CLI=""
CLI_DEPLOYMENT_MODE=""
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-}"
SKIP_APP_BUILD=false
SKIP_DRY_RUN=false
POSTPROVISION_ONLY=false
NO_COLOR="${NO_COLOR:-}"
export AZD_SKIP_FIRST_RUN="${AZD_SKIP_FIRST_RUN:-true}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/deploy.sh [options]

Options:
  --mode <mode>            Deployment mode. Required unless DEPLOYMENT_MODE is
                           set in the env file or azd environment.
                           Values: byo-fabric, mcp-only, full
  --env-file <path>        Load local env settings before deployment.
                           Useful for external tenant profiles, for example:
                           --env-file .env.external.local
  --env-name <name>        Select or create an azd environment.
  --location <region>      Set AZURE_LOCATION for the azd environment.
                           Example: koreacentral, eastus, swedencentral
  --fabric-location <region>
                           Set FABRIC_LOCATION for full greenfield Fabric capacity.
                           Use a region where the subscription has Fabric quota.
  --skip-app-build         Skip local demo UI npm install/build validation.
  --skip-dry-run           Skip postprovision dry-run validation.
  --postprovision-only     Do not run azd up. Only run postprovision.py.
  --no-color               Disable ANSI color output.
  -h, --help               Show this help.

Examples:
  bash scripts/deploy.sh --mode mcp-only --env-name liveks-mcp --location eastus
  bash scripts/deploy.sh --mode byo-fabric --env-file .env.external.local --env-name liveks-byo --location eastus
  bash scripts/deploy.sh --mode full --env-name liveks-full --location eastus --fabric-location westus3
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      CLI_DEPLOYMENT_MODE="${2:-}"
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
      FABRIC_LOCATION_CLI="${2:-}"
      shift 2
      ;;
    --skip-app-build)
      SKIP_APP_BUILD=true
      shift
      ;;
    --skip-dry-run)
      SKIP_DRY_RUN=true
      shift
      ;;
    --postprovision-only)
      POSTPROVISION_ONLY=true
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

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"

log() {
  printf '%s\n' "$*" | tee -a "$LOG_FILE"
}

plain_log() {
  printf '%s\n' "$*" >> "$LOG_FILE"
}

bar() {
  local current="$1"
  local total="$2"
  local width=24
  local filled=$(( current * width / total ))
  local empty=$(( width - filled ))
  printf '['
  printf '%*s' "$filled" '' | tr ' ' '#'
  printf '%*s' "$empty" '' | tr ' ' '-'
  printf '] %d/%d' "$current" "$total"
}

header() {
  cat <<'BANNER' | tee -a "$LOG_FILE"

+---------------------------------------------------------------------+
| Azure AI Search Foundry IQ Live Knowledge Sources                   |
| One-command demo deployment                                         |
+---------------------------------------------------------------------+
BANNER
  log "Log file: $LOG_FILE"
  log ""
}

step() {
  CURRENT_STEP=$(( CURRENT_STEP + 1 ))
  local title="$1"
  log ""
  log "${C_BLUE}$(bar "$CURRENT_STEP" "$TOTAL_STEPS")${C_RESET} ${C_BOLD}${title}${C_RESET}"
  log "$(printf '%*s' 72 '' | tr ' ' '-')"
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
  log "${C_DIM}$ $*${C_RESET}"
  plain_log ""
  plain_log ">>> $description"
  plain_log ">>> $*"

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

probe_cmd() {
  local description="$1"
  shift
  log "${C_DIM}$ $*${C_RESET}"
  plain_log ""
  plain_log ">>> optional: $description"
  plain_log ">>> $*"

  set +e
  "$@" 2>&1 | tee -a "$LOG_FILE"
  local status=${PIPESTATUS[0]}
  set -e

  if [[ "$status" -ne 0 ]]; then
    warn "$description failed; continuing because this is diagnostic only."
    return 0
  fi

  ok "$description"
}

require_command() {
  local name="$1"
  local install_hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    fail "$name is required."
    log "$install_hint"
    exit 1
  fi
  ok "$name found: $(command -v "$name")"
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

valid_deployment_mode() {
  case "$1" in
    byo-fabric|mcp-only|full) return 0 ;;
    *) return 1 ;;
  esac
}

mode_display_name() {
  case "$1" in
    byo-fabric) printf 'BYO Fabric Mode' ;;
    mcp-only) printf 'MCP-only Mode' ;;
    full) printf 'Full Greenfield Mode' ;;
    *) printf '%s' "$1" ;;
  esac
}

select_or_create_azd_env() {
  if [[ -z "$ENV_NAME" ]]; then
    warn "No --env-name provided. azd may prompt you to select or create an environment."
    return 0
  fi

  if azd env select "$ENV_NAME" >/dev/null 2>&1; then
    ok "Selected existing azd environment: $ENV_NAME"
  else
    run_cmd "Create azd environment $ENV_NAME" azd env new "$ENV_NAME"
  fi
}

resolve_deployment_mode() {
  local from_azd=""
  if [[ -n "$CLI_DEPLOYMENT_MODE" ]]; then
    DEPLOYMENT_MODE="$CLI_DEPLOYMENT_MODE"
  fi

  if [[ -z "$DEPLOYMENT_MODE" ]]; then
    from_azd="$(azd_env_value DEPLOYMENT_MODE)"
    if [[ -n "$from_azd" ]]; then
      DEPLOYMENT_MODE="$from_azd"
    fi
  fi

  if [[ -z "$DEPLOYMENT_MODE" ]]; then
    fail "Deployment mode is required."
    log ""
    log "Choose one:"
    log "  --mode byo-fabric  Use an existing Fabric workspace and ontology; create Azure/Search/MCP/app resources."
    log "  --mode mcp-only    Create Azure/Search/MCP/app resources and skip Fabric."
    log "  --mode full        Greenfield path; creates Azure, Fabric capacity/workspace/lakehouse/ontology, and app resources."
    log ""
    log "Recommended first run:"
    log "  bash scripts/deploy.sh --mode byo-fabric --env-file .env.external.local --env-name liveks-byo --location eastus"
    exit 2
  fi

  if ! valid_deployment_mode "$DEPLOYMENT_MODE"; then
    fail "Invalid deployment mode: $DEPLOYMENT_MODE"
    log "Allowed values: byo-fabric, mcp-only, full"
    exit 2
  fi

  export DEPLOYMENT_MODE
  ok "Deployment mode: $(mode_display_name "$DEPLOYMENT_MODE")"
}

set_azd_deployment_mode() {
  run_cmd "Set deployment mode to $DEPLOYMENT_MODE" azd env set DEPLOYMENT_MODE "$DEPLOYMENT_MODE"
}

set_azd_location() {
  if [[ -z "$LOCATION" ]]; then
    return 0
  fi
  run_cmd "Set azd deployment location to $LOCATION" azd env set AZURE_LOCATION "$LOCATION"
}

set_azd_subscription() {
  local subscription_id
  subscription_id="$(az account show --query id -o tsv 2>/dev/null || true)"
  if [[ -n "$subscription_id" ]]; then
    run_cmd "Set azd subscription to current Azure CLI account" azd env set AZURE_SUBSCRIPTION_ID "$subscription_id"
  else
    warn "Unable to determine current Azure subscription id. azd may prompt for subscription selection."
  fi
}

set_azd_resource_group() {
  if [[ -z "$ENV_NAME" ]]; then
    warn "No --env-name provided. azd may prompt for resource group selection."
    return 0
  fi
  run_cmd "Set azd resource group to rg-$ENV_NAME" azd env set AZURE_RESOURCE_GROUP "rg-$ENV_NAME"
}

set_azd_name_salt_default() {
  if [[ -z "$ENV_NAME" ]]; then
    return 0
  fi
  if [[ -z "$(azd_env_value AZURE_NAME_SALT)" ]]; then
    run_cmd "Set default resource name salt" azd env set AZURE_NAME_SALT "$ENV_NAME"
  fi
}

azd_env_value() {
  local key="$1"
  azd env get-values 2>/dev/null | awk -F= -v k="$key" '$1 == k {gsub(/^"|"$/, "", $2); print $2; exit}' || true
}

setting_value() {
  local key="$1"
  local process_value="${!key:-}"
  local azd_value=""
  if [[ -n "$process_value" ]]; then
    printf '%s' "$process_value"
    return 0
  fi
  azd_value="$(azd_env_value "$key")"
  printf '%s' "$azd_value"
}

is_real_guid_value() {
  local value="$1"
  [[ -n "$value" && "$value" != 00000000-* && "$value" != *"<"* ]]
}

sync_nonsecret_setting_to_azd() {
  local key="$1"
  local value
  value="$(setting_value "$key")"
  if [[ -n "$value" ]]; then
    run_cmd "Set $key for azd environment" azd env set "$key" "$value"
  fi
}

write_full_mode_checklist() {
  local env="${ENV_NAME:-$(azd_env_value AZURE_ENV_NAME)}"
  [[ -z "$env" ]] && env="dev"
  local dir="deployments/${env}"
  local path="${dir}/fabric-full-mode-checklist.md"
  mkdir -p "$dir"
  cat > "$path" <<'CHECKLIST'
# Full Greenfield Fabric Automation Checklist

This file is generated by `scripts/deploy.sh --mode full` and is ignored by git.

Full mode is the target one-command experience:

1. Create or select Fabric capacity.
2. Create a Fabric workspace.
3. Load the Airline Ops sample data.
4. Create the Fabric ontology item.
5. Map entities, relationships, measures, and synonyms.
6. Capture `FABRIC_WORKSPACE_ID` and `FABRIC_ONTOLOGY_ID`.
7. Create the Azure AI Search Fabric Ontology Knowledge Source.
8. Deploy the demo app with live Fabric retrieve enabled by delegated user token.

Current implementation status:

- Azure AI Search, Azure OpenAI, Storage, MCP KS/KB, combined KB, Search index, and demo app are automated.
- Fabric capacity/workspace/lakehouse/ontology authoring is handled by `scripts/fabric-provision.py`.
- If this checklist appears, Fabric creation was explicitly skipped or Fabric IDs were not available before Search postprovision.
- Use `--mode full --fabric-location <region-with-quota>` for greenfield Fabric creation, or run `--mode byo-fabric` with an existing Fabric workspace and ontology.
CHECKLIST
  warn "Full Fabric automation did not run. Wrote checklist: $path"
}

safe_capacity_name() {
  local raw="$1"
  local cleaned
  cleaned="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')"
  if [[ -z "$cleaned" || ! "$cleaned" =~ ^[a-z] ]]; then
    cleaned="fab${cleaned}"
  fi
  printf '%.63s' "$cleaned"
}

set_fabric_full_defaults() {
  local workspace_id="$1"
  local ontology_id="$2"
  local account_user=""
  local fabric_mode=""
  local fabric_location=""
  local fabric_capacity_name=""

  if [[ "$DEPLOYMENT_MODE" != "full" ]]; then
    return 0
  fi

  if is_real_guid_value "$workspace_id" && is_real_guid_value "$ontology_id"; then
    fabric_mode="byo"
  else
    fabric_mode="$(setting_value FABRIC_CAPACITY_MODE)"
    [[ -z "$fabric_mode" || "$fabric_mode" == "skip" ]] && fabric_mode="create"
  fi
  run_cmd "Set Fabric capacity mode to $fabric_mode" azd env set FABRIC_CAPACITY_MODE "$fabric_mode"

  fabric_location="${FABRIC_LOCATION_CLI:-$(setting_value FABRIC_LOCATION)}"
  if [[ -z "$fabric_location" ]]; then
    fabric_location="${LOCATION:-$(azd_env_value AZURE_LOCATION)}"
  fi
  [[ -z "$fabric_location" ]] && fabric_location="eastus"
  run_cmd "Set Fabric location to $fabric_location" azd env set FABRIC_LOCATION "$fabric_location"

  sync_nonsecret_setting_to_azd FABRIC_CAPACITY_SKU
  if [[ -z "$(azd_env_value FABRIC_CAPACITY_SKU)" ]]; then
    run_cmd "Set default Fabric capacity SKU" azd env set FABRIC_CAPACITY_SKU F2
  fi

  fabric_capacity_name="$(setting_value FABRIC_CAPACITY_NAME)"
  if [[ -z "$fabric_capacity_name" ]]; then
    fabric_capacity_name="$(safe_capacity_name "fab${ENV_NAME:-liveks}")"
    run_cmd "Set generated Fabric capacity name" azd env set FABRIC_CAPACITY_NAME "$fabric_capacity_name"
  else
    run_cmd "Set Fabric capacity name" azd env set FABRIC_CAPACITY_NAME "$(safe_capacity_name "$fabric_capacity_name")"
  fi

  sync_nonsecret_setting_to_azd FABRIC_WORKSPACE_NAME
  sync_nonsecret_setting_to_azd FABRIC_LAKEHOUSE_NAME
  sync_nonsecret_setting_to_azd FABRIC_ONTOLOGY_NAME

  account_user="$(az account show --query user.name -o tsv 2>/dev/null || true)"
  if [[ -z "$(setting_value FABRIC_CAPACITY_ADMIN)" && -n "$account_user" ]]; then
    run_cmd "Set Fabric capacity admin to current Azure account" azd env set FABRIC_CAPACITY_ADMIN "$account_user"
  else
    sync_nonsecret_setting_to_azd FABRIC_CAPACITY_ADMIN
  fi
}

validate_mode_inputs() {
  local workspace_id
  local ontology_id
  workspace_id="$(setting_value FABRIC_WORKSPACE_ID)"
  ontology_id="$(setting_value FABRIC_ONTOLOGY_ID)"

  case "$DEPLOYMENT_MODE" in
    byo-fabric)
      if ! is_real_guid_value "$workspace_id" || ! is_real_guid_value "$ontology_id"; then
        fail "BYO Fabric mode requires FABRIC_WORKSPACE_ID and FABRIC_ONTOLOGY_ID."
        log "Put them in an ignored env file, for example .env.external.local, or set them in azd env."
        exit 2
      fi
      sync_nonsecret_setting_to_azd FABRIC_WORKSPACE_ID
      sync_nonsecret_setting_to_azd FABRIC_ONTOLOGY_ID
      ;;
    mcp-only)
      warn "MCP-only mode selected. Fabric workspace/ontology settings will be ignored for Knowledge Source creation."
      ;;
    full)
      if is_real_guid_value "$workspace_id" && is_real_guid_value "$ontology_id"; then
        warn "Full mode found existing Fabric IDs; this run will connect them instead of creating new Fabric assets."
        sync_nonsecret_setting_to_azd FABRIC_WORKSPACE_ID
        sync_nonsecret_setting_to_azd FABRIC_ONTOLOGY_ID
      else
        warn "Full mode will create Fabric capacity/workspace/lakehouse/ontology before Search postprovision."
      fi
      set_fabric_full_defaults "$workspace_id" "$ontology_id"
      ;;
  esac
}

preprovision_full_fabric_if_needed() {
  local workspace_id
  local ontology_id
  local capacity_mode
  workspace_id="$(setting_value FABRIC_WORKSPACE_ID)"
  ontology_id="$(setting_value FABRIC_ONTOLOGY_ID)"
  capacity_mode="$(setting_value FABRIC_CAPACITY_MODE)"

  if [[ "$POSTPROVISION_ONLY" == "true" ]]; then
    warn "Skipping Fabric preprovision because --postprovision-only was provided."
    return 0
  fi
  if [[ "$DEPLOYMENT_MODE" != "full" ]]; then
    warn "Skipping Fabric preprovision because deployment mode is $DEPLOYMENT_MODE."
    return 0
  fi
  if is_real_guid_value "$workspace_id" && is_real_guid_value "$ontology_id"; then
    ok "Fabric workspace and ontology IDs are already configured."
    return 0
  fi
  if [[ "$capacity_mode" == "skip" ]]; then
    write_full_mode_checklist
    return 0
  fi

  local command=(python3 scripts/fabric-provision.py)
  if [[ -n "$FABRIC_LOCATION_CLI" ]]; then
    command+=(--fabric-location "$FABRIC_LOCATION_CLI")
  fi
  run_cmd "Preprovision Fabric capacity/workspace/lakehouse/ontology/GraphModel" "${command[@]}"
}

set_azd_hosting_defaults() {
  local hosting_mode
  hosting_mode="$(azd_env_value AZURE_HOSTING_MODE)"
  if [[ -z "$hosting_mode" ]]; then
    run_cmd "Set default demo hosting to Static Web Apps" azd env set AZURE_HOSTING_MODE staticwebapp
  else
    ok "Demo hosting mode: $hosting_mode"
  fi

  local static_web_app_location
  static_web_app_location="$(azd_env_value AZURE_STATIC_WEB_APP_LOCATION)"
  if [[ -z "$static_web_app_location" ]]; then
    run_cmd "Set default Static Web Apps region" azd env set AZURE_STATIC_WEB_APP_LOCATION eastus2
  else
    ok "Static Web Apps region: $static_web_app_location"
  fi

  local app_service_sku
  app_service_sku="$(azd_env_value AZURE_APP_SERVICE_SKU)"
  if [[ -z "$app_service_sku" ]]; then
    run_cmd "Set default App Service SKU for optional hosting" azd env set AZURE_APP_SERVICE_SKU F1
  fi
}

latest_summary() {
  local env="${ENV_NAME:-}"
  local azd_env=""
  if [[ -z "$env" ]]; then
    azd_env="$(azd_env_value AZURE_ENV_NAME)"
    env="$azd_env"
  fi
  if [[ -n "$env" && -f "deployments/${env}/deployment-summary.md" ]]; then
    printf 'deployments/%s/deployment-summary.md\n' "$env"
    return 0
  fi
  find deployments -path '*/deployment-summary.md' -type f -print 2>/dev/null | sort | tail -n 1 || true
}

show_azd_env_safe() {
  set +e
  local output
  output="$(azd env get-values 2>&1)"
  local status=$?
  set -e

  if [[ "$status" -ne 0 ]]; then
    warn "Unable to read azd environment values; continuing."
    plain_log "$output"
    return 0
  fi

  plain_log ""
  plain_log ">>> optional: Sanitized azd environment values"
  while IFS= read -r line; do
    if [[ "$line" == *KEY* || "$line" == *TOKEN* || "$line" == *SECRET* || "$line" == *PASSWORD* ]]; then
      log "${line%%=*}=<redacted>"
    else
      log "$line"
    fi
  done <<< "$output"
}

on_error() {
  local exit_code=$?
  fail "Deployment script stopped unexpectedly."
  log "Exit code: $exit_code"
  log "See log: $LOG_FILE"
  exit "$exit_code"
}
trap on_error ERR

header

step "Preflight: local tools"
load_env_file
require_command azd "Install Azure Developer CLI: https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd"
require_command az "Install Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli"
require_command python3 "Install Python 3.10 or newer."
require_command node "Install Node.js 20 or newer."
require_command npm "Install npm with Node.js."
probe_cmd "Azure Developer CLI version" azd version
probe_cmd "Azure CLI version" az version
probe_cmd "Node version" node --version
probe_cmd "npm version" npm --version

step "Preflight: Azure session"
probe_cmd "Current Azure account" az account show --query "{name:name,id:id,tenantId:tenantId}" -o json
select_or_create_azd_env
resolve_deployment_mode
set_azd_deployment_mode
set_azd_subscription
set_azd_resource_group
set_azd_location
set_azd_name_salt_default
set_azd_hosting_defaults
validate_mode_inputs
show_azd_env_safe

step "Preprovision Fabric greenfield assets"
preprovision_full_fabric_if_needed

step "Validate infrastructure template"
run_cmd "Build Bicep template" az bicep build --file infra/main.bicep --outfile "$LOG_DIR/main.bicep.validate.json"

step "Validate postprovision payloads"
if [[ "$SKIP_DRY_RUN" == "true" ]]; then
  warn "Skipping postprovision dry-run."
else
  run_cmd "Run postprovision dry-run" python3 scripts/postprovision.py --dry-run
fi

step "Validate demo app"
if [[ "$SKIP_APP_BUILD" == "true" ]]; then
  warn "Skipping demo UI install/build."
else
  if [[ -f static-app/package-lock.json ]]; then
    run_cmd "Install static-app dependencies" npm --prefix static-app ci
  else
    run_cmd "Install static-app dependencies" npm --prefix static-app install
  fi
  run_cmd "Build static-app" npm --prefix static-app run build
fi

step "Provision Azure resources"
if [[ "$POSTPROVISION_ONLY" == "true" ]]; then
  warn "Skipping azd up because --postprovision-only was provided."
else
  run_cmd "Run azd up" azd up --no-prompt
fi

step "Postprovision and smoke test"
if [[ "$POSTPROVISION_ONLY" == "true" ]]; then
  run_cmd "Configure Fabric, Knowledge Sources, Knowledge Bases, Search index, and smoke tests" bash scripts/postprovision.sh
else
  ok "azd up completed. The azure.yaml postprovision hook ran during provisioning."
fi

SUMMARY_PATH="$(latest_summary)"
log ""
log "${C_GREEN}+---------------------------------------------------------------------+${C_RESET}"
log "${C_GREEN}| Deployment workflow complete                                        |${C_RESET}"
log "${C_GREEN}+---------------------------------------------------------------------+${C_RESET}"

if [[ -n "$SUMMARY_PATH" ]]; then
  log "Summary: $SUMMARY_PATH"
else
  warn "No deployment summary was found. Check postprovision output above."
fi

log "Log: $LOG_FILE"
log ""
log "Next checks:"
log "  1. Open the demo app URL from the deployment summary."
log "  2. Run the MCP panel live test."
if [[ "$DEPLOYMENT_MODE" == "byo-fabric" || "$DEPLOYMENT_MODE" == "full" ]]; then
  log "  3. Run the Fabric panel with a transient delegated token for live retrieve."
else
  log "  3. Fabric is skipped in MCP-only mode; use offline replay if you want to inspect the trace shape."
fi
log ""
log "Cleanup when finished:"
log "  azd down --purge"
