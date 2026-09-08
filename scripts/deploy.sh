#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
exec python3 scripts/deploy-cloud.py "$@"
