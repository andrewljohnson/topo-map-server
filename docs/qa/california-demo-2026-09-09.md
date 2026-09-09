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
