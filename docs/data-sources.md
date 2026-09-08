# Data sources and map composition

This is the source guide for the current nationwide base map. It describes what
we ingest, what we actually draw, and how the web and mobile clients share it.
The running server's `GET /metadata` is authoritative for dataset versions,
tile URLs, geographic bounds, and download zoom ranges.

## Rendering policy: import existing sources, draw one merged network

OSM, NPS, USFS, MVUM, and PCTA are retained. Agency-only public terrestrial trails
are drawn, not discarded. Imports remain nationwide **on demand**, with persistent
raw caches; this does not mean every national source cell has been downloaded.
Non-public NPS and non-terrestrial USFS routes are excluded as before.

At z13+ the `trails.network` vector layer contains OSM roads/trails plus unmatched
agency segments. The web and mobile styles use this one network for road/trail
strokes, casings, names, and highway shields; the separate OSM road copy stops at
z13. Existing class styling is preserved. OSM geometry takes precedence, followed
by PCTA, NPS, USFS, and MVUM additions. Source records and conflicting attributes
are retained in `source_records`; tapped network features expose matched sources.

Conflation runs in local ground metres before final tile clipping/quantization:

- Compatible path/road classes and bridge/tunnel status are required. Motorized
  agency trails may match OSM tracks. Distinct overlapping route identities retain
  separate badges even when they use the same physical path.
- A shared normalized distinctive name or explicit long-route identity permits up to15m alignment difference;
  unnamed comparisons use5m, and differently named lines require near-coincidence
  within2.5m. These are matching tolerances, not source accuracy guarantees.
- Shared stretches need sustained directional agreement, at least8m and normally
 35m of overlap. Transverse crossings and switchback shortcuts do not match.
- Only matched stretches disappear from the secondary geometry. Unmatched
  branches/extensions remain; newly cut ends connect to the retained centerline.
- Nearby distinct paths and ambiguous alignments can remain separate. This is
  conservative geometric conflation, not a claim of perfect entity resolution.

At overview zooms, OSM remains the road source; nonduplicated MVUM road additions
and long-distance route lines supplement it. Route lines stop at z13, while route
badges remain from z6. The detailed network then includes both OSM and agency-only
portions of those routes. Duplicate agency route segments are merged per route
identity before placing badges. PCT has a bundled complete centerline; other
recognized long trails still depend on available named agency segments.

Regression coverage:
[`test_trail_matching.py`](../services/tiles/test_trail_matching.py),
[`test_national_trails.py`](../services/tiles/test_national_trails.py), and
[`trail-composition.test.mjs`](../apps/mobile/tests/trail-composition.test.mjs).
POIs use the separate entity-matching rules below.

## Source inventory

