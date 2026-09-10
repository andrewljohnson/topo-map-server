# California demo release — active

User authorized full California on public website and new distributable iOS app, with QA and later improvements in parallel.

- Frozen checkout: `/tmp/topo-california-release-20260909`, commit `320ee2b`. Do not modify its processing inputs.
- Release: `topo-california-20260909-r1`, scope `california`, 16 workers, 256-parent rolling shards. 17,838 base/overview objects + 13,734 DEM objects. Includes existing Tahoe Nevada-side pilot. Broad world z0–3.
- Running publisher execution session: 48305. Log `/tmp/topo-california-20260909-r1.log`. Check process/status before resuming; detached nohup attempt did not persist, foreground session did.
- Status/checkpoints: `services/tiles/data/publication/combined/topo-california-20260909-r1/`. Shared raw data via symlink, disposable bounded shard spool, 50 GB disk reserve. Snapshot has independent git metadata and shared Python venv.
- Re-run exact publish command from frozen checkout to resume checkpoints, never from changing main: `services/tiles/.venv/bin/python services/tiles/publish_combined.py publish --scope california --release topo-california-20260909-r1 --workers 16`.
- Do not promote until complete + coverage ledger verified + representative visual and actual TileStore offline tests. Existing default r14 remains live until then.
- Mobile 131 tests and typecheck passed. Inspect `/tmp/topo-california-eas-before.json` for recent builds; new internal iOS build still to start. `pnpm dlx eas-cli` is available via `source scripts/env.sh`; npx is not installed in bundled runtime.
- QA subagent `/root/map_qa` is inspecting r14 read-only and reports findings separately; no release code mutation allowed. Cathedral Spur remains uncertain, not blindly removed.
- Hourly heartbeat `map-publication-progress` resumed for this release and build; no national generation/rented compute.

Complete representative QA at Tahoe, Yosemite, SF, Los Angeles, San Diego, north coast, Shasta, and desert; verify two tile sets and downloads. Promote from frozen checkout using same scope/release. Deliver public map + iOS install link and pause heartbeat once done. Future app/cartography edits happen on main and cannot mutate this release; use new immutable IDs for processing changes.

## iOS build submitted

EAS internal preview build `a87dcaeb-9864-4691-9f54-4d26c5af9a80` submitted successfully from main after 131 tests/typecheck. Existing signing profile verified both registered phones. Build URL: https://expo.dev/accounts/andrewljohnson/projects/topo-map-server/builds/a87dcaeb-9864-4691-9f54-4d26c5af9a80 . Log `/tmp/topo-california-eas-build.log`. Query this ID before starting another build. Full California data is not yet promoted; the build uses the current live manifest and will pick it up after promotion. First two publication overview batches uploaded successfully; disk free roughly 72 GiB.

## First hourly follow-up — 2026-09-10 00:52 UTC

iOS EAS build finished successfully at 23:57 UTC; existing build page is the install entry point for both registered phones. No replacement build submitted.

California publisher paused after 970 seconds on a transient SSL handshake timeout fetching DEM source data in detail shard 4. All 19 overview shards and first 4 detail shards were verified; approximately 6,875 tile objects plus release documents had uploaded. Disk free ~71 GiB. No live promotion occurred.

Confirmed publisher stopped, then resumed unchanged frozen release through `/tmp/topo-california-supervise.py`, execution session 42898, supervisor log `/tmp/topo-california-supervise.log`. Wrapper retries at most six attempts only for recognized transient network failures; other errors stop for review. It does not alter immutable code, inputs, or checkpoints. Resumed shard 4 generation completed in 6.4 seconds using saved work, began uploading, and shard 5 generation started. Status elapsed/startedAt reset per invocation; use original start 2026-09-09 23:52 UTC and completed checkpoint counts for total progress. Avoid duplicate supervisors: lock `/tmp/topo-california-supervise.lock`.

Preflight QA remains documented in `california-demo-preflight-2026-09-09.md`; garden path density and uncertain spur geometry are nonblocking separate follow-ups. Keep full-state visual/offline checks as the promotion gate.

## Coverage complete; delivery gate fix — 2026-09-10

All 31,572 objects verified; exact manifest coverage matches plan (13,182 detail bases, 4,656 overviews, 13,734 DEMs). Stored bytes 12,875,356,383. Eight-region browser visual QA passes, but actual TileStore test exposed Cloudflare 1102 resource-limit 503s on large DEM batches. Do not promote until rerun succeeds.

Delivery fix on main (separate from immutable tile generator): replace per-byte JS binary-string construction with native `node:buffer` base64 encoding, opt into nodejs compatibility, increase explicit CPU ceiling from 100 to 500 ms for bounded large batches. Existing request/byte quotas and decoded-size limits remain. Ten Worker tests pass, including four 1 MiB binary DEMs with all byte values and byte-quota accounting. Cloudflare documents [native Buffer support](https://developers.cloudflare.com/workers/runtime-apis/nodejs/buffer/) and [1102 resource limits](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1102/). Deploy then repeat real eight-region download/offline gate. Test script `/tmp/check-california-r1.mjs`, failure diagnostics `/tmp/topo-california-download-debug.json`.

## Complete — California live

Promoted `topo-california-20260909-r1` after all gates passed. Default public `/metadata` and `/publication` both confirm this release, status complete, 17,838 base/overview and 13,734 DEM tiles. Website: https://topo-map.andrewljohnson.workers.dev/ . iOS install: https://expo.dev/accounts/andrewljohnson/projects/topo-map-server/builds/a87dcaeb-9864-4691-9f54-4d26c5af9a80 . Existing app/Expo picks up the new cloud manifest on reload.

Worker delivery fix deployed from `a321372`, Cloudflare version `f38f81bc-01ef-49f8-901d-19654ca59264`. Eight-region actual TileStore rerun passed: 134 unique tiles in 13.875 seconds, all eight region queues complete, zero request errors, offline reload succeeds, 1024px DEM and notes/GPS fixtures preserved. This uses the real mobile storage/queue implementation with an in-memory filesystem; it is not manual airplane-mode testing on the physical phones.

[Exact coverage/object evidence](california-demo-2026-09-09/coverage.json), [download/offline results](california-demo-2026-09-09/offline.json), [eight-region browser QA](california-demo-2026-09-09/visual.md). The iOS build finished successfully and its provisioning profile included both phones; device installation remains the user's action. No additional build required for the server-only batch encoding fix.

Nonblocking follow-ups: residential/private swimming-pool icon clutter in Los Angeles, dense garden-path styling in SF/San Diego, uncertain Cathedral Spur source geometry. Do not silently remove uncertain paths. Publication monitoring can stop now that data and install link are delivered.
