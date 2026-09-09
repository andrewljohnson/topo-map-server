# Tahoe zoom-12 experiment

Nationwide publication is paused. The user has authorized measured 10× and
further representative scale tests to support a detailed-CONUS plan targeting
three days or less. Do not restart the old publisher, launch nationwide
generation, or provision paid compute without the next explicit go-ahead.

The first fixture is four zoom-12 tiles around Fallen Leaf Lake and Tahoe's south
shore: x=681–682, y=1566–1567. It is a small performance/correctness fixture, not
all of Lake Tahoe. The app experiment delivers one combined vector source and one
separate raw DEM source, both capped at zoom 12. MapLibre overzooms vectors; the
existing device contour worker generates contour geometry at the display zoom.

## Run locally

From the repository root:

```sh
services/tiles/.venv/bin/python experiments/tahoe/build.py --workers 2
services/tiles/.venv/bin/python experiments/tahoe/serve.py
```

With the existing web dev server on port 3000, open
<http://localhost:3000/experiment>. Port 3012 serves the experiment's files only;
it cannot generate tiles on demand. The viewer is constrained to the fixture.
On a phone on the same Wi-Fi, use `http://<computer-LAN-IP>:3000/experiment`
in Safari, not `localhost`. Start the web dev server with
`pnpm dev --hostname 0.0.0.0 --port 3000` from `apps/web` (`--host` is not the
vinext hostname option). The tile server must also be running on port 3012;
the viewer uses the same hostname for it automatically.

This route is a browser test; Expo and the public cloud map still use their
existing datasets. No experiment tiles have been uploaded to R2.

Outputs are ignored under `services/tiles/data/experiments/tahoe-z12-v1`.
`--clean-derived` deletes **only this experiment directory**, retaining original
source inputs. Without it, derived child tiles are reused.
Use `--regenerate-vectors` to ignore derived child files while retaining raw inputs
and served outputs, and `--legacy-recreation` to benchmark the original recreation
path. Direct recreation preparation always runs; it has no persistent derived cache. Reports distinguish
those hits from regeneration and retain per-source, packing, and DEM timings.
`results/` holds checked-in baseline measurements; raw output tiles stay local.

## Baseline format and limitations

Seven logical vector sources are combined with namespaced MVT layer names:
OSM, protected boundaries, land cover, trails, amenities, waterways, recreation.
The correctness baseline generates 16 z14 children per source per z12 tile and
merges them into an extent-16384 MVT. The current default directly encodes full-detail
recreation points into each parent, preparing its z10 source cell once per build;
the other six vector sources still use fine children. It clips child buffers, unions feature
fragments with matching IDs/properties, and joins lines where possible. This
retains the children's coordinate precision and source detail, but does **not**
yet eliminate internal z14 cutting for the remaining sources. Existing zoom-based style rules still apply.
Differing per-child properties can prevent a merge; visual seam and POI tests
remain essential before replacing the production format.

Each 1024-pixel DEM tile preserves the samples from four existing 512-pixel z13
DEM tiles. A one-parent-tile halo supports contour stitching. These are raw
Terrarium elevations, not baked contours. Do not replace them with ordinary
512-pixel z12 DEMs: that would reduce elevation resolution.

## Acceptance checks before scaling

- Compare source features, polygon/line seams, lake labels, trail badges and
  cluster breakup at zooms 12, 14, 16 and 18 against the existing fine tiles.
- Measure compressed bytes, request count, first useful render, full terrain
  readiness and peak memory on desktop **and the actual iPhone**.
- Confirm all fetched vector/DEM tile coordinates are z12, while local contour
  generation can use higher zooms.
- Keep raw-input acquisition, derived generation, packing, and cached reruns
  separate in timings. Record worker counts and competing compute load.
- Next compare direct full-detail parent generation with this fine-child
  correctness reference. Preserve low-ranking features for later display zooms;
  simply calling the existing generator at z12 would omit detail.
