#!/usr/bin/env bash
# Release only committed main. No working-tree files or local secrets are uploaded.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f deploy/deploy.env ]]; then source deploy/deploy.env; fi
remote=${DEPLOY_REMOTE:-origin}
if git remote get-url "$remote" >/dev/null 2>&1; then
  git fetch --no-tags "$remote" main
  sha=$(git rev-parse --verify 'FETCH_HEAD^{commit}')
else
  sha=$(git rev-parse --verify 'refs/heads/main^{commit}') || {
    echo 'No committed main branch. Commit the project to main before releasing.' >&2; exit 1;
  }
fi
git cat-file -e "$sha:deploy/release.sh" || {
  echo 'Deployment files must be committed to main first.' >&2; exit 1;
}
if [[ ${1:-} == --dry-run ]]; then
  echo "Would deploy committed main revision $sha to ${DEPLOY_HOST:-<not configured>}"
  exit 0
fi
[[ $# == 0 ]] || { echo 'Usage: scripts/deploy.sh [--dry-run]' >&2; exit 2; }
: "${DEPLOY_HOST:?Copy deploy/deploy.env.example to deploy/deploy.env and set DEPLOY_HOST}"
root=${DEPLOY_ROOT:-/srv/topo-map}
[[ $DEPLOY_HOST =~ ^[a-zA-Z0-9_@.:-]+$ && $DEPLOY_HOST != -* ]] || exit 2
[[ $root =~ ^/[a-zA-Z0-9_/-]+$ && $root != / ]] || exit 2
# A unique immutable checkout per attempt also makes repeating a release safe.
release="$root/releases/$sha-$(date -u +%Y%m%dT%H%M%S)-$$"
ssh "$DEPLOY_HOST" "test -f '$root/server.env' && command -v docker >/dev/null && mkdir -p '$root/releases' && mkdir '$release'"
git archive "$sha" | ssh "$DEPLOY_HOST" "tar -xf - -C '$release'"
# Small, versioned source indexes are release inputs; the huge tile cache is not.
if ! ssh "$DEPLOY_HOST" "bash '$release/deploy/seed.sh' '$root' check"; then
  manifest=$(mktemp)
  trap 'rm -f "$manifest"' EXIT
  git show "$sha:deploy/seed-data.sha256" > "$manifest"
  seed_source=${SEED_DATA_DIR:-$PWD/services/tiles/data}
  (cd "$seed_source" && sha256sum -c "$manifest")
  mapfile -t seed_names < <(awk '{print $2}' "$manifest")
  ssh "$DEPLOY_HOST" "mkdir '$release/.seed-staging'"
  tar -czf - -C "$seed_source" "${seed_names[@]}" | ssh "$DEPLOY_HOST" "tar -xzf - -C '$release/.seed-staging'"
  ssh "$DEPLOY_HOST" "bash '$release/deploy/seed.sh' '$root' install"
fi
ssh "$DEPLOY_HOST" "bash '$release/deploy/release.sh' '$root' '$sha'"
echo "Released $sha. The nationwide job continues independently of this terminal."
