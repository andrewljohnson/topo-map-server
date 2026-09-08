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