- Then test a larger Tahoe fixture and dense urban case before extrapolating
  throughput/storage or evaluating rented spot compute. No nationwide ETA from
  these four tiles.

## Tests

```sh
services/tiles/.venv/bin/python experiments/tahoe/test_build.py
# After a reference build has populated every source child:
services/tiles/.venv/bin/python experiments/tahoe/verify_reference.py
source scripts/env.sh
node --test apps/mobile/tests/terrain-worker.test.mjs
cd apps/web
pnpm exec tsc --noEmit
pnpm build
```

The Python tests cover merging adjacent polygon/line fragments, retaining source
namespaces and lossless DEM encoding. Worker tests cover feet, contour seams,
cached transfer safety, and z12-only DEM requests from higher display zooms.
These checks do not replace visual proofing or phone performance measurements.

## Measurements — 2026-09-08

Four-parent fixture, retained source inputs, existing AI training left running:

| Run | Derived child cache hits | Vector stages | DEM | Total |
| --- | ---: | ---: | ---: | ---: |
| First baseline, 2 threads | not instrumented; new output directory | 48.3 s | 32.7 s | 83.9 s |
| Repeat, 2 threads | 0 / 448 | 52.8 s | 15.6 s | 71.6 s |
| Repeat, 4 threads | 0 / 448 | 57.7 s | 16.0 s | 78.5 s |

Combining vectors cost approximately 3 seconds. Initial combined output was
649,434 compressed bytes across four tiles; 16 DEM tiles including the halo
were 24,131,754 bytes. These timings are observations, not isolated speedup
claims: source acquisition/cache effects and competing workloads can vary.
Four threads did not help, so two remain the default. Recreation and trail
processing dominate vectors; avoiding repeated child processing is the next
algorithmic target. DEM acquisition was more expensive on the first run.

Type checking, web build, four packing/DEM unit tests, and two actual contour
worker tests pass. The sample API served all four basemap files and 16 DEM files
successfully to the browser. Browser-control timeouts prevented screenshot/zoom
proofing in this session; visual readiness and iPhone speed remain unverified.


## Iteration 2 — prepare recreation once, encode direct parents

Profiling a recreation child spent 1.28 of 1.30 instrumented seconds in OSM
matching, including roughly 440,000 candidate comparisons. Repeating this for
64 children in the same source cell was wasted work. The experiment now prepares
that cell once at **detail zoom 14**, then emits four extent-16384 parent tiles at
z12. Feature display thresholds (including z15 amenities) remain unchanged.
Production calls keep their existing default zoom/detail behavior and do not gain
a stale global preparation cache.

Two clean vector-generation runs with retained inputs and two threads took
**40.52 s and 39.07 s** total. Recreation took **0.51 s and 0.49 s**, compared with
32.96 s in the earlier two-thread baseline. No derived vector cache hits were
used. The current vector output is 649,443 bytes compressed; DEM remains
24,131,754 bytes including the halo. This is about a 45% total-time reduction in
this fixture under the observed load, not a national throughput projection.

`verify_reference.py` compared all **5,022** output features in all four parents
with retained fine-child input tiles: layer set, extent, geometry, identity and
properties all match exactly. Encoded byte order can differ, explaining the
nine-byte compressed-size change. Five packing/direct-detail/DEM tests and the
16 recreation/matching tests pass; web type checking and production build pass.

Browser proofing now succeeded for the overview (z12.5) and Fallen Leaf detail
(z14): shape-following lake label at overview, horizontal label on the larger
lake, shoreline, detailed trails, contours and terrain relief are visible.
The browser reported 24.8 s to full initial vector/terrain readiness, not first
useful paint; no physical iPhone timing has been measured. Controls now provide
fixed z12/14/16/18 views, a campground shortcut, and received-file/payload counts.
Browser-control timeouts resumed during further checks, so z16/18 campground
breakup and phone performance still need proofing. No renderer errors were
reported in the inspected browser error log.

Next: measure trail work after one-time PCT initialization separately, reduce
repeated route matching with equivalence checks, and measure DEM overfetch/first
useful paint. Keep nationwide publication disabled and avoid widening coverage
until these local tests justify it.

