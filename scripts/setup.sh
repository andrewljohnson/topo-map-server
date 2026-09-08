#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
python3 -m venv services/tiles/.venv
services/tiles/.venv/bin/python -m pip install -r services/tiles/requirements.txt
services/tiles/.venv/bin/python services/tiles/tile_service.py warm --min-zoom 0 --max-zoom 2
(cd apps/web && pnpm install --frozen-lockfile)
(cd apps/mobile && pnpm install --frozen-lockfile && pnpm bundle:map)
