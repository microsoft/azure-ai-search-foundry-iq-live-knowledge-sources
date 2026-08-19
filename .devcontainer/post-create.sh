#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"
export NEXT_TELEMETRY_DISABLED=1

printf '\nLiveKS safe first boot\n'
for tool in python3 node az azd; do
  command -v "$tool" >/dev/null || {
    printf 'Required tool is missing: %s\n' "$tool" >&2
    exit 1
  }
done
az bicep version >/dev/null

./liveks try --evidence-out .deployment/codespaces-first-run-evidence.json
./liveks bootstrap
./liveks profiles --format json >/dev/null
./liveks doctor --profile offline --format json

printf '\nEnvironment ready. No Azure or Fabric resources were created.\n'
printf 'Open docs/15-codespaces-first-live.md for the guarded mcp-only live path.\n'