## Iteration 3 — avoid intermediate PNGs and repeated trail corridors

The DEM builder now requests raw float32 samples, combines them, and encodes each
final parent only once. Previously it encoded and decoded 64 child PNGs before
encoding the 16 delivered PNGs. `--legacy-dem` retains that path for comparison.
All 16 delivered PNGs are **byte-for-byte identical** to the previous output,
including the halo. A synthetic test also compares the paths across positive and
negative elevations. Source selection, resampling, fallback behavior and
provenance are unchanged; normal tile-serving calls still return PNGs.

The first full build with this change took 34.62 s, with DEM at 9.44 s (previously
about 15 s). Another build took 32.00 s with DEM at 7.60 s. Cache/competing CPU
variation affects these full-build observations; all vector stages regenerated
from retained inputs rather than reusing derived vector files.

Trail matching now reuses each immutable reference geometry's 15-metre corridor
within a conflation call, instead of recomputing it for every candidate. All 64
sample trail tiles are byte-identical. A paired two-thread benchmark, alternating
old/new order over three rounds and excluding one-time PCT setup, measured:

| Version | Run 1 | Run 2 | Run 3 | Median |
| --- | ---: | ---: | ---: | ---: |
| Original | 7.86 s | 7.53 s | 7.82 s | 7.82 s |
| Reused corridors | 6.66 s | 7.22 s | 6.91 s | 6.91 s |

That is an approximately 12% improvement in this trail-only comparison. The
builder also initializes the PCT cache once before submitting uncached trail
work to parallel workers, preventing duplicate first-time construction; its
cost remains included in reported source time. Cached-only vector repacks skip
that preparation.

29 trail/DEM regression tests and six experiment tests pass. The full sample
continues to use the same four vector parents and 16 DEM parents; no coverage
expansion or paid compute. Hourly Tahoe follow-ups remain active. Next targets
are the remaining per-child vector work, raw DEM source reads/reprojection, and
end-to-end loading measurements; none of these local runs establishes a national
runtime estimate.

The combined final run took **31.79 s**: trails 10.52 s (including 3.04 s of
one-time PCT preparation), DEM 8.30 s. All 64 trail child hashes and all 16 DEM
PNG hashes still match the pre-optimization reference; the full parent feature
comparison also passes. This is about 19% faster than the preceding 39.07 s run,
and about 56% below the original 71.63 s two-worker baseline, for this fixture.

## Iteration 4 — reuse the normalized OSM input for trails

Trail generation formerly read and normalized the pinned OSM basemap a second
time. The experiment now supplies the already-built OSM child to the trail
stage. `--legacy-trail-basemap` retains the old path for comparisons. Ordinary
trail API calls still normalize their own input when no prepared tile is supplied.
No feature filtering, matching rules or output schema changed.

In a paired two-thread, 64-tile benchmark (PCT prepared before timing), old/new
trail times were 7.09/5.33 s and 7.38/5.50 s with reversed second-round order:
about **25% faster** for this stage. Every output tile was byte-identical to its
pre-optimization reference. Reused input file reads were outside that small
paired benchmark, but included in the full-build runs.

Full builds took **16.90 s and 29.09 s**, including input reads, PCT setup,
regeneration of all vector stages, packing and DEM. Other unchanged stages also
varied significantly with machine load, so the 16.90 s observation is not evidence
that this code change halved end-to-end time. Future reports include process CPU,
peak RSS and system load alongside wall time to help distinguish these effects.
They also identify the selected pipeline options explicitly.

25 trail regression tests pass, including prepared-input geometry/metadata
identity and ensuring it does not perform another archive read. All 64 trail tile
hashes match, and the full vector reference comparison passes. The output remains
approximately 649 KB combined vectors and 24 MB raw DEM including the halo. The
existing Wi-Fi sample remains accessible; nationwide warming is disabled.

