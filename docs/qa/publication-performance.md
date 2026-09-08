# Local publication performance — September 7, 2026 PDT

The California DEM zoom-12 pass is network-heavy. At 16 workers, the first
128-second instrumented sample spent 1,699 summed worker-seconds rendering DEM
and 270 publishing it (remote lookup, upload and verification). These are
concurrent worker times, not elapsed wall time. More CPU was not the first lever.

A 32-tile replay from already-published DEM blocks, using eight threads, took
5.20 seconds without memory reuse, 4.62 seconds with a cold 64-block memory cache,
and 4.56 seconds with a warm cache. SHA-256 hashes of every encoded PNG were
identical across all three passes. This is a hot-disk microbenchmark, not a
prediction for untouched terrain. Replay did not upload more objects.

The running service now uses 32 workers, a rolling lookahead of 128 tiles, and
a bounded 64-block read-only DEM cache. Existing CPUQuota=600%, MemoryHigh=10G,
MemoryMax=12G, source disk-cache ceiling, 50 GB local free-space reserve and
1 TB publication ceiling remain unchanged. R2 object verification is unchanged.

A live post-startup sample published **1165 tiles in 290.2 seconds
(4.01 tiles/second)**. The earlier 16-worker run sustained about
2.2 tiles/second. Different terrain and existing source-cache contents prevent a
controlled causal comparison; do not extrapolate this sample unchanged to all
CONUS layers. Publisher memory was about 3 GB, CPU remained below its cap, and
training was left running.

Validation: 5 raw DEM tests, 9 national contour/source tests, 4 publication
scheduler/order tests and 9 cloud storage tests passed. The new memory-cache
regression checks immutable arrays, namespace isolation and bounded eviction.

For subsequent comparisons, use differences in completed upload-ledger counts
over several minutes. Status `performance` counters reset on publisher restart.
Compare similar source/zoom runs, exclude startup, note cache and terrain changes,
and investigate errors or CPU/memory pressure before increasing concurrency.

## September 8 follow-up: connection lifetime

The heartbeat found repeated SQLite `unable to open database file` failures during
OSM zoom-13 publication. The transaction context did not close connections. With
garbage collection disabled, 120 sequential ledger reads grew the process's open
file count from 4 to 124, reproducing the resource leak independently of R2.

`Publisher.db()` now commits/rolls back and always closes in `finally`. A regression
performs 1,200 reads with garbage collection disabled and checks that file handles
stay bounded; another verifies commit, rollback, and closure on both exit paths.
Six publication tests and nine cloud storage tests passed.

After restart, a live 80.7-second sample completed 8,425 OSM tiles (104.4/sec),
kept the same process with zero automatic restarts, and held open handles at 37.
Memory was about 250 MB and CPU well below the existing six-core cap. This OSM
section has small payloads and is not comparable to terrain throughput; do not
extrapolate its rate to dense base-map tiles or DEM. California DEM zoom 12 has
reached its planned 12,989 tiles; zoom 13 DEM and the remaining base-map/enrichment
passes still need publication.

## September 8 import retry and native filtering

The hourly check at 08:07 PDT found that the US source import had reset from
3.78 million selected features/tags to 120,000, without a service restart.
The old retry path overwrote its error status and did not log the exception.
The cause of that failure is not yet established. Import failures now preserve
`osm-source/import-error.json` and a traceback in the service journal.

The installed pyosmium `SimpleHandler._apply_object` places node-location and
area-assembly handlers before callback filters. Enabling its native EmptyTagFilter
therefore eliminates Python callbacks for irrelevant untagged objects while
retaining node coordinates and untagged polygon-member ways. A real import test
compares all feature, extent, waterway and metadata rows against the unfiltered
path, including a multipolygon with an untagged outer way: identical results.
A 200,000-node fixture (200 selected amenities) took 1.31 seconds unfiltered and
0.173 seconds filtered, with identical selected features. This microbenchmark is
not a nationwide import ETA. The running import was restarted to apply the change
and retain failure evidence rather than silently repeating another long pass.

The service now explicitly sets TILE_MIN_FREE_GB=50 for import, matching the
existing publisher free-space reserve. Bulk query connections now close explicitly,
preventing the same file-handle accumulation previously fixed in the publisher.

## September 8: confirmed import failure

The optimized pass reached the original failing stage in about 57 minutes
(previous unfiltered attempt took roughly 3 hours 40 minutes). Retained diagnostics
identified `RuntimeError: invalid area (area_id=250220764)` from libosmium's
multipolygon factory. The importer now records only this recognized invalid-area
failure and continues, preserving the earlier way geometry if available. Other
factory failures still propagate and prevent an incomplete index being published.
Six bulk-import tests and the preparation-diagnostics test pass. Existing valid
feature processing and published tile bytes are unchanged. The next full pass
must still confirm that no other source error prevents completion.

Restarting after the fix released resources retained by failed imports; free disk
space recovered from 63 GiB to 111 GiB. The 50 GB reserve remains enforced.
