# Cartographic treatment and visual proofing

The September 7 pass combines device terrain with the existing nationwide base
map. It applies the following cartographic practices as a coherent style; it does
not replace already-working label ranking, lake geometry or trail conflation.

## Technique coverage

| Practice | Applied treatment and proof target |
| --- | --- |
| Visual hierarchy | Warm quiet cover beneath water, paths, roads and labels. Overview parks yield to destinations and local facilities. |
| Gentle relief | New local GPU hillshade with northwest light, Igor shading and reduced strength at close zooms. |
| Terrain generalization | Native low-resolution overview DEMs; detail DEMs and progressively finer contour intervals. No enlargement of overview downloads. |
| Restrained contours | Thin, translucent minors; darker index lines; spaced labels in feet. Lakes cover contour lines. |
| Elevation tints | New subtle elevation-dependent warm-to-neutral ramp beneath water and navigation features. |
| Harmonious palette | Cream land, muted greens, blue water, warm contour browns; protected designations remain distinct from physical cover. |
| Cover textures | New faint wetland reed marks, sand stipple and scrub dots. Coarse NLCD fills fade at close zooms to reduce the prominence of raster blocks. |
| Water structure | River/stream width hierarchy, retained seasonal/intermittent tags, shoreline glow and lake masking. Smaller streams now compete less with trails. |
| Road casings and bridges | Existing class-specific paired strokes and merged network; new bridge deck pass above intersecting surface roads. |
| Trail vocabulary | Retained hiking, footpath, cycle, bridle, steps, track, surface/SAC distinctions, long-route lines and badges. |
| Typography | Retained distinct water lettering, area capitals, place/POI type and compact route shields. |
| Shape-aware labels | Retained elongated lake-axis labels and horizontal fit transitions; park anchors derived from polygon geometry. |
| Label halos | New consistent, restrained halos capped at 1.3 px with slight blur. |
| Selective labels | Retained importance/isolation-ranked peaks, destinations and landmarks, with collision placement. |
| Contextual density | Existing spatial ranking surfaces isolated destinations while keeping campground facilities for closer zooms. |
| Shape preservation | Detailed agency boundaries and source-aware geometry remain intact; coarse land-cover pixels lose weight when zoomed in. |
| Symbol displacement | Existing deterministic offsets separate coincident facilities. Unknown exact facility positions stay attached to their site. |
| Stable zoom transitions | Reverse-zoom checks of label sets and cluster handoffs; contour cache transfer and DEM cancellation tests. |
| Quiet spaces | Open water and undeveloped terrain retain breathing room; no forced POI overlap outside deliberate cluster-member separation. |
| Systematic proofing | Repeatable mobile-renderer matrix, actual localhost web checks, offline reloads, rotated/tilted landscape views and persisted evidence. |

## Repeating the visual checks

From the repository root, after starting the local tile/web services:

```bash
source scripts/env.sh
node scripts/build-terrain.mjs
node scripts/build-base-features.mjs
node scripts/build-map-info.mjs
node scripts/proof-cartography.mjs
node scripts/proof-offline-terrain.mjs
node scripts/proof-web-terrain.mjs
```

Set `PLAYWRIGHT_MODULE` and `CHROMIUM` for another machine's installed browser
runtime. `PROOF_OUTPUT` changes the artifact directory (default
`docs/qa/cartography`). `PROOF_SCENES` optionally supplies a JSON array of
`[name, [longitude, latitude], [zooms...]]`; `DENSITY_PASS` names a run.

The default matrix contains 23 views:

- Yosemite: 7 → 10 → 13 → 15 → 13 → 10.
- Fallen Leaf Lake/campground: 12 → 14 → 15 → 17 → 14.
- Desolation Wilderness: 11 → 14 → 11.
- Boundary Waters: 9 → 12 → 15.
- Zion: 8 → 11 → 14.
- Bar Harbor/Acadia: 10 → 13 → 16.

Each frame records source settlement, errors, time to the snapshot, label/POI
counts, local contour counts, DEM bytes and worker request statistics. A source
being settled **does not** establish that its tiles succeeded; inspect the error
list as well. Worker times include DEM acquisition and decoding, not just CPU
contouring. The headless renderer uses software graphics, so these are not
physical-phone frame-rate measurements.

## Acceptance checks and observations

- In Yosemite, trails and destinations remain legible over steep shaded terrain.
  Minor contours are subordinate to index contours and trail strokes.
- Fallen Leaf uses an elongated one-line lake label at z12. Facility groups at
  z14 break into members at z15; closer z17 views retain facilities in bounds.
- Desolation retains 17 ranked peaks in both z11 visits, plus its wilderness label.
- Overview state/park boundaries, coastal water, dense lakes, desert relief,
  campground roads and town buildings are covered by the matrix.
- Review of the first screenshots led to narrower small streams, quieter close-up
  land-cover fills and lighter label halos. The final pass repeats those views.
- The first cold pass recorded timeouts in upstream-dependent stream/amenity
  enrichment. Raw DEM/contour generation had no worker errors. Cached stream tag
  reads now bypass an unrelated writer lock; first-time Overpass enrichment can
  still take time. This pass does not certify that the entire country is cached.
- A fresh renderer with networking blocked rebuilds 362 visible contour features
  in portrait and 509 in rotated/tilted landscape from four saved DEM tiles
  (1,811,538 bytes). Online and offline counts match. The test recreates workers,
  so previously generated contour tiles cannot satisfy the check.
- The browser legend is checked for casing/fill/dash samples, grouped columns,
  drawer layout, attribution sanitation and cleanup. Terrain relief and cover
  textures are represented, and contour labels report the current foot interval.

Physical iPhone testing of frame rate, battery use and long background sessions
remains separate from this desktop proof. Both platform exports and the Expo Go
bundle are checked, but a successful export is not a physical-device test.

See [device terrain](device-terrain.md) for the download architecture and source
accuracy, and `qa/cartography/` for saved reports and representative screenshots.

## Recorded results

- 147 Python tests and 71 JavaScript tests passed; both type checks passed.
- Final web build, iOS export and Android export passed. The exact Expo Go iOS
  launch bundle returned HTTP 200. The actual web app and terrain legend passed
  their browser check with no page errors.
- All 23 final views generated terrain without worker errors. Eighteen views
  fully settled without tile errors. Five views recorded upstream/transport
  failures; the report does not label those fully successful.
- Boundary Waters z12 was rechecked with bounded source lanes matching the phone:
  basemap, DEM, contours, amenities, boundaries, trails, land cover and recreation
  loaded; the stream source remained pending. The proof runner now uses those
  bounded lanes instead of forwarding an unbounded burst of requests.
- Zion and Bar Harbor cold stream enrichment remained blocked by refused upstream
  connections, including a direct read-only GET probe and a timed-out tile retry.
  One Bar Harbor overview amenity request also timed out. These are recorded
  availability limits, not missing DEM coverage or silently successful tiles.
- For the identical 118 requested DEM keys, preserving native overview samples
  reduced elevation transfer from 43,846,024 to 24,737,511 bytes: **43.6% less**.
  This is the sampled view sequence, not a universal download-size estimate.

[Contact sheet](qa/cartography/contact-sheet.jpg) ·
[Machine-readable results](qa/cartography/summary.json) ·
[Full frame records](qa/cartography/density-verified.json) ·
[Offline proof](qa/cartography/terrain-offline-proof.json) ·
[Web legend](qa/cartography/web-legend.png)
