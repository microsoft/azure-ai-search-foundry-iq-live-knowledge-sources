#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "[compatibility] scripts/e2e-test.sh delegates to the v2 LiveKS CLI." >&2
exec "$ROOT/liveks" e2e "$@" --yes
