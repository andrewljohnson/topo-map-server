#!/usr/bin/env bash
# Prefer normal developer tooling; use the installed Codex runtime on this host.
TOPO_RUNTIME="${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if [ -d "$TOPO_RUNTIME/node/bin" ]; then
  export PATH="$TOPO_RUNTIME/node/bin:$TOPO_RUNTIME/bin/fallback:$PATH"
fi
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/topo-pnpm-cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-/tmp/topo-pnpm-data}"
export EXPO_NO_TELEMETRY=1
export __UNSAFE_EXPO_HOME_DIRECTORY="${__UNSAFE_EXPO_HOME_DIRECTORY:-/tmp/topo-expo}"
