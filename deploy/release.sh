#!/usr/bin/env bash
# Runs on the target server after an immutable git archive has been uploaded.
set -euo pipefail
root=$1
export RELEASE_SHA=$2
[[ $RELEASE_SHA =~ ^[0-9a-f]{40}$ ]] || exit 2
release=$(cd "$(dirname "$0")/.." && pwd)
exec 9>"$root/deploy.lock"
flock -n 9 || { echo 'Another release is running.' >&2; exit 1; }
set -a
source "$root/server.env"
set +a
[[ ${DATA_DIR:-} == /* && -d $DATA_DIR ]] || { echo 'DATA_DIR must be an existing mounted directory.' >&2; exit 1; }
: "${SITE_ADDRESS:?Set SITE_ADDRESS in server.env}"
: "${SECRETS_DIR:?Set SECRETS_DIR in server.env}"
for file in storage.env access.json client.token warm.token; do
  test -s "$SECRETS_DIR/$file" || { echo "Missing $SECRETS_DIR/$file" >&2; exit 1; }
done
header=$(mktemp)
chmod 600 "$header"
trap 'rm -f "$header"' EXIT
printf 'Authorization: Bearer %s\n' "$(cat "$SECRETS_DIR/client.token")" > "$header"
compose() { docker compose -p topo-map -f "$1/deploy/compose.yaml" "${@:2}"; }
previous=$(readlink -f "$root/current" || true)
# Building leaves the current site and warmer running.
compose "$release" build --pull tiles web
was_warming=false
if docker ps --filter label=com.docker.compose.project=topo-map --filter label=com.docker.compose.service=warmer --format '{{.ID}}' | grep -q .; then was_warming=true; fi
if [[ -n $previous && -f $previous/deploy/compose.yaml ]]; then
  compose "$previous" --profile warm stop warmer
fi
rollback() {
  echo 'Release failed; restoring the previous release.' >&2
  if [[ -n $previous && -f $previous/.release-sha ]]; then
    export RELEASE_SHA=$(cat "$previous/.release-sha")
    compose "$previous" up -d --no-build --wait --wait-timeout 180 tiles web
    if $was_warming; then compose "$previous" --profile warm up -d --no-build warmer; fi
  fi
}
if ! compose "$release" up -d --no-build --wait --wait-timeout 180 tiles web; then
  rollback; exit 1
fi
# Verify actual page and API through the public HTTPS listener, not just a process.
if ! curl --fail --silent --show-error --retry 8 --retry-all-errors --retry-delay 5 --max-time 20 "https://$SITE_ADDRESS/" -o /dev/null ||
   ! curl --fail --silent --show-error --header "@$header" --max-time 20 "https://$SITE_ADDRESS/metadata" -o /dev/null ||
   ! curl --fail --silent --show-error --header "@$header" --max-time 120 "https://$SITE_ADDRESS/tiles/0/0/0.pbf" -o /dev/null ||
   ! curl --fail --silent --show-error --header "@$header" --max-time 120 "https://$SITE_ADDRESS/dem/3/1/3.png" -o /dev/null; then
  rollback; exit 1
fi
printf '%s\n' "$RELEASE_SHA" > "$release/.release-sha"
ln -s "$release" "$root/current.next"
mv -Tf "$root/current.next" "$root/current"
# Persist an operator pause across releases by creating $root/warming-paused.
if [[ ! -e $root/warming-paused ]]; then
  compose "$release" --profile warm up -d --no-build warmer
fi
printf '%s %s\n' "$(date -u +%FT%TZ)" "$RELEASE_SHA" >> "$root/releases.log"
echo "Live: https://$SITE_ADDRESS"
