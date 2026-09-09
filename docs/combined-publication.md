# Combined base map / DEM releases

The production candidate uses one namespaced vector dataset and one Terrarium
DEM dataset. Detailed vectors stop at z12 (extent 16384); DEMs are 1024×1024 at
z12. The client overzooms these and computes contours/relief locally. Lower vector
zooms retain their native source extent. Static symbols/borders remain bundled.

## Pilot scope

`topo-z12-pilot-20260909-r2` contains 80 detailed base tiles around Tahoe and San
Francisco, 140 DEM tiles including halos, and 132 native overview tiles. The
worldwide portion is z0–3 for this pilot; regional ancestors extend through z11.
Outside those exact published regions, the broad overview remains visible.
This is not California or CONUS completion. The nationwide scope is separate and
increases world overview to z7. Do not start it until the pilot is accepted.

## Commands

Run with the repository Python environment. Commit the source first; the release
contract records its content fingerprint, Git revision, source datasets and exact
coverage plan. Reusing a release ID with changed processing code is rejected.

```sh
services/tiles/.venv/bin/python services/tiles/publish_combined.py plan --release topo-z12-pilot-20260909-r2
services/tiles/.venv/bin/python services/tiles/publish_combined.py publish --release topo-z12-pilot-20260909-r2
```

Repeat the same publication command to resume. A candidate manifest appears only
after all expected base and DEM keys are verified. Each upload is checked by
reading the object back and hashing its actual bytes, including gzip encoding.
The durable shared ledger is `services/tiles/data/publication/uploads.sqlite`.
Release contracts, plans, reports and completion markers live under
`services/tiles/data/publication/combined/RELEASE/` and must be retained.

The candidate API is `/releases/RELEASE/metadata`; its tile URLs are pinned to that
release. Browse the candidate website with `/?release=RELEASE`. Existing clients
keep their existing manifest until promotion. Code releases still use
`scripts/deploy.sh`, which builds and deploys committed remote main.

After online/offline validation:

```sh
services/tiles/.venv/bin/python services/tiles/publish_combined.py promote --release topo-z12-pilot-20260909-r2
# Restore the saved previous manifest if needed:
services/tiles/.venv/bin/python services/tiles/publish_combined.py rollback --release topo-z12-pilot-20260909-r2
```

Promotion changes only the current manifest pointer, with up to 30 seconds of
metadata caching. Old release-pinned tile URLs continue working. Mobile reloads
metadata, uses new dataset IDs to separate tile files, and retains notes/GPS in
separate files. Old saved map selections may reset for this incompatible format;
old binary caches are not reused as new-format tiles. Expo development reload
still clears only its map cache as requested previously.

## Bounded processing and recovery

- Sixteen CPU processes by default (configurable from 1–32) generate spatial shards of up to 512 z12 parents (default
  256), with separate sixteen-thread native DEM prefetch.
- One upload shard overlaps generation of the next. Uploads have eight threads;
  an upload backlog blocks further generation. At most two shards are in flight.
- Resume reuses completed derived work and verified uploads. A shard completion
  marker is durable before its disposable output tree is removed.
- Only this release's `spool/` directory is removed. Existing raw sources, sample
  tiles, notes and GPS are untouched. Missing native DEM/NLCD raster inputs go to
  that shard's scratch directory; existing cached inputs are read in place.
  Source catalogs and other source indexes persist for provenance/reuse.
- Generation stops on errors, a 50 GB disk reserve, or a 25 GB spool ceiling.
  Run the same command after correcting the cause; failed data is never recorded
  as empty coverage. Large persistent source-index growth can still require
  intervention; the reserve protects other machine workloads.
- The existing global publisher lock prevents concurrent old/new publishers.
  The old nationwide service stays disabled.

## Delivery contract

HTTP vector responses carry `Content-Encoding: gzip`. Batch JSON contains decoded
MVT bytes in base64 so native downloads and the WebView use the same parser path.
Combined sets advertise four-tile batches. Decode limits cap individual raw vectors
at 4 MB and each batch at 16 MB, in addition to existing request/byte quotas.
Pilot coverage lists exact tile-row ranges. Known out-of-coverage base requests
return a valid empty MVT, exposing the broad overview underneath; absent *planned*
objects still fail and remain retryable. Offline selection skips unpublished keys.
The two separated DEM view bounds avoid requesting DEMs throughout the gap between
Tahoe and SF.

## Angora Ridge Road

At z11 the USFS MVUM record identifies asphalt (`AC - ASPHALT`) and seasonal
passenger-car access. OSM omits that small road from its coarse tile, so the MVUM
record supplies it. Previously every MVUM road was classified as a track and given
a dashed centerline. At fine zooms the same road is already conflated with OSM,
retaining OSM geometry/class plus USFS source records and access dates.

The v4 trail processor classifies explicitly paved MVUM roads as ordinary roads;
overview paint uses a solid pale road with a gray casing. Other tracks retain their
track styling. The combined renderer uses the conflated network starting at z12,
removing the unnecessary z13 geometry handoff. Same-name trail/track/service
segments remain separate where the data describes different segments; no blanket
name-based merging or removal is used.

## Additional road and CPU validation

The v5 road processor and the refreshed pilot cover name/reference matching and
conservative rural alignment correction across all 640 fine Tahoe source tiles.
See [road and worker proof](qa/road-merging/README.md) for rules, residual review
candidates, before/after geometry and measured CPU scaling. No nationwide run
is started by these changes.
