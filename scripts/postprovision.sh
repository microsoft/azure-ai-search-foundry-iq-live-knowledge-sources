#!/usr/bin/env bash
set -Eeuo pipefail

azd_value() {
  local key="$1"
  azd env get-values 2>/dev/null | awk -F= -v k="$key" '$1 == k {gsub(/^"|"$/, "", $2); print $2; exit}' || true
}

setting_value() {
  local key="$1"
  local process_value="${!key:-}"
  local azd_env_value=""
  if [[ -n "$process_value" ]]; then
    printf '%s' "$process_value"
    return 0
  fi
  azd_env_value="$(azd_value "$key")"
  printf '%s' "$azd_env_value"
}

is_real_guid_value() {
  local value="$1"
  [[ -n "$value" && "$value" != 00000000-* && "$value" != *"<"* ]]
}

DEPLOYMENT_MODE_VALUE="$(setting_value DEPLOYMENT_MODE)"
FABRIC_WORKSPACE_ID_VALUE="$(setting_value FABRIC_WORKSPACE_ID)"
FABRIC_ONTOLOGY_ID_VALUE="$(setting_value FABRIC_ONTOLOGY_ID)"
FABRIC_CAPACITY_MODE_VALUE="$(setting_value FABRIC_CAPACITY_MODE)"

if [[ "$DEPLOYMENT_MODE_VALUE" == "full" ]] && { ! is_real_guid_value "$FABRIC_WORKSPACE_ID_VALUE" || ! is_real_guid_value "$FABRIC_ONTOLOGY_ID_VALUE"; }; then
  if [[ "$FABRIC_CAPACITY_MODE_VALUE" == "skip" ]]; then
    echo "Full mode Fabric capacity mode is skip; Search postprovision will use offline/checklist behavior."
  else
    python3 scripts/fabric-provision.py
  fi
fi

python3 scripts/postprovision.py "$@"
