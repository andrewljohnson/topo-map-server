# topo-map-server

Outdoor maps with a Python tile pipeline, a MapLibre web viewer, and an Expo app
with offline downloads, GPS recording, and device-generated contours and shading.

**Code: [MIT](LICENSE).** Map data, icons, and other bundled material retain their
[own licenses and attribution](THIRD_PARTY_NOTICES.md).

[Live map](https://topo-map.andrewljohnson.workers.dev/) ·
[Mobile setup](apps/mobile/README.md) · [Data sources](docs/data-sources.md)

## Current map coverage

The published pilot has detailed tiles around **Lake Tahoe and San Francisco**.
It contains 80 detailed base tiles, 140 DEM tiles including neighboring samples,
and 132 overview tiles. The worldwide background is zooms 0–3; regional ancestors
continue through zoom 11. Outside the published detail regions, only the broad
background is available. California and CONUS publication remain paused.

Each detailed zoom-12 tile contains the combined vector layers at extent 16384.
A separate 1024×1024 Terrarium DEM supplies elevation. The client overzooms through
zoom 18, drawing contours in feet and relief locally. No precomputed contour tiles
are downloaded by the current combined client. See the
[combined release contract](docs/combined-publication.md) and
[device terrain pipeline](docs/device-terrain.md).

## Run locally

Requirements: Python 3.11+, Node 22.13+, and pnpm. The helper scripts also recognize
this machine's bundled runtime.

```sh
./scripts/setup.sh   # dependencies and overview cache; no full-US import
./scripts/dev.sh     # local tile API :3001 and web viewer :3000
./scripts/mobile.sh  # Expo development server :8081
```

Open http://localhost:3000. The local API can generate uncached tiles from source
data on demand; the cloud serves already published objects. These are different
coverage modes.

Expo defaults to the live cloud API so testing does not accidentally use a warmer
LAN cache. To test the local tile service explicitly:

```sh
EXPO_PUBLIC_TILE_SERVER=http://YOUR_LAN_IP:3001 ./scripts/mobile.sh
```

Use the Expo Go version matching `apps/mobile/package.json` and the same Expo
account as the CLI. A physical phone uses the computer's LAN address, not
`localhost`. The development server must be reachable from the phone.

Full Expo development reloads clear map tiles and saved download selections, as
requested for clean cloud testing. Fast Refresh does not repeatedly clear an
active session. Notes and GPS recordings remain; installed release builds retain
offline maps. See [mobile setup and distribution](apps/mobile/README.md).

## Using the map

- The map button opens the download grid. Entering this mode moves to a useful
  grid zoom once; tapping cells does not zoom. Tap a cell to select or remove it,
  and tap the map to hide the panel. Active downloads animate the
  map icon and show progress and byte counts in the panel.
- Locate centers on the current position; the compass resets rotation and tilt.
- The circular information button opens attribution and a grouped, two-column
  legend for the visible map.
- Map notes save a comment with camera and bounds. Saved notes can restore the
  view or be copied for a reproducible report.
- The mobile recording panel shows distance, moving time, and elevation gain,
  with reset/recalculation and optional background recording.

[Map notes](docs/map-notes.md) · [GPS recording](docs/gps-recording.md) ·
[Background downloads](docs/background-downloads.md)

## Sources and composition

The base map combines a pinned Protomaps/OpenStreetMap snapshot, official
protected areas, agency trails and MVUM roads, long trails, recreation facilities,
GNIS/GeoNames landmarks, OSM amenities and stream tags, and USGS NLCD land cover.
USGS 3DEP supplies elevation. Small archive ranges and source windows are cached
locally; this pipeline does not download rendered tiles from tile.openstreetmap.org.

OSM geometry remains the reference where an agency road or trail matches it.
Source-backed branches and source-scoped details are retained; proximity alone
does not authorize joining disconnected paths. Protected-area strokes are
compared separately from their original designation polygons. Lake labels use
polygon-aware axes and font-fit thresholds. POI grids give way to detailed
locations, with conservative duplicate matching and ranked labels.

See [source URLs, processing, licenses, and refresh rules](docs/data-sources.md),
[label ranking](docs/label-ranking.md), and
[systematic conflation checks](docs/qa/systematic-conflation/README.md).

## Generate and publish

Data is generated locally, then uploaded to Cloudflare R2. A Worker serves the
website and published tiles. There is no cloud tile-cutting job. Credentials stay
outside Git; setup is documented in [Cloudflare setup](services/cloud/README.md)
and the [local-generation plan](docs/local-generation-cloudflare.md).

Tile publications use a new immutable release ID, verified uploads, and a separate
promotion step. Website releases use committed **remote main**:

```sh
./scripts/deploy.sh
```

Uncommitted or unpushed changes are not included by that deployment script. Follow
[combined publication and rollback](docs/combined-publication.md) for data releases.
Historical California/CONUS warmers are not the current pilot workflow; do not
resume them as part of a routine client release.

## Repository and validation

| Location | Purpose |
|---|---|
| `services/tiles` | Source import, conflation, DEMs, local API, publication |
| `services/cloud` | Cloudflare Worker and R2 delivery |
| `apps/web` | Web viewer and shared cartographic helpers |
| `apps/mobile` | Expo app, native storage/downloads, GPS, embedded map |
| `experiments/tahoe` | Bounded generation benchmarks and geometry audits |
| `docs/qa` | Reproducible camera views, map renders, and data checks |

```sh
source scripts/env.sh
(cd apps/mobile && pnpm bundle:map && pnpm test && pnpm typecheck)
(cd apps/web && pnpm exec tsc --noEmit)
services/tiles/.venv/bin/python -m unittest discover -s experiments/tahoe -p test_build.py
```

Map styles and browser helpers are shared with mobile through generated source
modules. Regenerate them before committing. MapLibre and its workers/icons are
bundled, so offline maps need no external renderer CDN or glyph server.

[Cartography proofing](docs/cartography-proofing.md) ·
[Latest overnight evidence](docs/qa/overnight-2026-09-09/README.md) ·
[Scaling plan and its measurement limits](docs/qa/zoom12-conus-plan.md) ·
[Product roadmap](docs/product-roadmap.md)
