#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 scripts/azd_postprovision.py "$@"
