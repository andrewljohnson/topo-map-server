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
This route is a browser test; Expo and the public cloud map still use their
existing datasets. No experiment tiles have been uploaded to R2.

Outputs are ignored under `services/tiles/data/experiments/tahoe-z12-v1`.
`--clean-derived` deletes **only this experiment directory**, retaining original
source inputs. Without it, derived child tiles are reused. Reports distinguish
those hits from regeneration and retain per-source, packing, and DEM timings.
`results/` holds checked-in baseline measurements; raw output tiles stay local.

## Baseline format and limitations

Seven logical vector sources are combined with namespaced MVT layer names:
OSM, protected boundaries, land cover, trails, amenities, waterways, recreation.
The first implementation generates 16 z14 children per source per z12 tile and
merges them into an extent-16384 MVT. It clips child buffers, unions feature
fragments with matching IDs/properties, and joins lines where possible. This
retains the children's coordinate precision and source detail, but does **not**
yet eliminate internal z14 cutting. Existing zoom-based style rules still apply.
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