The instrumented final run took **28.77 s**, used 34.13 process CPU-seconds and
peaked at about **419 MiB RSS**. A nearby full-build control with independent OSM
normalization took 29.46 s. The isolated paired-stage comparison is stronger
evidence for the 25% trail improvement than these noisy end-to-end differences.
The final run again matched all 64 reference trail hashes and all 16 DEM hashes.


## Iteration 5 — process workers and the first scale test

Two processes beat two threads in a bounded trail benchmark including startup,
PCT preparation and shutdown: 5.93/3.76 s for processes versus 7.17/7.37 s for
threads, with all 64 reference tile hashes matching. Spawn is used, avoiding
forking a GDAL runtime. A full four-parent build took 15.59 s with two processes
and 12.34 s with four. Worker memory is reported separately from parent RSS;
`maxChildPeakRssKiB` is the largest child's peak, **not aggregate worker memory**.

The builder now supports `--executor threads|processes` and defaults to four
processes based on the current machine's measured headroom. The source pipeline
still reserves normalized OSM completion before trail jobs consume those files.

The authorized 10× fixture is 40 z12 parents, x=680–684/y=1560–1567. It writes to
`tahoe-10x-z12-v1`, preserving the four-parent phone sample. Its first build took
91.44 s, including 31.87 s in land cover with retained inputs plus cache misses.
It includes 70 DEM parents with halo: 10× vector area does **not** mean 10× DEM
files, because neighboring parents share the halo. With parallel packing and retained inputs, its next full regeneration took
35.79 s, with all 40 parent hashes unchanged. Packing used 8.28 s and DEM 8.08 s.
The 91-to-36-second change also includes warmer input caches and must not be
attributed entirely to packing.

A further authorized `--region sierra-100x` fixture contains 400 z12 parents,
x=672–691/y=1552–1571, and also writes to a separate namespace. These fixtures
are explicit bounded regions; there is no arbitrary nationwide job option.
US mask enumeration alone found 144,027 detailed vector parents and 146,681 DEM
parents with its geographic halo. These are counts, not runtime estimates. The
broad z0–7 world overview is 21,845 tiles; CONUS intermediate z8–11 adds 48,750.
Intermediate-scale representation and cold-source acquisition still need to be
included in any three-day proposal.


## Iteration 6 — cold acquisition and geometry reuse at 100×

The 400-parent first build exposed a real cold-input failure: an NLCD TLS
handshake timeout. The job is resumable from completed child files; errors do
not become empty tiles. NLCD now retries transient failures (four bounded
attempts) and requests aligned 16×16 groups of fine rasters in one 1312-square
export. This reduces the high-detail request count by up to **256×**. It retains
2024 C1V1/raster ID 40, nearest interpolation, each child's original pixel grid,
and the same polygonization. Existing fine-raster caches remain reusable.

The acquisition change matched **17,583,260 pixels across 2,615 retained child
rasters, with zero differences**. Source cells outside the batch proof are still
covered by the same alignment arithmetic; no source edition was changed.
The resumed 400-parent land-cover stage completed 6,400 children in 41.88 s,
including 1,920 derived hits and fresh batched requests for remaining inputs.
This is a mixed resume measurement, not a clean cold benchmark.

Boundary preparation now retains its repaired polygon geometry alongside the
already-prepared outline. Previously each fine child parsed/repaired the same
polygon again. A full 6,400-child rerender took 6.20 s and matched every existing
boundary tile byte-for-byte. The first stage took 110.1 s, but that also included
cold acquisition, so those timings do not isolate the geometry speedup.

Agency trail cells similarly retain projected geometry and immutable source
properties, while tile-local clipping and OSM/agency conflation remain per tile.
All **6,400 trail children remained byte-identical** in a 28.22 s verification
run, versus 51.89 s for the prior full stage including cold source acquisition.
These results establish correctness; use warm paired runs for isolated speedups.

## Iteration 7 — lossless DEM compression tradeoff

