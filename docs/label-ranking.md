# Nationwide label density and ranking

The web map and Expo renderer use the same multi-scale hierarchy in recreation
processing revision `us-agency-recreation-v8` (vector zooms 6–14, display through
zoom18). The hierarchy is built once across the available nationwide catalog,
not separately for each requested tile or viewport. It works in downloaded maps.

## What determines importance

**Peaks:** reported elevation plus distance to the nearest strictly higher known
catalog peak. This promotes a region's high point, even when smaller summits are
clustered nearby. It is not DEM-derived topographic prominence or a guarantee that
every intervening summit is cataloged. Heights come from the imported reported
GeoNames field; GNIS's current export has no heights, and coarse DEM estimates are
not substituted. Peaks without a reported height enter conservatively at z11 or
later. Highest known/tied highest peaks have `highest_known_peak=true`, rather
than a fictitious distance to a higher mountain.

**Destinations:** kind (visitor center, ranger station, trailhead, shelter,
campground, viewpoint, lodging, picnic site, information) plus distance to the
nearest other known destination. This gives isolated named facilities more room
than another point in a dense group. Nearby facilities at the same compound
still count as neighbors. Isolation is relative to available records: nationwide
RIDB plus cached NPS/USFS cells, not a nationwide census of buildings. We do not
invent POIs or public access for unnamed/isolated building footprints. Newly
fetched agency sites outside the snapshot retain their original conservative zoom
until the hierarchy is rebuilt.

**Other landmarks:** passes enter from z11, waterfalls z12, arches/rocks z13,
caves/springs z14, with spacing within the landmark family. Small facilities such
as toilets and water points remain close-zoom details. No spring is inferred to
be drinking water.

## Stable spatial hierarchy

The builder uses a spherical nearest-neighbor tree for distance queries. At each
zoom6–13 it admits candidates in descending importance, using approximately120
world-screen pixels between summit anchors at z6–9,72 pixels from z10, and104 between destination/landmark
anchors. Neighboring spatial buckets participate in every decision, including
across the date line. Buckets accelerate proximity tests; they are not arbitrary
one-winner-per-tile cells. Stable source IDs break equal-score ties.

Once admitted, a point remains eligible at subsequent zooms. Remaining points
enter at z14, with detail classes retained for z15. MapLibre then resolves actual
text/icon collisions using `symbol-sort-key`, padding, and alternative label
anchors. An eligible label can still be obscured by a higher-priority label;
monotonic eligibility does not promise every label is rendered at every frame.
Regional peaks and park names receive priority over routine facilities and
repeated route badges. Park names can shift around their anchor to make room
for a nearby summit label.

| Display zoom | Intended density |
| --- | --- |
| 6–8 | Widely separated regional high points; park/forest names and route context |
| 9–10 | Additional mountain groups and remote destinations; smaller campground grids |
| 11–13 | Local peaks, named trailheads/camps/shelters, passes and waterfalls |
| 14 | Full detailed peak catalog/OSM handoff and ungrouped facilities |
| 15+ | Campground grids break into their real member coordinates; minor amenities appear |

Matched OSM peak labels inherit rank at close zoom. Matched campground groups
inherit their site's minimum zoom and priority; a matched toilet never gates the
whole site's group. Detail members keep their original coordinates and close-zoom
visibility. Canonical source IDs deduplicate repeated raw/ranked records even
when their names are generic.

## Build, storage and refresh

```sh
services/tiles/.venv/bin/python services/tiles/poi_ranking.py
```

Run after importing GNIS/GeoNames and RIDB, with whatever NPS/USFS cells are
available. The builder needs SciPy/NumPy from `services/tiles/requirements.txt`.
Serving only needs the completed SQLite/R-tree index. The builder checks and
atomically replaces `data/label-ranking/hierarchy-v1.sqlite`, under `TILE_DATA_DIR`
when configured. A missing index returns an error rather than caching an empty
successful tile. Copy the index to the cloud data volume with the other indexes.

Current snapshot:135,518 canonical points, including77,493 summits (68,942 with
reported elevations),7,007 destinations,50,493 other landmarks and525 details.
See [build manifest](../services/tiles/regions/label-ranking.json) for the index
checksum, build time and first-eligible-zoom counts.

Rebuild and bump `national_recreation.DATASET_ID` together when accepting new
ranking inputs or algorithm parameters. Existing MVT caches must not silently
mix ranking generations. Overview z6–9 queries use only the local index; z10–14
also merge live/cached agency cell data and RIDB details. Phone selections survive
this expanded zoom range and refresh only recreation files; terrain and other
compatible downloads are retained.

## Validation

Behavioral tests cover higher-versus-lower neighbors, missing/equal elevations,
spatial bucket edges/date-line wrapping, deterministic nested selection, remote
facilities, z15 detail survival inside z14 source tiles, overview requests without
agency calls, OSM handoff, campground breakup, and compatible offline upgrades.
Screenshot review covers repeated zooms7–16 around Yosemite/Sierra, Fallen Leaf
Lake/Tahoe and Acadia. Tile-load completeness is recorded separately from symbol
counts, so missing cold overlays are not mistaken for a labeling choice.

Final review confirmed Mount Whitney at z7, Cadillac Mountain alongside the
Acadia park label at z9, local peaks and destinations appearing progressively,
and Fallen Leaf campground grids at z14 splitting into true member points at
z16. Repeated zoom-in/zoom-out checks covered four regions; complete label-source
frames were distinguished from initial cold-cache frames. Some Acadia stream
overlay requests still encountered upstream timeouts during review; those are
separate from this ranking change. The actual web page was also checked at a
430×860 viewport, and its container now resizes correctly despite stylesheet
load order. Web tile URLs preserve MapLibre coordinate placeholders instead of
percent-encoding the braces. Python (136 tests), mobile/shared-client (59 tests), client typechecks and the web
production build passed.

## Nearby named facility labels

NPS publishes two “Sentinel Vault Toilet” records about85m apart, with different
feature/geometry IDs, both tagged as arbitrary points with unknown positional
accuracy. These are not automatically declared to be the same physical facility.
The shared client groups same-name restroom/drinking-water records within120m
when they share an agency and park/unit and have a distinctive location name.
At z15–16 one representative symbol/label is eligible (normal collision
placement still applies); at z17+ individual source
locations return, with the name printed once. The popup identifies nearby records
and retains their IDs and coordinates. This is presentation grouping, not a
change to source identity or the conservative server entity matcher.

Generic labels such as “Vault Toilet,” different names, different units, and
points outside the radius stay separate. Every pair must fit within120m, so a
chain of points cannot grow into an arbitrarily large group. The behavior works
with existing offline tiles; reload the client without redownloading maps.

## Desolation Wilderness medium-zoom regression

Center: `[-120.16, 38.935]`, portrait viewport430×860; check z9,10,11,12
and the reverse sequence. The overview retains Dicks Peak from z9. The smaller
summit spacing from z10 admits Mount Tallac, Phipps Peak, Red Peak and Pyramid
Peak at z10 instead of their previous z11–12 thresholds. This is a nationwide
spacing adjustment, not manually inserted POIs or a Desolation-only override.
The renderer still resolves text collisions, and labels outside the viewport do
not count toward evaluating density within the wilderness. Source revision v8
refreshes the recreation tiles while retaining other downloaded map sources.
