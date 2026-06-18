#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_PREFIX="[static-webapp]"

log() {
  printf '%s %s\n' "$LOG_PREFIX" "$*"
}

azd_value() {
  local key="$1"
  azd env get-values 2>/dev/null | awk -F= -v k="$key" '$1 == k {gsub(/^"|"$/, "", $2); print $2; exit}'
}

cd "$REPO_ROOT"

if ! command -v az >/dev/null 2>&1; then
  log "Azure CLI is required for Static Web Apps API deployment."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  log "npm is required for Static Web Apps API deployment."
  exit 1
fi

RESOURCE_GROUP="$(azd_value AZURE_RESOURCE_GROUP)"
STATIC_WEB_APP_NAME="$(azd_value AZURE_STATIC_WEB_APP_NAME)"
HOSTING_MODE="$(azd_value AZURE_HOSTING_MODE)"

if [[ "${HOSTING_MODE:-staticwebapp}" != "staticwebapp" ]]; then
  log "Hosting mode is ${HOSTING_MODE}; skipping Static Web Apps API deployment."
  exit 0
fi

if [[ -z "$RESOURCE_GROUP" || -z "$STATIC_WEB_APP_NAME" ]]; then
  log "AZURE_RESOURCE_GROUP or AZURE_STATIC_WEB_APP_NAME is missing from azd env."
  exit 1
fi

log "Building static demo app."
if [[ -f static-app/package-lock.json ]]; then
  npm --prefix static-app ci
else
  npm --prefix static-app install
fi
npm --prefix static-app run build

log "Reading Static Web Apps deployment token without printing it."
SWA_TOKEN="$(az staticwebapp secrets list \
  --name "$STATIC_WEB_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.apiKey \
  -o tsv)"

if [[ -z "$SWA_TOKEN" ]]; then
  log "Unable to read Static Web Apps deployment token."
  exit 1
fi

log "Deploying static frontend and managed Functions API."
npx --yes @azure/static-web-apps-cli@2.0.6 deploy static-app/dist \
  --api-location static-app/api \
  --api-language node \
  --api-version 20 \
  --deployment-token "$SWA_TOKEN" \
  --env production

log "Static Web Apps deployment complete."
