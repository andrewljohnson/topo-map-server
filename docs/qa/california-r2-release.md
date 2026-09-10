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
