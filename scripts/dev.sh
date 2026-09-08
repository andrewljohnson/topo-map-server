#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
pids=()
trap 'for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done' EXIT INT TERM
services/tiles/.venv/bin/python services/tiles/tile_service.py serve &
pids+=("$!")
(cd apps/web && pnpm dev --host 0.0.0.0 --port 3000) &
pids+=("$!")
wait -n
