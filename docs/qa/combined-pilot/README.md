# Combined pilot validation

Release `topo-z12-pilot-20260909` is promoted to the public default manifest.
The website and Expo's default API now advertise exactly `osm` and `dem`.
Detailed coverage is Tahoe/San Francisco; this does not start nationwide production.

The same 80-parent fixture with eight workers took 85.77 seconds under competing
workloads and 53.20 seconds after the user freed CPUs (38% less elapsed time).
Both runs regenerated derived vectors with retained sources. This single comparison
also includes filesystem-cache effects; it is not a cold-source national forecast.
Packing fell from 25.27 to 15.29 seconds. DEM generation fell from 4.17 to 2.89 seconds.

The real mobile TileStore downloaded 37 unique base/DEM tiles for two Tahoe/SF
cells, then reopened every file with network disabled. DEM dimensions were 1024
pixels, batch and direct vectors decoded, and seeded notes/GPS remained intact.
This uses the real cloud service and queue with an in-memory filesystem; it is
not a physical iPhone background-download test. Two consecutive final runs took
21.88 and 14.27 seconds, including direct-tile and metadata checks.

Live validation caught an edge-cache defect: cache hits could lose Content-Encoding
while retaining gzip bytes. The Worker now stores opaque compressed bytes with an
internal encoding header and restores the HTTP header on retrieval. A cache-round-
trip regression test and the two live offline checks pass. The cache namespace was
changed so old entries cannot be reused. Eight Worker tests pass.

Publication resume verified all 352 ledger objects without repeating generation.
The previous manifest is retained for the documented rollback command.
