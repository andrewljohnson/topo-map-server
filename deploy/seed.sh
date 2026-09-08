#!/usr/bin/env bash
set -euo pipefail
root=$1
mode=$2
release=$(cd "$(dirname "$0")/.." && pwd)
source "$root/server.env"
[[ ${DATA_DIR:-} == /* && -d $DATA_DIR ]] || exit 1
if [[ $mode == check ]]; then
  cd "$DATA_DIR"
  sha256sum --status -c "$release/deploy/seed-data.sha256"
  exit
fi
[[ $mode == install ]] || exit 2
cd "$release/.seed-staging"
sha256sum -c "$release/deploy/seed-data.sha256"
# Never silently replace a differently versioned production source index.
while read -r digest name; do
  if [[ -e $DATA_DIR/$name ]]; then
    actual=$(sha256sum "$DATA_DIR/$name")
    [[ ${actual%% *} == "$digest" ]] || { echo "Existing seed differs: $name. Version the source path before replacing it." >&2; exit 1; }
  fi
done < "$release/deploy/seed-data.sha256"
while read -r digest name; do
  mkdir -p "$DATA_DIR/$(dirname "$name")"
  if [[ ! -e $DATA_DIR/$name ]]; then
    cp "$name" "$DATA_DIR/$name.incoming"
    mv "$DATA_DIR/$name.incoming" "$DATA_DIR/$name"
  fi
done < "$release/deploy/seed-data.sha256"