On 16 existing Tahoe DEMs, PNG compression level 6 used 5.15–5.31 CPU-seconds
and 24,131,754 bytes. Level 3 used 1.16 CPU-seconds and 25,553,295 bytes:
about **4.5× faster encoding for 5.9% more bytes**. Level 1 used 0.72 CPU-seconds
and 25,837,111 bytes. All decoded elevations were exactly identical.
The experiment defaults to level 3; `--dem-compression` permits comparisons.
Ordinary production encoding keeps level 6 until the new format is adopted.
This affects storage/compression, not elevation precision or contour detail.

The completed 400-parent resume took **388.29 s**, including 217.83 s for 484
DEMs and 58.95 s for packing. It produced 30,276,120 compressed vector bytes and
791,206,387 DEM bytes. This run resumed the failed first attempt and reused its
OSM/boundary children; it is not the total first-acquisition time.

The next **full vector regeneration**, using all retained raw inputs and the
new geometry/compression paths, took **173.11 s** with four workers. Subsequent
controlled spatial-order and worker-count comparisons are recorded below. Separate
`sf-10x`, `smokies-10x`, `desert-10x` (40 parents each) and `western-1000x`
(4,000 parents) fixtures permit the authorized representative and next-scale
checks without exposing arbitrary nationwide execution. A 60 GiB free-disk
reserve prevents launching experiments when storage is already constrained.

Validation: 93 national tile tests pass with `OSM_ENRICHMENT_DB` pointed at a
nonexistent temporary path, isolating HTTP-fallback tests from the installed
local OSM database. Seven experiment tests pass, and the original four-parent
full feature reference still matches. No source index or raw input was deleted.


## Final staged result and execution strategy

The 4,000-parent western first build finished in **878.33 s**, producing
4,264 DEMs and 6.91 GB of final files. It required 2,926 native DEM chunks and
reused most existing native inputs. To avoid an optimistic cold estimate,
separate empty native caches were tested in Tahoe, Kansas and the Cascades.
Eight processes produced 144 DEM parents in 93–95 s in each region.

Sixteen threads improved cold runs to 66–67 s, but the large warm run exposed a
CPU bottleneck: its DEM phase took **560.99 s**. The selected pipeline therefore
uses **16 threads only to prefetch missing native chunks, followed by 8 processes
for reprojection and PNG encoding**. Cold Tahoe/Kansas probes now take **50–60 s**;
the warm 4,264-DEM phase takes **119.54 s**. Every output PNG is byte-identical.
Thirty-two threads had a slow tail and were not selected. Existing AI training
was left running throughout these comparisons.

`--dem-prefetch-workers` defaults to 16, `--dem-executor` to processes, and DEM
render workers default to the selected vector worker count (up to eight).
`--dem-prefetch-workers 0` preserves an unprefetched comparison. The planner uses
the same native-window calculation as rendering, verified by a regression test.

The complete western rerun retained all **4,000 vector hashes and 4,264 DEM hashes**,
covering 4,471,128,064 identical elevation samples. New York's dense four-parent
stress test peaked at 1.48 MB compressed / 2.55 MB raw per combined base tile.
Native overview samples were also composed without changing source geometry,
IDs, properties or buffers.

The [CONUS plan](../../docs/qa/zoom12-conus-plan.md) reserves **36–60 hours locally**
for the nationwide rollout, with continuous verified R2 upload and a bounded
scratch spool. The corpus is approximately 210–320 GB; keeping all of it on this
box is not the plan. No nationwide generation or experimental R2 publication
has started. Existing raw sources, phone samples and training jobs remain intact.

The local viewer now has links for the original fixture, the larger Tahoe region
and San Francisco. `add_sample_overviews.py` adds z10–11 base overviews to the two
larger samples; all detailed vectors and DEMs still stop at z12. These are browser
experiments, and Expo/public production retain their existing datasets.

The final four-parent Tahoe regeneration takes **10.52 s**, including 16 DEMs,
with the selected prefetch/process path and retained raw inputs. Its full feature
reference still matches. Final validation: 94 national tests, seven experiment
tests, native overview equivalence, web type checking and production build pass.
