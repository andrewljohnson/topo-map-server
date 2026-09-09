# Tahoe zoom-12 experiment

Nationwide publication is paused. Do not restart the publisher, expand the sample,
or provision paid compute until this experiment has been reviewed.

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
