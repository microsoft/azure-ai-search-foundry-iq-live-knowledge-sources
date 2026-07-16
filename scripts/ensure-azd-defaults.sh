#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 scripts/ensure_azd_defaults.py "$@"
