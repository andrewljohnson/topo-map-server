# California r2 release — 2026-09-09

Dataset: `topo-california-20260910-r2`. Generation source is immutable commit `1210b40` in `/tmp/topo-california-release-r2`. Gazetteer and label-ranking SQLite databases were copied with SQLite backup into this checkout; other source caches and publication spool are shared. Do not modify frozen processing code or pinned databases.

The release addresses both reported PCT survey duplicates, Halfmoon Campground, Three Brothers, and developed-area walkway hierarchy. Source regression tests and exact-location local browser proof passed. Separate client coverage fixes prevent out-of-publication DEM requests and misleading global failure banners; Nevada → Fallen Leaf and rapid zoom 18→9→16 passed against public r1 without reload. The 71,550 MapLibre allocation warning is not proof of an actual vertex overflow; no library patch was made. Location denial is a browser permission issue.

## Active publication

Supervisor `/tmp/topo-california-r2-supervise.py`, lock `/tmp/topo-california-r2-supervise.lock`, log `/tmp/topo-california-r2-supervise.log`. Publisher log `/tmp/topo-california-20260910-r2.log`. Started in terminal session 18976. Supervisor retries up to six recognized transient network failures, preserving checkpoints.

Status: `services/tiles/data/publication/combined/topo-california-20260910-r2/status.json`. Expected 17,838 base/overview and 13,734 DEM objects. Sixteen workers; retain 50 GB free-disk floor. Do not start duplicate publishers. Existing complete California r1 remains live while this runs.

## Completion gate

Check complete manifest/object ledger and candidate cloud metadata. Adapt `/tmp/check-california-r1.mjs` for r2 and verify actual TileStore batch downloads, offline reload, DEM decoding, and preservation of notes/GPS. Visually check the five reported coordinates plus representative California regions through the candidate release before promoting. Promote only from the frozen r2 checkout with `services/tiles/.venv/bin/python services/tiles/publish_combined.py promote --scope california --release topo-california-20260910-r2`. Verify default public metadata/publication afterwards.

Latest client fixes must be committed, pushed, deployed and included in a new internal iOS preview build for the two registered phones. Previous working build: https://expo.dev/accounts/andrewljohnson/projects/topo-map-server/builds/a87dcaeb-9864-4691-9f54-4d26c5af9a80 . Expo map development server is port 8081; leave the unrelated app on 8082 alone.

Report progress hourly and immediately on required user action or completion. Continue through recoverable failures. Delete the release heartbeat once promotion and delivery are complete.

## Client delivery status

Coverage fix commit `dd65d93` is pushed and deployed to the existing public map; Cloudflare version `d70b768f-7987-4e75-a41e-0b93be05e26f`. Deployment tests and live smoke checks passed. Final mobile checks: 134 tests passing and clean typecheck.

New internal iOS build submitted with both existing registered phones: `efe580bb-6b2e-47f3-9442-73ef902d52e3`, https://expo.dev/accounts/andrewljohnson/projects/topo-map-server/builds/efe580bb-6b2e-47f3-9442-73ef902d52e3 . Check this build rather than submitting another. Submission log `/tmp/map-r2-ios-submit.log`.

Hourly follow-up is active as `california-r2-release-progress`. California r2 is still generating; r1 remains the public dataset.

## Superseded by r3 after source geometry failure

At 46.7 minutes r2 stopped on detail-24 after 17,365 verified upload operations. A self-intersecting source building at z14/2631/6352 caused GEOS intersection to fail in developed-walkway context. No public pointer was changed. Do not resume r2 with changed code.

The fix repairs invalid buildings with `make_valid` before clipping and retains polygon components, including nested collections. Eight path-context tests, 112 national-source tests, and real building indexes across the 3×3 failure neighborhood pass. Dataset versions advance to basemap v11/trails v15. A new immutable release `topo-california-20260910-r3` uses `/tmp/topo-california-release-r3`, with the same pinned gazetteer/ranking inputs copied from r2. Supervisor `/tmp/topo-california-r3-supervise.py`, log `/tmp/topo-california-r3-supervise.log`, publisher log `/tmp/topo-california-20260910-r3.log`. Apply all completion gates above to r3 instead. r2 remains unpromoted.

The iOS build `efe580bb-6b2e-47f3-9442-73ef902d52e3` is FINISHED (2026-09-10 03:16 UTC) and ready to install on both registered phones. No new native build is needed for the server-only geometry repair.

## Follow-up after the frozen r3 release

New user report at Twin Peaks (-120.23739,39.10252) exposed a remaining USFS/PCT survey overlap in r1 and frozen r3. Follow-up source code on main (official trails v16) uses the complete PCTA catalogue plus OSM for main-PCT geometry; redundant USFS main-PCT remains metadata-only through strict matching. Tests preserve alternate/spur/other routes and OSM geometry. See `docs/qa/pct-twin-peaks-2026-09-10/source-policy.md`.

Do not silently mutate or restart frozen r3 for this follow-up. Finish its verified publication, then freeze a subsequent immutable candidate from main with the v16 fix and run the same generation/QA/promotion gates. The report's PCT must be included in that candidate's visual checks. Keep hourly monitoring active until the follow-up fix is published; do not claim r3 fixes this location. No new iOS binary is required for this server tile-data change.

## R3 live; r4 follow-up

R3 completed in101.9minutes with all31,572objects verified. Eight-region actual TileStore/offline test and cloud visual gates passed; see `docs/qa/california-r3/README.md`. Promoted successfully: default `/metadata` and `/publication` now confirm `topo-california-20260910-r3`, completeCalifornia,17,838base and13,734DEM. Previous manifest is retained in r3's `previous-metadata.json` for rollback.

Follow-up `topo-california-20260910-r4` is being frozen at `/tmp/topo-california-release-r4` from current main with trailsv16. Pin gazetteer/ranking databases from r3, share source caches/publication spool, initialize snapshot Git provenance, then run `/tmp/topo-california-r4-supervise.py`. Supervisor log `/tmp/topo-california-r4-supervise.log`; publisher log `/tmp/topo-california-20260910-r4.log`. Do not run r3 again. R4 needs all standard completion gates plus the TwinPeaks PCT cloud view before promotion. Expected measured generation/publication time approximately100minutes beforeQA; preserve50GBdisk floor. Existing publicr3 stayslive while it runs.

## Complete: r4 live

`topo-california-20260910-r4` is now the default public map release. All 31,572 objects verified; generation/publication took 96.5 minutes. Eight-region TileStore/offline checks and cloud visual checks passed, including the Twin Peaks PCT switchbacks, both earlier PCT reports, Halfmoon and Three Brothers. Evidence is in `docs/qa/california-r4/`.

No publication jobs remain for this release. The internal iOS build already delivered uses the public API and needs no rebuild for this tile correction. Release heartbeat can be deleted. Nearby TRT overlap remains an explicitly recorded independent cartographic QA issue.
