# Cloudflare map delivery

The Worker serves the existing static web app and private XYZ/batch API from R2.
It never runs DEM processing or downloads geographic sources. The local publisher
renders data and verifies immutable R2 uploads before checkpointing progress.

## Credentials

`~/.config/topo-map/cloudflare.env`, mode 600:

```
CLOUDFLARE_ACCOUNT_ID=...
R2_BUCKET=topo-map-tiles
R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
```

Use `source scripts/env.sh` then `pnpm --dir apps/web exec wrangler login` for
Worker deployment authorization. No AWS account or additional manually saved API
token is required. R2 remains private, including its r2.dev domain.

## Releases

Commit directly to main, then run `scripts/deploy.sh`. It selects fetched remote
main if configured, otherwise committed local main, extracts an isolated release,
installs frozen dependencies, tests the Worker, builds the website and deploys.
Client and publisher keys are generated once outside Git. Verification hashes are
Worker secrets. Authorized and unauthorized live smoke tests run after deployment.
The old VPS deployment remains available only through `scripts/deploy-server.sh`.

The website and mobile Map server dialog use the URL recorded in
`~/.config/topo-map/deployment.json`. Enter the key from `client.token`; never enter
R2 credentials into the app. The browser stores its key for the tab session, and
Expo uses SecureStore. Background native download sessions include authorization.

## Publication

```
services/tiles/.venv/bin/python services/tiles/publish_cloud.py --sample
services/tiles/.venv/bin/python services/tiles/publish_cloud.py
```

The sample publishes world z0–3 and a small multi-layer area at Fallen Leaf Lake.
The full job publishes world z0–7, California core detail, CONUS core detail,
then California and CONUS supplementary layers. Existing valid development cache
is reused. No generated full-country tile tree is created locally; new output is
held in memory until its PUT and verification finish. Uploads use two threads.
The SQLite journal lives in `services/tiles/data/publication/uploads.sqlite`.
**Preserve this journal**: it provides immutable checksums, resume cursors and the
storage ledger. A populated bucket with no journal is rejected for manual recovery.
A successful upload is verified by content length and stored SHA-256 metadata.

Defaults: 1 TB publication ceiling, 50 GB free disk reserve, replaceable source
scratch target 30 GB. Development cached tiles, source indexes and provenance are
not pruned. Raw-source import may pause if the reserve is reached. Pause/resume the
local job with `systemctl --user stop/start topo-map-publisher` when installed.

The local JSON status file and authenticated `/publication` endpoint expose uploaded
count/bytes, current source/zoom and errors. `complete` is written only after every
planned tile succeeds. A partial sample is not nationwide coverage. While publication
runs, unpublished detail returns 404 and batches report per-tile failures; existing
coarse tiles remain available, but clients opening directly on an unpublished deep
zoom can show gaps until parent coverage is loaded. Improve explicit parent fallback
before treating partially warmed deep views as fully supported.

## Controls and priorities

A Durable Object atomically meters all authenticated API calls, including cache hits:
100 GB/month and one million requests/month; 1,200 requests/minute. Batches contain
at most eight tiles, individual tiles at most 4 MB, Worker CPU is limited to 100 ms.
Cached objects stay behind the authentication and metering path; responses are
private/no-store. The cache only contains immutable tile responses or short-lived
publication metadata. ACCESS_DISABLED=1 stops client delivery. Rotate/revoke the
ACCESS_SHA256 secret to revoke the client key. No credentials appear in URLs.

Missing requests add at most 256 deduplicated jobs to a Durable Object queue. The
publisher polls it using its separate warm.token, prioritizing eligible CONUS tiles.
Supplementary priorities wait for the local bulk OSM index. The operator endpoint is
not available to the client key. Already published maps work while this computer is
off; new detail waits. No unbounded cloud generation can be triggered by browsing.

Application quotas do not cap the entire provider invoice. Stored data still costs
money, and rejected requests can incur Worker costs. Only this publisher should write
to the bucket; manually adding objects bypasses its storage ledger. Restoring old
usage ledgers or deleting Durable Objects resets accounting and must be deliberate.

## Validation

`node --test services/cloud/worker.test.mjs` tests auth, revocation, byte/request
limits, concurrent reservations, batch bounds and missing tile responses.
Python service tests and `scripts/test-deploy.py` cover local storage/coverage and
committed-main release selection. Live smoke tests verify the actual Cloudflare path.