| Component | Upstream data | Processing and use |
| --- | --- | --- |
| Base map | [OpenStreetMap](https://www.openstreetmap.org/copyright) and Natural Earth through the [Protomaps basemap](https://docs.protomaps.com/basemaps/downloads), pinned to the 2026-08-11 PMTiles archive, schema4.15.1 | Range-read archive blocks, decode selected layers, normalize properties, and encode our MVT schema. Roads, detailed trails, buildings, water polygons, places, peaks, and fallback land cover. |
| Elevation samples | [USGS 3DEP](https://tnmaccess.nationalmap.gov/api/v1/products) and [Mapzen/AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) | Package elevation samples as lossless Terrarium PNG. USGS approximately 10 m for detailed US views; global DEM for overviews and coverage gaps. Contours and shading are generated on the device. See [device terrain](device-terrain.md). |
| Land cover | [USGS Annual NLCD2024, Collection1.1](https://www.usgs.gov/centers/eros/science/annual-nlcd-data-access), through the [USFS/GeoPlatform categorical ImageServer](https://imagery.geoplatform.gov/iipp/rest/services/Vegetation/USFS_EDW_NLCD_Landcover_CONUS/ImageServer) | Lock raster40, sample categorical values with nearest-neighbor resampling, sieve small speckles, polygonize and simplify. Eight styled classes. CONUS coverage; OSM cover remains the fallback elsewhere. |
| Waterway behavior | Pinned Protomaps OSM waterway geometry plus current OSM way tags from Overpass | Join by OSM way ID, retain intermittent/seasonal flags, and clip stream geometry outside lake/water polygons. Missing flow tags remain unknown. |
| Protected areas | [NPS administrative boundaries](https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2), [USFS forest boundaries](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0), and [Wilderness Connect boundaries](https://services1.arcgis.com/ERdCHt0sNM6dENSD/arcgis/rest/services/Wilderness_Areas_in_the_United_States/FeatureServer/0) | Cache complete agency objects, dissolve/repair geometry, extract real boundaries before tile clipping, and simplify for display. Detailed boundaries replace generalized overview outlines. |
| OSM amenities and clusters | [Overpass](https://overpass-api.de/api/interpreter), with [private.coffee fallback](https://overpass.private.coffee/api/interpreter) | Query supported facility categories in z10 cells with a halo; fetch complete site extents when needed. Polygon containment or conservative proximity to point sites assigns members to named sites. |
| Agency recreation and campground details | [NPS public POIs](https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/MapServer/0), [USFS recreation sites](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0), [Recreation.gov RIDB bulk download](https://ridb.recreation.gov/download) | Normalize public point features and facility details. A local SQLite import contains5,523 enabled geolocated RIDB campgrounds/visitor centers from the imported snapshot. Duplicate records merge conservatively. |
| Natural landmark names | [USGS GNIS](https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data) and [GeoNames US](https://download.geonames.org/export/dump/) | Nationwide local SQLite import, conservative matching with agencies/OSM, source-specific records preserved. Included in the recreation tileset. |
| Long-distance trails | [PCTA January2026 centerline](https://www.pcta.org/discover-the-trail/maps/pct-data/), [USFS trails](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0), [NPS trails](https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_Trails_Geographic/FeatureServer/0) | PCT has a bundled complete centerline. Other recognized routes come from named agency segments and are not guaranteed complete. Used for overview route lines and badges. |
| Motor Vehicle Use Map | [USFS MVUM roads, layer1](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_MVUM_02/MapServer/1), [trails, layer2](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_MVUM_02/MapServer/2) | Preserve route refs, vehicle designations, and published dates-open strings. Roads and motorized trails participate in the merged network; matched permissions are retained without drawing a second line. |
| State/area overview | [Natural Earth50m](https://www.naturalearthdata.com/) and bundled generalized agency protected-area features | Small GeoJSON data for overview state lines and named park/forest/wilderness context. The removed Explore areas UI is not required to render these. |
| Symbols | Vendored [Maki](https://github.com/mapbox/maki) SVG paths plus our generated road shields and trail badges | Local canvas images work offline. Facilities generally have square frames; recreation/natural features use circles according to the style. Trail badges are original identifiers, not official trail logos. |

The basemap geometry snapshot, newer OSM enrichment tags, and agency snapshots
have different dates. They are not a synchronized or live national survey.
Facility seasons and MVUM designations are published attributes, not a live
closure feed.

## From source to screen

1. **Request:** MapLibre requests a source-specific vector tile for the viewport,
   or the phone queues tiles for a selected download-grid cell.
2. **Cache lookup:** The Python service checks
   `services/tiles/data/cache/<datasetId>/<z>/<x>/<y>.pbf`.
3. **Build a missing tile:** The source module uses persisted raw responses,
   PMTiles byte ranges, a DEM window, or the local RIDB import. Successful output
   is written atomically. Upstream failures do not become successful empty tiles.
4. **Compose:** The same MapLibre style rules combine independent sources in the
   web map and the Expo app's MapLibre WebView.
5. **Retain offline:** The phone stores vector and raw elevation bytes by source, dataset version,
   and tile coordinate. Rendering, local icons, clustering, and duplicate
   matching use those bytes without requiring a fresh upstream query.

The current source contracts are:

| Style source | Dataset ID | Generated zooms | MVT source layers used |
| --- | --- | --- | --- |
| `osm` | `osm-us-pm20260811-b2aa7f4b1858-v6` | 0–14 | `land`, `forest`, `grass`, `residential`, `rock`, `water`, `building`, `road`, `rail`, `poi`, `label`, `water_label` |
| `dem` | `dem-terrarium-usgs10m-v2-20260907` | 3–13 | Raster elevation samples; client derives `contours.contour` at z11–15 |
| `landcover` | `usgs-annual-nlcd-2024-c1v1-v1` | 6–14 | `landcover` |
| `waterways` | `osm-waterways-pm20260811-v2` | 6–14 | `waterline` |
| `boundaries` | `us-agency-boundaries-v2` | 8–14 | `areas` |
| `amenities` | `osm-us-amenities-v2` | 10–14 | `amenities` |
| `recreation` | `us-agency-recreation-v8` | 6–14 | `recreation` |
| `trails` | `us-official-trails-v3` | 5–14 | `network` at13–14; `roads` additions below13; `routes` for overview strokes and badges; unused legacy `trails` is empty |

The clients overzoom z14 vector data up to display zoom18. Style-layer zoom
ranges control detail visibility; member filtering must not rely on a feature
zoom expression above the source's maximum zoom.

### Drawing order and cartographic derivations

- Background and terrestrial cover go underneath navigation features. NLCD
  excludes open water so OSM lake/river polygons remain the water geometry.
- Protected-area designation is a separate fill/boundary treatment; a national
  park does not imply a particular land-cover class.
- Intermittent/seasonal stream styling uses retained tags. Streams are clipped
  outside lakes and painted beneath the water fill.
- The bundled device worker generates contours in feet: 200/1,000 at tile z11,
  100/500 at z12, 40/200 at z13, and 20/100 at z14+. The pair is minor/index
  interval. GPU relief uses the same offline DEM. No national contour downloads.
- Roads and OSM trails use class-specific strokes/casings above cover and
  contours. Apply the trail-source policy at the top of this document.
- Lake-name orientation is derived from lake polygon shape. Elongated lakes can
  use an angled, single-line name, then switch to horizontal when the words fit
  at the current zoom. This is local geometry-derived labeling, not another
  gazetteer source.
- Labels, highway shields, route badges, and POIs use zoom thresholds and
  collision placement. The legend is built from currently rendered features.

### Facility grouping and duplicate matching

Cluster icons summarize the site's facilities below z15. At z15 the group layer
ends and individual members appear at their mapped coordinates. Site-level tags
such as “drinking water=yes” do not invent a water-point coordinate; those
services remain in the site's tap details. Display offsets separate nearby
member symbols without moving the underlying feature coordinates.

Agency/RIDB records match only with compatible feature kinds and supporting
identity/name/distance evidence. Name normalization handles punctuation, accents,
Mount/Mt, and selected facility suffixes. Generic names, different campground
loops, and ambiguous nearby candidates remain separate. Shared external IDs have
a distance guard. Source-specific values and conflicts are retained in the
`source_records` attributes and the “Matched sources” detail view.

The client also matches currently loaded OSM/agency data, including offline
tiles. An agency marker is hidden only when its OSM representation is eligible
at the current zoom. Matching updates when either source arrives. Redundant OSM
node/way/relation representations within the same site are suppressed only for
compatible names, the same icon, and a separation of at most3m.

See [recreation-sources.md](recreation-sources.md) for the facility schema.
**GNIS and GeoNames are imported:** 127,970 selected nationwide landmarks remain
after 102,951 duplicate records were merged. OSM basemap peaks/saddles participate
in matching as well as facility groups/members. The local indexed data contributes
summits, passes, springs, waterfalls, natural arches, rocks and caves at z13/14.
See [gazetteer-sources.md](gazetteer-sources.md) for exact snapshots, selected
classes, source attribution, ambiguity safeguards and import instructions.
No fire or weather overlay is part of this base map.

## Caching, downloads, and refreshes

- Sources have independent dataset versions and caches. A style-only change,
  such as removing duplicate trail strokes, does not require new tile bytes.
- PMTiles reads use256KiB aligned disk-cache blocks. DEM catalog choices,
  raster blocks, agency responses, and Overpass extracts have separate raw
  caches. `TILE_DATA_DIR` relocates server data; contour storage can also use
  `NATIONAL_CONTOURS_DATA`.
- A successful foreground tile request can warm a one-tile neighbor ring and
  four children at detail zooms10–13. At z14 it warms neighbors only. Below z10
  it warms only the basemap. Warming is bounded and never recursively expands.
  Inspect `GET /jobs/viewport`; `VIEWPORT_WARMING=0` disables it.
- Downloads use batches of up to8 tiles with bounded concurrency, partial
  retries, cancellation, and persisted queue state. Each selected region
  includes the supported sources and required ancestor/descendant tiles.
- Added sources upgrade saved selections while retaining existing binary data.
  Trail/recreation processing revisions with equal or expanded zoom ranges and coverage
  also retain selections and refresh only the changed source files. Other incompatible
  composition changes currently reset saved selections; unaffected binary cache
  files remain reusable.
- Trails v3 reuses the v1 raw agency-response directory. Its generated MVTs use
  v3; matching OSM road geometry comes from the same pinned archive as the base map.
- Recreation v8 reuses v1's pinned raw agency-response and RIDB-import directory.
  Generated recreation MVTs use the v8 namespace. Refreshing raw data requires a
  deliberate generated-dataset version change as well.
- Contour catalog refreshes use `NATIONAL_CONTOURS_EPOCH`. Do not silently replace
  pinned sources underneath an existing dataset ID.
- Existing California warming covered its original basemap/contour job. It does
  not establish that later-added datasets are fully warm across California.

## Implementation and provenance references

- [Tile API and integration](../services/tiles/tile_service.py)
- [Basemap normalization and lake labels](../services/tiles/national_basemap.py)
- [Raw elevation packaging](../services/tiles/national_dem.py) · [device contour worker](../apps/mobile/src/terrain.worker.ts)
- [NLCD processing/source notes](../services/tiles/LANDCOVER_SOURCES.md)
- [Detailed protected-area processing](../services/tiles/national_boundaries.py)
- [Overview boundary provenance](../services/tiles/regions/protected-areas-sources.json)
- [Stream enrichment](../services/tiles/national_waterways.py)
- [OSM facility extraction](../services/tiles/national_amenities.py) and [group builder](../services/tiles/regions/build_amenities.py)
- [GNIS/GeoNames importer](../services/tiles/national_gazetteers.py) and [snapshot manifest](../services/tiles/regions/gazetteer-sources.json)
- [Agency facilities](../services/tiles/national_recreation.py), [server entity matching](../services/tiles/feature_matching.py), and [client matching](../apps/web/app/poiMatching.ts)
- [Trail line conflation](../services/tiles/trail_matching.py)
- [Agency/MVUM/long-route data](../services/tiles/national_trails.py) and [PCTA/badge provenance](../assets/trail-badges/SOURCES.md)
- [Maki assets, license, and pinned originals](../assets/maki/)
- [Web style](../apps/web/app/vectorStyle.ts), [mobile style](../apps/mobile/src/style.mjs), and [mobile TypeScript style copy](../apps/mobile/src/vectorStyle.ts)
- [Mobile offline storage](../apps/mobile/src/storage.ts) and [viewport warmer](../services/tiles/viewport_warmer.py)

Source attributions are attached to MapLibre sources and shown in the information
drawer. The repository records OSM/ODbL attribution, PCTA's CC BY4.0 data credit,
Maki's CC0 license, and the original badge designs. Official trail emblems are
not bundled as freely reusable logos; see the linked badge provenance.

When changing a source or how it is composed, update this guide, the source
metadata/provenance, the relevant dataset version if tile bytes change, and all
three style copies. Regenerate shared mobile browser-code literals with
`node scripts/build-base-features.mjs` (and the relevant icon/legend generator).
Keep regressions for source precedence, cluster handoff, offline upgrades, and
duplicate matching alongside the change.

## Nationwide label hierarchy

See [label-ranking.md](label-ranking.md) for peak elevation/isolation scoring,
destination spacing, stable cross-tile selection, zoom thresholds, snapshot
coverage, and the derived index build/refresh procedure.

## Natural-feature symbols

Original local SVG symbols in [assets/topo-icons](../assets/topo-icons/README.md)
supplement Maki: waterfall, cascade, natural arch, cave, spring, rock landmark,
pass/saddle and shelter. The same mappings drive the map and viewport legend.
Classification happens in the clients from existing kind/class attributes, so
cached/downloaded tiles with the old generic marker gain the new symbols without
reimporting data. Falls named Cascade/Cascades receive the stepped-water symbol;
other falls use falling-water columns. This name-based distinction is cartographic,
not a new surveyed waterfall classification. Springs remain distinct from potable
water. The generated glyphs are local/offline, with blue ink for water features,
circular natural-feature frames and square shelter frames.


### Site service badges and Boundary Waters audit

Amenity processing v2 retains services such as `toilets=yes` and `drinking_water=yes` through the zoom-15 cluster split. If OSM provides a separate mapped facility, that facility uses its own position. If it only reports a service for a site, a small combined badge stays on the site's campsite/picnic/visitor symbol. `facility_location=site_only` and `site_facilities` record that distinction, and the popup explains it. This does not invent precise restroom or water coordinates. Detail-symbol separation accounts for the wider badge, and the viewport legend includes each of its icons.

The v2 vector namespace reuses existing raw OSM cell extracts and rebuilds old processed cells on access. Saved mobile selections refresh only the amenities source while retaining other cached layers. The raw extract directory remains `osm-us-amenities-v1` intentionally.

The Boundary Waters audit in `docs/qa/boundary-waters-clusters.json` covers all 109 currently cached clusters inside the overview wilderness boundary plus a small fringe: 76 site-service badges needed retention, including 75 bathroom badges. No group icon is lost from the data at the split after the fix. A fresh region-wide OSM inventory could not be completed: broad and narrower queries timed out, followed by HTTP 429. The audit is explicitly a cached-data audit, not a claim of complete current OSM coverage.

Lake styling adds a pale, zoom-scaled blurred shoreline stroke between the water fill and the crisp shore outline. It uses existing water geometry and requires no extra tile layer or downloads.

The reusable `scripts/audit-cluster-data.py` now checks **every icon**, including site-service badges, against the detail representation (previously it only checked that some member existed). It rebuilds stale processed data from cached raw extracts without network requests. Set `CLUSTER_AUDIT_AREA="Boundary Waters Canoe Area Wilderness"` to restrict it to this area; run `scripts/test-all-clusters.mjs` against the generated vector fixtures for renderer checks.

Renderer validation: all 109 cached Boundary Waters clusters passed the encoded-vector check at zoom 15 with no missing in-viewport members. Live Saganaga Lake #63 screenshots at zooms 13, 15, and 17 verify the shoreline glow and persistent bathroom service badge.


### Centered protected-area labels

Label anchors are separate from navigation centers. `services/tiles/area_labels.py` chooses the centroid of the largest connected polygon in Web Mercator, matching its displayed shape. If that centroid falls outside a concave area or inside a hole, it uses an interior pole of inaccessibility. Detached islands and antimeridian components cannot drag a label into the sea. The area builder precomputes `label_center` and `label_method`; `/areas.geojson` uses these for label points. Existing navigation bounds and centers remain intact.

The renderer anchors area text at its center with zero radial offset, removing the previous collision-driven shift to top/bottom/left/right. Centered area names take placement priority over nearby ranked peaks. Labels still obey collision avoidance and may be omitted when crowded. All 1,347 supplied areas have validated interior anchors; the audit is in `docs/qa/area-label-centers.json`. Yosemite National Park and Yosemite Wilderness now use their main polygons' visual centroids. This changes overview label data and style, not downloadable terrain tiles.

## September 7 terrain/cartography revision

See [device terrain](device-terrain.md) for DEM acquisition, offline migration,
licenses and contour generation; [cartographic proofing](cartography-proofing.md)
records the visual acceptance matrix and coverage of the cartographic techniques.


### Shared protected-area outlines

Boundary v2 draws NPS park edges first, wilderness second, and forest edges last.
Nearly coincident strokes within 5 metres are suppressed. Forest administrative
outlines are sometimes much coarser than NPS geometry: continuous forest runs of
at least 1 km inside a 250 m park-edge corridor are also suppressed. Short
crossings and branches outside that corridor remain. This is a display rule,
not a modification of legal boundaries; all designation polygons and their
attributes remain in the tiles. Processing precedes tile clipping. The v1 raw
agency cache is reused, while v2 rendered tiles and phone downloads are refreshed.
The reported Yosemite east-edge view (-119.260788, 37.743606, z12.229378)
contains Yosemite NP, Yosemite and Ansel Adams wildernesses, and Inyo/Sierra
national forests; the wilderness edges differ from the park by about 0–3 m,
while portions of the forest outlines differ by tens to hundreds of metres.


## Production US bulk enrichment and warming

`prepare_us.py` freezes the official [Geofabrik US PBF](https://download.geofabrik.de/north-america/us.html), verifies its publisher MD5, and retains it under `data/osm-source`. `osm_bulk.py` creates a SQLite/R-tree index of amenity geometries and waterway tags. Its manifest records SHA-256 and replication timestamp. Multipolygon amenity areas retain full geometry; OSM IDs remain the deduplication identity. This replaces public Overpass queries in production, while development still supports its existing fallback. Public deployments set `OSM_REQUIRE_BULK=1`. This source enriches the pinned Protomaps basemap; it does not change its geometry vintage.

`regions/us-warming.geojson` is the USA feature from Natural Earth's public-domain 1:10m country dataset, used only to enumerate warming coverage. Its source URL is recorded in its properties. `warm_us.py` intersects this mask with each tile source's published extent, resumes checkpoints, and retains failed keys. See [deployment](cloud-deployment.md) for operation and limitations.
