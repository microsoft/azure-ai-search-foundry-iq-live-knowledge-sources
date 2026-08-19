#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

printf '\nFoundry IQ Live Knowledge Sources\n'
printf 'Replay status: run ./liveks try\n'
printf 'First live profile: ./liveks init --profile mcp-only --env liveks-mcp\n'
printf 'Then follow docs/15-codespaces-first-live.md for auth, doctor, plan, guarded up, verify, and cleanup.\n\n'
