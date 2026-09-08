# topo-map-server

Open-source outdoor maps: a Python vector-tile pipeline, MapLibre web viewer, and
cross-platform Expo app with offline downloads and on-device DEM contours and shading.

**Code: [MIT](LICENSE).** Map data and bundled third-party material retain their
[own licenses and attribution](THIRD_PARTY_NOTICES.md).

[Live map](https://topo-map.andrewljohnson.workers.dev/) ·
[Mobile setup](apps/mobile/README.md) · [Data sources](docs/data-sources.md)

The cloud publication is still warming: a worldwide overview is available, while
detailed CONUS coverage is incomplete. Run the local tile service for on-demand
generation. Cloud deployment uses local generation plus Cloudflare Workers/R2; see
[the current cloud setup](services/cloud/README.md).

Cloud v1: [deployment and hosting](docs/cloud-deployment.md), [product roadmap](docs/product-roadmap.md). Release committed main with `./scripts/deploy.sh` after configuring a server.

## Current terrain pipeline

The national app now downloads **raw elevation rasters**, with contours in feet
and hillshading generated locally. Saved cells upgrade by downloading DEM plus
neighbor samples while retaining other map tiles. The national service no longer
advertises or generates contour tiles for app requests. Historical regional
contour commands below describe the earlier pipeline.

See [device terrain](docs/device-terrain.md) and
[cartography proofing](docs/cartography-proofing.md). Local web: http://localhost:3000;
Expo remains on port 8081.


A local vector map server, full-screen web map, and Expo Go app with offline grid downloads.

See [Data sources and map composition](docs/data-sources.md) for source URLs, processing, rendering precedence, duplicate handling, caching, and refresh rules. The map opens on the United States and supports browsing nationwide, including Alaska and Hawaii. Basemap and contours are separate vector tile sources composed by MapLibre.

## Run locally

Requirements: Python 3.11+, Node 22.13+ and pnpm. Scripts recognize this machine's bundled runtime.

```sh
./scripts/setup.sh  # dependencies and overview cache, no full-US import
./scripts/dev.sh    # API :3001 and webpage :3000
./scripts/mobile.sh # Expo LAN server :8081
```

Open http://localhost:3000. Open the Expo QR code in Expo Go SDK 57 on the same Wi-Fi. Expo CLI and Expo Go must use the same signed-in account. The app defaults to the live cloud API. Use `EXPO_PUBLIC_TILE_SERVER=http://YOUR_LAN_IP:3001 ./scripts/mobile.sh` to test your local service. Full Expo reloads clear development map downloads; installed builds preserve offline maps. The top title/text panel has been removed from both maps.

The bottom-right Download button opens the selection grid. Tap a square to download both vector sources, and tap again to remove it from the queue. Saved tiles and locally generated labels work offline. Downloads use native background transfers; see [background behavior and platform limits](docs/background-downloads.md).

## On-demand maps and caching

The server reads small portions of a pinned, downloadable [Protomaps OSM archive](https://docs.protomaps.com/basemaps/downloads), normalizes the features into our vector schema, and atomically caches each generated PBF. It does not download rendered tiles from tile.openstreetmap.org. Downloaded archive blocks are also cached, so nearby requests reuse source bytes. The reviewed snapshot is August 11, 2026, Protomaps 4.15.1, a retained patch build. A local mirror can be selected with `NATIONAL_PMTILES_URL`; it must contain the same pinned snapshot. Source size, ETag and BLAKE3 identity are recorded in `national_basemap.py`.

Contours are generated separately from USGS 3DEP COG elevation windows on a consistent grid. Contours use feet: 20-foot intervals from zoom 13, 100-foot index lines from zoom 11. The pipeline prefers approximately 10 m DEMs, fills missing samples with 30 m data, and can use 60 m data in Alaska. Actual source resolutions and vertical datums are retained in per-window provenance. Death Valley's negative elevations are included. Confirmed open-water tiles may have empty contour overlays; unavailable elevation over land returns an error and is not silently cached as empty terrain.

Generated tiles live under `services/tiles/data/cache/<source-dataset-id>/z/x/y.pbf`. Basemap archive blocks live in `data/national-basemap`; elevation windows, pinned catalogs and provenance live in `data/national_dem`. Source versions are independent. `NATIONAL_CONTOURS_EPOCH` changes the elevation catalog/cache namespace for an intentional source refresh. `TILE_DATA_DIR` relocates all server data; `NATIONAL_CONTOURS_DATA` optionally relocates DEM storage alone.

Basemap source zooms are 0–14, with display overzoom to 18. Contours use 11–14. Maps outside the US can display the global basemap, but USGS elevation coverage is not global. The first request for a new area needs network access and generation time; subsequent requests use disk cache.

## California background cache job

```sh
services/tiles/.venv/bin/python services/tiles/precache.py
# Resume after a stop, including retrying exhausted failures:
services/tiles/.venv/bin/python services/tiles/precache.py --retry-errors
```

The job covers the checked-in Geofabrik California boundary through zoom 14: **278,075 basemap tiles and 276,863 contour tiles**. It uses two batch requests at most, through the API's lower-priority rendering lane. A SQLite queue records successful work and resumes on rerun. A lock prevents duplicate jobs. Network failures retry with backoff; exhausted errors remain visible. The job pauses if free disk space falls below 10 GiB. It needs the local tile server running and does not depend on the webpage or Expo being open.

Progress: http://localhost:3001/jobs/california. Persistent state is `data/jobs/california.sqlite`, with a readable `california-status.json`. The interactive session running the job prints progress; stopping it preserves its queue. This is a large background job, not an instant full-state download.

## Download performance

Both sources use gzip-compressed batches of up to eight tiles. Mobile allows two offline batches and two independent interactive requests, with per-tile deduplication, partial retries and persistent resume. A full grid cell has 33 basemap and 22 contour tiles with the national zoom range. Completed sources remain reusable when only the other source changes. Offline selections reset on a composition update so a saved region never falsely claims to contain outdated terrain.

## Repository and checks

- `services/tiles`: on-demand source readers, MVT generation, HTTP cache, DEM pipeline and California job.
- `apps/web`: React/Vinext and MapLibre GL JS.
- `apps/mobile`: Expo/React Native, bundled MapLibre WebView and filesystem storage.
- `scripts`: setup and launch commands.

```sh
source scripts/env.sh
(cd services/tiles && .venv/bin/python -m unittest -v)
(cd apps/web && pnpm build && pnpm exec tsc --noEmit)
(cd apps/mobile && pnpm test && pnpm typecheck && pnpm export)
```

The original raw Maryland OSM importer and precomputed contour database remain available in regional mode: `tile_service.py prepare --mode regional`, then `tile_service.py serve --mode regional`. National mode is the CLI default. Importing the module in tests defaults to regional unless `TILE_MODE` is set.

## Deployment and attribution

Nothing is deployed. The same Docker service supports persistent `/data`; run precaching as a separate job against its API. Use HTTPS and a production HTTP serving layer/CDN before public deployment. Mirror the pinned source archive for control over its long-term availability. Cached areas remain available if an upstream source is unavailable; new areas still require those sources.

[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL; [Protomaps](https://protomaps.com), Natural Earth; [USGS 3DEP](https://www.usgs.gov/3d-elevation-program). Attribution is visible online and offline. Generated data and caches are excluded from Git.

### Lake labels

National basemap revision v2 preserves Protomaps water-label points in a `water_label` layer. Upstream derives these from full polygons with point-on-surface placement and area-based `min_zoom`; preserving them avoids independently labeling each clipped polygon fragment. Web and mobile use centered blue serif labels, wrapping and collision detection, and prioritize labels by minimum zoom. Labels are included in basemap tiles and offline downloads. Existing v1 offline areas need to be downloaded again for this revision. California precaching resets only the changed basemap source, retaining completed contour tasks and the source archive range cache.

Basemap revision v3 adds cached lake-axis angles from reference-zoom water polygons, merging neighboring tile fragments when needed. Elongated lakes receive single-line, map-aligned labels; round lakes remain horizontal. Existing v2 server tiles are reused during the upgrade.

### Road styling and shields

Revision v5 preserves route network/number pairs and available road surface, bridge, tunnel and ramp attributes. The style distinguishes muted red highways, warm gold main roads, ivory local streets, brown dashed tracks, and fine dashed trails. Locally generated shield images support Interstate, US, generic state and county routes, with collision-aware route numbers; they need no network connection. Unknown route networks use a neutral badge. Surface markings depend on upstream availability. Download older offline areas again to receive the new route attributes.

### Offline POI icons

Twenty Maki icons (CC0-1.0) are vendored in `assets/maki` with the original license, pinned commit, source URLs and SHA-256 hashes. `python3 assets/maki/build-icons.py` regenerates the web and mobile helpers from the original SVG paths. Icons draw locally in square frames for facilities/amenities and circular frames for recreation, lodging, landmarks and natural features. The v6 basemap contains the `poi` layer, icon/frame classification, names and source zoom priorities, so downloaded maps retain POIs offline. Unnamed facilities still receive icons; administrative/land-use centroids are excluded. Availability follows the pinned upstream map data. Re-download older offline areas for the new POI layer.

### Explore public areas

The standalone overview overlay includes 1,347 dissolved named areas: 429 NPS units, 112 Forest Service administrative areas (including combined forest/grassland units), and 806 wilderness areas. Agency source URLs, date and checksum are in `services/tiles/regions/protected-areas-sources.json`. Outlines are simplified for overview navigation. Green solid boundaries mark parks, olive dashed boundaries mark forests, and purple dotted boundaries mark wilderness. Prominent park labels appear nationally; forest and wilderness labels become visible as you zoom.

The Explore areas interface has been removed. The overview geometry still supports protected-area labels and boundaries and is retained offline. Detailed agency boundaries replace overview outlines at closer zooms.

To refresh the source data, run `python3 services/tiles/regions/fetch_areas.py`, then `services/tiles/.venv/bin/python services/tiles/regions/build_areas.py`, review the generated boundaries and manifest, and restart the tile service.

Shield styling uses compact text-fit padding and higher sprite pixel ratio to keep symbols subordinate to roads. California uses a green state shield; county pentagons point upward. Other states currently use a neutral generic marker rather than individual state silhouettes.

### Trail cartography

Trail classes follow the OSM highway classes retained by the pinned Protomaps archive: general paths use rust-red short dashes, footways use fine charcoal dots, cycleways use teal long dashes, bridleways use purple dash-dot lines, steps use ladder treads, and vehicle tracks use wider pale twin-edge lines with a dashed center. Pedestrian areas and sidewalks remain visually quieter. A narrow paper-colored halo separates these lines from contour and woodland detail. Trail names and route refs have their own line-following label layer, and road names exclude trail classes to prevent duplicate labeling. These visual classes do not assert hiking difficulty, trail visibility, or access permissions: those attributes are not provided by the current tile source.

### Zoom-level density

The style prioritizes major protected-area names at overview scales, forests/wilderness at regional scales, and summits/trail labels once the source includes them (often z13). Everyday POIs wait until z14 or their later source minimum; outdoor destinations have their own earlier layer. Small boundary outlines are hidden at overview scales. Contours step from 500-foot lines at z11 to 200-foot lines at z12, 100-foot lines at z13, and 20-foot detail at z14; elevation labels use wider intervals to leave room for trails and summits. This is styling of the existing downloaded vector data and does not invalidate cached tiles.

### Land cover

The pinned Protomaps vector basemap already carries OSM/Natural Earth land-cover polygons. Web and mobile distinguish forest, meadow/grass, scrub, agriculture, orchards, wetlands, developed land, bare rock, sand/beach, and glaciers. Protected-area designation alone does not imply grass cover; its separate transparent overlay and boundary remain visible. Cover fills sit below contours and navigation features. These classes are included in existing basemap downloads and server caches, so no re-download or California cache reset is needed. OSM cover remains a fallback. The additional Annual NLCD2024 source now provides satellite-derived categorical cover across CONUS; see [the source guide](docs/data-sources.md) for its processing and precedence.

### Yosemite amenity grids (offline pilot)

Yosemite Valley has a separate bundled GeoJSON amenity source: 12 named destination groups and 384 individual icon features from OSM. At zooms 10–14, groups display a compact grid with one icon per facility category. At zoom 15 the groups give way to individual facilities; ungrouped facilities enter at zoom 14. Each grid is a single collision-placed symbol, preserving square amenity and circular recreation frames. Original matching POI categories are suppressed within the pilot bounds to avoid duplicates. Outside this coverage, ordinary basemap POIs remain.

Membership uses site polygons, with an unambiguous 70 m fallback only for point sites. Anchors are inside representative points for polygons. Facilities mapped as points retain their coordinates; area facilities use inside points. Site-level water/toilet tags contribute to summaries without inventing an exact location. Beaches do not automatically imply swimming. This pilot does not yet add fishing/boat-ramp pictograms or nationwide grouping.

The approximately 109 KB source data ships with web and mobile, so it works offline immediately with downloaded maps and does not change California's warm tile datasets. To refresh, run `services/tiles/.venv/bin/python services/tiles/regions/build_amenities.py --fetch`, then `python3 scripts/embed-amenities.py`. Source query, timestamp, license and hash live in `services/tiles/regions/yosemite-amenities-sources.json`.

### Nationwide amenity tiles

The Yosemite prototype is now superseded by a nationwide, on-demand `amenities` vector tileset (`osm-us-amenities-v1`), composed independently from basemap and contours. Metadata advertises `/amenities/{z}/{x}/{y}.pbf` and `/amenity-batch` (up to eight tiles), zooms 10–14 with display overzoom. Web and Expo use this source; the bundled Yosemite sample remains only as fallback for older servers.

OSM Overpass extracts are fetched for zoom-10 regions with a padded boundary, then cached as raw data plus grouped features under `data/national-amenities/`. Full site geometries and bounded extent followups support group membership near edges. Generated MVT tiles have independent disk caches. Overview multi-amenity grids start at zoom 10, single-icon destinations at 13, ungrouped facilities at 14, and grouped individual facilities at 15. Real point coordinates are retained. Data quality and facility coverage depend on OSM.

Cold regions require upstream work (the initial Zion and Acadia extracts took about 4 and 7 seconds respectively; busy regions, queued fetches, or upstream failures can take longer). Overpass requests are serialized and rate limited across processes. Incomplete/error responses are retried and never cached as empty successful data. Amenities have a dedicated execution lane so terrain continues rendering. Configure `AMENITY_OVERPASS_URL` for a dedicated upstream when scaling beyond local use.

Offline grid downloads include amenity tiles and byte counts. Adding this source upgrades saved selections automatically by downloading missing tiles, while retaining existing basemap/contour files; failed additions remain retryable. California's previously completed basemap and contour cache is unchanged. The new amenity layer is generated on demand, not already prewarmed statewide or nationwide.

### Detailed protected areas and lake labels

Protected-area fills and outlines now switch from the compact nationwide overview to a separate `boundaries` vector source at zoom 8. It fetches official NPS, Forest Service, and wilderness geometry with upstream simplification tolerance 0.000025 degrees rather than the overview's 0.003-degree fetch plus 0.005-degree simplification. This preserves much more source detail; it does not imply survey-level positional accuracy or reshape administrative borders to follow terrain. Geometry is cached per agency object, dissolved by unit, and simplified for the requested zoom. True boundaries are extracted before clipping to prevent false tile-edge borders; polygon fills use the same geometry. The source has its own server execution lane and participates in offline downloads and additive saved-region upgrades. Existing basemap, contour, and amenity caches remain usable.

Lake labels now enter one zoom before the upstream label priority when the point is available. This fixes Fallen Leaf Lake's previously empty angled-label interval (priority 13 and horizontal threshold 13): zoom 12 shows its single-line name along the lake, and 13 switches to horizontal. Lake names have higher collision placement priority and reduced padding; names are still not forced to overlap. Large lakes retain horizontal labels where the name fits.

### Viewport download responsiveness

Mobile viewport traffic reserves two request slots each for basemap and raw DEM. Visible terrain precedes overlays, which share two additional slots; phone download batches yield while the viewport loads. Slow cold overlays cannot occupy the terrain queue. Direct requests now use an abortable transport; timeout and panning cancellation propagate from MapLibre through the native bridge. Shared offline-download owners keep still-needed requests alive, and viewport requests promote queued offline tiles. Retry refreshes tile sources after reconnecting. A live local queue test with intentionally stalled overlays returned zoom-14 map/contour pairs for Tahoe, Yosemite, and Shasta in 12–16 ms; phone/network latency will vary.

State boundaries appear at overview zooms 2–8, fading out by zoom9. Natural Earth 1:50m internal US boundary lines are bundled into both clients (about76KB), so they work offline without another tile download or cache reset. Source provenance is in `regions/us-state-boundaries-sources.json`.

### Stream flow and map legend

Waterways now have their own cached vector tileset and offline download source. The pinned Protomaps stream lines omit flow tags, so the service joins retained OSM way IDs to batched, cached OSM tag lookups. Tagged intermittent and seasonal streams use blue dash-dot strokes; ordinary/unknown-flow streams stay solid blue. Missing tags do not establish perennial flow. Stream geometry is clipped outside water polygons, and streams are painted below water fills. Initial tag lookups can be slow; their client/server lanes are isolated from basemap and contour requests. Existing terrain caches are unchanged.

The circular information button opens a bottom drawer containing a legend of visible feature types and map attribution. It includes individual POIs and campground-grid amenities, road/trail/stream samples, route shields, boundaries, land cover, and contours. The legend refreshes on map movement/loading while open. Credits retain safe external links. The drawer respects safe areas, scrolls, closes by its close button/backdrop/Escape, and returns keyboard focus to the information button. `scripts/build-map-info.mjs` refreshes the mobile browser-code literal from the shared web implementation; `scripts/test-map-info.mjs` checks drawer behavior and rendered color samples.

### Warming around map views

National mode now expands the server cache around foreground tile requests. A successful map request queues a one-tile ring at the same zoom and the four child tiles at the next zoom (detail zooms 10–13), composing basemap, raw DEM, amenities, protected boundaries, waterways, land cover, official trails/MVUM, and recreation facilities within their supported zoom ranges. Requests at zoom 14 warm neighbors only; overview requests below zoom 10 warm only the basemap. Background work never recursively schedules more work.

The queue holds at most 1,024 tiles, expires untouched requests after ten minutes, deduplicates queued/running tiles, skips existing files, and backs off failed tiles for two minutes. Generated files use the normal persistent dataset caches. Pending work is in memory and is rediscovered from browsing after a restart. One background worker serves terrain and one each serves amenities, boundaries, waterways, land cover, trails, and recreation. Background rendering leaves foreground capacity available with the default two-slot configuration; a one-slot deployment cannot reserve a second slot. Interactive requests take priority over queued background work. Set `VIEWPORT_WARMING=0` to disable this behavior. `GET /jobs/viewport` reports queue counts, active tiles, and recent failures.

Mobile cold requests now allow 150 seconds for generation (the WebView deadline is 180 seconds); panning cancellation still releases the phone request immediately. Cold generation continues to populate the server cache if the phone leaves the area. These changes do not create elevation coverage where the upstream DEM is unavailable: missing land elevation remains an explicit error rather than a permanently cached blank tile.

OSM facility and stream-tag queries retry through `https://overpass.private.coffee/api/interpreter` if the primary Overpass endpoint fails. `AMENITY_OVERPASS_URL` and `AMENITY_OVERPASS_FALLBACK_URL` configure the two endpoints. Both share the same serialized request budget; cached records retain the endpoint that actually supplied their data.


## Nationwide base-map enrichment

Three independent vector datasets now compose with OSM and contours and participate in
batched offline downloads and viewport warming. Adding these sources upgrades existing
saved regions with the missing tiles, retaining existing OSM/elevation files.

- **Land cover:** USGS Annual NLCD 2024, 30 m categorical data vectorized at zooms6–14.
  Forest, scrub, grass, wetland, farmland, developed land, rock and ice sit beneath
  water and labels. This source covers CONUS; OSM remains the fallback elsewhere.
  Source and processing notes: [LANDCOVER_SOURCES.md](services/tiles/LANDCOVER_SOURCES.md).
- **Official trails and MVUM:** USFS/NPS trails and Forest Service motor-vehicle
  roads/trails, plus published vehicle designations and seasonal date strings.
  Tap a feature for its details; these attributes are not a live closure feed.
  OSM and agency trails/roads are conflated into one detail network from zoom13.
  Matched stretches draw once; agency-only branches and source attributes remain.
  Long-route overview strokes stop at zoom13 while badges remain.
  See the source guide for matching tolerances and retained source details.
- **Long trails:** complete January2026 PCTA PCT centerline and named agency route
  segments for AT/CDT/JMT/TRT and other recognized long trails. Other route
  alignments are not guaranteed complete. Compact badges are original route
  identifiers, not official logos; official insignia need reuse permission.
  See [badge/source notes](assets/trail-badges/SOURCES.md).
- **Campgrounds and hiking facilities:** NPS/USFS public points and5,523 enabled
  geolocated campground/visitor-center records from RIDB bulk data. Tap campground
  symbols for available water, restrooms, descriptions, fees, phone, accessibility
  and stay limits. Matched OSM sites retain their symbols and open the merged
  agency details; new agency points fill gaps. Minor facilities appear at zoom15
  even though vector sources overzoom from14. Data and GeoNames/GNIS assessment:
  [recreation-sources.md](docs/recreation-sources.md).

Endpoints: `/landcover/{z}/{x}/{y}.pbf`, `/trails/{z}/{x}/{y}.pbf`,
`/recreation/{z}/{x}/{y}.pbf`, each with a corresponding `/{name}-batch`
endpoint and independent dataset version in `/metadata`. RIDB bulk imports are
local and require a deliberate refresh; source notes describe the import command.
No fire/weather overlay is included.


### Cluster regression audit

Cluster grids stop at zoom15, and separate member symbols begin at the same zoom.
Member filters do not depend on the vector source zoom, which stops at14.
Nearby or coincident member icons receive the smallest free display offset;
their source coordinates are unchanged. Site-level services without individually
mapped locations remain in the site's tap details.

To test every currently cached cluster without querying upstream services:

```sh
services/tiles/.venv/bin/python scripts/audit-cluster-data.py
node scripts/test-all-clusters.mjs
```

The audit snapshots cached group membership, generates local vector fixtures,
checks every group at zoom15 against original member coordinates, and checks
difficult groups around15 and at16/18 (including rotated/tilted views).
Results and screenshots default to `/tmp/topo-cluster-audit`.
This covers cached data and shared rendering rules, not every possible future
OSM edit or a nationwide visual inspection of uncached locations.


### Duplicate matching

OSM, NPS, USFS and RIDB recreation points now use conservative duplicate
matching. Compatible feature kinds, normalized distinctive names, nearby
coordinates, and explicit shared source IDs provide matching evidence.
Different campground loops, ambiguous sites, and generic nearby facilities
remain separate. Merged source details remain available from the single
symbol, including conflicting source-specific values.

The renderer matches loaded offline data too and handles either source arriving
first. Agency symbols are hidden only when their matching OSM representation is
eligible at the current zoom. Duplicate node/way/relation representations inside
a cluster are suppressed without deleting their data or moving coordinates.
Recreation processing v2 refreshes only recreation files in saved regions;
basemap, contours and other datasets are retained. This revision does not import
new GNIS/GeoNames records.

### GNIS and GeoNames landmarks

Nationwide named summits, passes, springs, waterfalls, arches, rock landmarks and
caves are imported and matched against existing agency/OSM POIs. The 127,970-point
local index avoids upstream requests while panning and feeds the same offline
recreation tiles. See [gazetteer sources and import instructions](docs/gazetteer-sources.md).

### Ranked labels at each zoom

Regional peaks now appear before local detail, using a nationwide elevation and
known-peak-isolation hierarchy. Named camps, trailheads and shelters use a separate
type/spacing hierarchy. Campground groups remain compact and split into their real
member coordinates at zoom15. See [label ranking](docs/label-ranking.md) for the
build command, source-coverage limits and offline behavior.
