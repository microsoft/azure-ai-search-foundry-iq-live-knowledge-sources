#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 scripts/deploy_static_webapp_api.py "$@"
