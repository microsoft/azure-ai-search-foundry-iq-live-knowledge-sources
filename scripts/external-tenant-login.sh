#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  EXTERNAL_TENANT_ID=<tenant-guid> scripts/external-tenant-login.sh
  scripts/external-tenant-login.sh --env-file .env.external.local

Purpose:
  Login to an external Azure tenant using an isolated Azure CLI profile so the
  local/internal tenant session is not overwritten.

Outputs:
  - active account summary
  - raw access token for https://search.azure.com/ when --print-token is used

Options:
  --env-file <path>   Load EXTERNAL_TENANT_ID and optional EXTERNAL_AZURE_CONFIG_DIR.
  --device-code       Force device-code login instead of browser login.
  --print-token       Print raw Search token to stdout. Use only for local testing.
  --check-only        Do not start login. Only validate existing external session.
USAGE
}

ENV_FILE=""
USE_DEVICE_CODE=false
PRINT_TOKEN=false
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --device-code)
      USE_DEVICE_CODE=true
      shift
      ;;
    --print-token)
      PRINT_TOKEN=true
      shift
      ;;
    --check-only)
      CHECK_ONLY=true
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

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Env file not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${EXTERNAL_TENANT_ID:-}" || "${EXTERNAL_TENANT_ID}" == "00000000-0000-0000-0000-000000000000" ]]; then
  echo "Set EXTERNAL_TENANT_ID first. Use .env.external.local or an environment variable." >&2
  exit 1
fi

AZ_CFG="${EXTERNAL_AZURE_CONFIG_DIR:-$HOME/.azure-foundry-iq-ext}"
AZ_CFG="${AZ_CFG/#\~/$HOME}"
mkdir -p "$AZ_CFG"
export AZURE_CONFIG_DIR="$AZ_CFG"

echo "Azure CLI profile: $AZURE_CONFIG_DIR"
echo "External tenant: $EXTERNAL_TENANT_ID"

if az account show --only-show-errors >/dev/null 2>&1; then
  CURRENT_TENANT="$(az account show --query tenantId -o tsv 2>/dev/null || true)"
else
  CURRENT_TENANT=""
fi

if [[ "$CURRENT_TENANT" != "$EXTERNAL_TENANT_ID" && "$CHECK_ONLY" == "false" ]]; then
  echo "Starting external tenant login..."
  if [[ "$USE_DEVICE_CODE" == "true" ]]; then
    az login --tenant "$EXTERNAL_TENANT_ID" --use-device-code --only-show-errors >/dev/null
  else
    az login --tenant "$EXTERNAL_TENANT_ID" --only-show-errors >/dev/null
  fi
fi

ACCOUNT_JSON="$(az account show --only-show-errors)"
ACTIVE_TENANT="$(printf '%s' "$ACCOUNT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tenantId",""))')"

if [[ "$ACTIVE_TENANT" != "$EXTERNAL_TENANT_ID" ]]; then
  echo "External tenant login is not active in this profile." >&2
  echo "Active tenant: $ACTIVE_TENANT" >&2
  exit 1
fi

echo "External tenant session is active."
printf '%s\n' "$ACCOUNT_JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); u=d.get("user") or {}; print("Account: {}".format(u.get("name",""))); print("Subscription: {} ({})".format(d.get("name",""), d.get("id","")))'

if [[ "$PRINT_TOKEN" == "true" ]]; then
  az account get-access-token --resource https://search.azure.com/ --query accessToken -o tsv
else
  echo "Token check:"
  az account get-access-token --resource https://search.azure.com/ --query '{tenant:tenant, expiresOn:expiresOn, tokenType:tokenType}' -o json
fi
