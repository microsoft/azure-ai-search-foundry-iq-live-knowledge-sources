#!/usr/bin/env bash
set -Eeuo pipefail

value_or_empty() {
  local key="$1"
  azd env get-values 2>/dev/null | awk -F= -v k="$key" '$1 == k {gsub(/^"|"$/, "", $2); print $2; exit}' || true
}

set_if_empty() {
  local key="$1"
  local value="$2"
  if [[ -z "$(value_or_empty "$key")" ]]; then
    azd env set "$key" "$value" >/dev/null
    printf '[azd-defaults] %s=%s\n' "$key" "$value"
  fi
}

set_if_empty AZURE_HOSTING_MODE staticwebapp
set_if_empty AZURE_STATIC_WEB_APP_LOCATION eastus2
set_if_empty AZURE_APP_SERVICE_SKU F1
set_if_empty DEPLOYMENT_MODE mcp-only
set_if_empty FABRIC_CAPACITY_MODE skip
azure_location="$(value_or_empty AZURE_LOCATION)"
if [[ -n "$azure_location" ]]; then
  set_if_empty FABRIC_LOCATION "$azure_location"
else
  set_if_empty FABRIC_LOCATION eastus
fi
set_if_empty FABRIC_CAPACITY_NAME ""
set_if_empty FABRIC_CAPACITY_SKU F2
set_if_empty FABRIC_CAPACITY_ADMIN ""

env_name="$(value_or_empty AZURE_ENV_NAME)"
if [[ -n "$env_name" ]]; then
  set_if_empty AZURE_RESOURCE_GROUP "rg-${env_name}"
  set_if_empty AZURE_NAME_SALT "$env_name"
fi
