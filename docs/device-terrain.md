# Device-generated terrain

National metadata now has a `dem` tileset instead of a downloadable `contours`
tileset. Both web and Expo compose its elevation samples with the existing vector
basemap. No contour MVT or hillshade image is requested from the national server.

## Samples and rendering

- The server fetches and caches native USGS 3DEP raster windows for z12–13,
  preferentially approximately 10 m. Its existing acquisition code can record
  30 m fallback, or 60 m in Alaska. Network failures remain retryable errors.
- For z3–11 and confirmed high-resolution coverage gaps, use the global
  [Mapzen/AWS Terrarium dataset](https://registry.opendata.aws/terrain-tiles/).
- `national_dem.py` reprojects measured elevations, then losslessly packages them
  into RGB PNG (native 256 × 256 overviews; 512 × 512 detail): `meters = R*256 + G + B/256 - 32768`.
  This is elevation encoding, not a rendered map image. Quantization is 1/256 m;
  that number does **not** describe source resolution or vertical accuracy.
- Each output has provenance recording USGS chunks, native/fallback pixel counts,
  source URLs, units and reprojection. Z13's output sample spacing varies with
  latitude; zooming further does not create more accurate terrain measurements.
- MapLibre's `raster-dem` source computes hillshading on the GPU, using northwest
  illumination fixed to map orientation and the Igor method. A subdued elevation
  tint uses the same source; lakes paint above relief and contours.
- A bundled `maplibre-contour` 0.1.0 worker stitches neighboring DEMs, applies
  marching squares, and encodes transient vector contours in feet. Contour
  generation stays off the UI thread. PNG decoding happens on the renderer thread;
  both consumers share an abortable raw-byte cache (24 tiles).

| Contour tile zoom | Minor interval | Index interval |
| --- | --- | --- |
| 11 | 200 ft | 1,000 ft |
| 12 | 100 ft | 500 ft |
| 13 | 40 ft | 200 ft |
| 14–15 (overzoomed through 18) | 20 ft | 100 ft |

Contour tiles use one level of DEM overzoom, capped at DEM z13. MapLibre's tile
selection is discrete; the legend reports the interval at the current zoom.
Contour cache buffers are copied before transfer so revisiting a tile does not
receive a detached buffer. Navigation cancellation propagates to shared DEM
requests only when no other consumer still needs them.

## Downloads and migration

`/dem/{z}/{x}/{y}.png` supports direct viewing; `/dem-batch` returns up to eight
base64 PNGs using the existing dataset-versioned batch contract. The server's
persistent cache and bounded viewport warmer now include DEM samples. Background
warming never recursively expands. DEM work has its own render gate.

The phone stores `.png` DEM files by dataset and coordinate. Every selected cell
includes a one-tile DEM halo at **each** saved zoom, wrapping the dateline and
clamping the poles. This supplies neighboring samples for offline shading and
contour seams. Adjacent cells share cached files and in-flight requests. Existing
native background download sessions also carry DEM batches.

Replacing the old contour source retains selected cells and existing basemap /
amenity / trail files. Those cells are queued for the new DEM samples; completion
and byte counts are recomputed. Old contour files are no longer requested by new
national metadata and are not counted as current saved-map content. They are not
destructively removed during migration. An entirely offline installation keeps
its saved metadata until it next connects and can discover the new DEM source.

## Building and validation

Install both applications' dependencies before regenerating shared assets.
`node scripts/build-terrain.mjs` bundles the worker into both applications;
`node scripts/build-base-features.mjs` shares renderer logic with Hermes without
serializing function source. The mobile `bundle:map`, `start` and `export` scripts
regenerate these automatically. Worker code and icons require no CDN.

- `test_national_dem.py`: negative/high elevation round trips, RGB-boundary
  interpolation, retryable upstream errors, cache reuse and contour API removal.
- `terrain-worker.test.mjs`: actual worker, foot intervals, neighboring edge
  agreement and repeat transfers from its cache.
- `batch.test.mjs`: old saved-cell migration, eight-tile batching, seam halo,
  retained basemap files, PNG paths, and fully offline reads.
- `scripts/proof-offline-terrain.mjs`: fresh browser worker with network access
  blocked after saving bytes; portrait plus tilted/rotated landscape. This tests
  the Expo renderer/bridge contract, not physical iPhone performance.

## Attribution

[USGS 3DEP](https://www.usgs.gov/3d-elevation-program) and USGS SRTM/GMTED2010;
NOAA ETOPO1; Mapzen/AWS Terrain Tiles and its
[full provider attribution](https://github.com/tilezen/joerd/blob/master/docs/attribution.md).
The linked provider credits are also reachable in the map attribution drawer.
The global composite includes additional regional providers; see the full list.

The contour worker is BSD-3-Clause, with ISC-licensed isoline code. Notices are
bundled in the worker and copied into `assets/licenses/maplibre-contour.txt`.
