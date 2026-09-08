#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec services/tiles/.venv/bin/python services/tiles/publish_cloud.py "$@"
