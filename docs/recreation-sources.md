# Federal recreation points and campground details

Implemented in `services/tiles/national_recreation.py` as vector source-layer `recreation`, dataset `us-agency-recreation-v8`, tile zooms 6–14 (overzoom beyond14), bounds `[-180,18,180,72]`. A persistent [label hierarchy](label-ranking.md) supplies `label_minzoom`6–15; unranked newly fetched facilities retain their original `min_zoom`12–15, so restroom/drinking-water points remain in z14 tiles and appear at15. All agency geometries are retained. No facility service is turned into a fictitious point inside a campground.

## Operational sources

* [NPS national public points](https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/MapServer/0): nationwide published visitor points. Campgrounds, trailheads, ranger stations, visitor centers, picnic areas, shelters, overlooks, springs and waterfalls supplement OSM. Restricted/non-extant/not-public records are excluded. Coordinates are agency representative points and may have unknown accuracy; they are not GPS-survey claims. Yosemite live query returned486 total POIs, including60trailheads and16campgrounds.
* [USFS recreation sites](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0): agency site points and explicit descriptions of water/restrooms, seasons, fees, restrictions and services. The public site name overrides a stale campground type when it explicitly describes a trailhead (Bayview is one such case). Snapshot status is not treated as a real-time closure feed.
* [RIDB daily public download](https://ridb.recreation.gov/download): [CSV ZIP](https://ridb.recreation.gov/downloads/RIDBFullExport_V1_CSV.zip), downloaded2026-09-06 (246,869,925bytes). Imported5,523 enabled campground/visitor-center records with valid US coordinates into a local SQLite spatially indexed table. Source includes5,789 campground and262visitor-center records before enabled/coordinate filtering. No API key required for bulk export. Permit-sale records and invalid/zero coordinates are excluded. Facility descriptions, telephone, accessibility, fee and stay-limit text remain available offline in the vector attributes. No individual campsite locations are fabricated from a facility center.

Run a refresh with:

```
services/tiles/.venv/bin/python services/tiles/national_recreation.py --import-ridb /path/to/RIDBFullExport_V1_CSV.zip
```

The importer builds and atomically swaps `data/national-recreation/us-agency-recreation-v1/ridb.sqlite`. Refreshing imported data requires invalidating/reversioning already generated recreation tiles; it does not touch basemap or contour downloads. RIDB access is governed by its published API/data access agreement linked from the official download page.

Agency requests are cached by z10 geographic cell, guarded by filesystem locks. Each response is capped at2,000features and transfer-limit/error responses fail rather than being cached as empty. No provider call is made for local RIDB lookups. Matches require compatible feature kinds and either a shared external ID (within5km) or a distinctive normalized name nearby (300m for summits/rocks/passes;120m for sites and other landmarks;15m for small facilities). Campground/trailhead suffixes, punctuation, accents and Mount/Mt variants normalize; generic facility names and differently named loops stay separate. Each merged record retains source-specific details and match provenance. Existing and neighboring OSM amenity-cache matches under the same kind/name rules are marked `osm_duplicate`, `matched_osm_id`, and `osm_match_distance_m`, preserving agency details for popups. Dedupe never starts a new Overpass request. Clients additionally match currently loaded sources, including offline tiles, so late-arriving OSM data can replace an agency symbol without a server refresh. An agency point remains visible until its OSM representation is eligible at the current zoom. Ambiguous nearby matches stay separate. Duplicate OSM node/way/relation representations are suppressed only for the same site and icon within3m, with compatible names.

Properties: `id`, `name`, `kind`, `poi_icon`, `poi_frame`, `poi_image`, `min_zoom`, `agency`, `unit`, `source_url`, `website`, `details`; optional `description`, `water`, `restrooms`, `fee`, `season`, `services`, `activities`, `restrictions`, `ridb_id`, `phone`, `accessibility`, `stay_limit`, `updated`, `coordinate_accuracy`, and OSM-match fields. All HTML descriptions are stripped to plain text. Springs use a natural marker, never a drinking-water symbol.

Live tests: Hetch Hetchy tile14/2740/6322 returns trailhead and restroom;14/2740/6323 returns backpackers-campground restroom. NPS does not publish the backpackers campground itself in this sampled cell; existing OSM remains its source. Fallen Leaf14/2728/6265 merges USFS campground and RIDB232769, retains OSM-match identity and description, adds nearby recreation facilities. Acadia14/5088/5937 contains Fabbri Picnic Area/restrooms and Thunder Hole services;14/5087/5938 contains Blackwoods Campground A Loop. Cold source requests on this run took0.6–0.93seconds; cached records require no upstream call. These timings are observations, not latency guarantees.

## GNIS / GeoNames landmarks

Both nationwide gazetteers are imported into the same downloadable source.
See [gazetteer-sources.md](gazetteer-sources.md) for selected classes, exact
snapshot provenance, counts, duplicate matching, local indexes and refresh rules.

Processing revision v5 reuses v1's pinned raw agency responses and RIDB SQLite
import and adds the local landmark index. Generated tiles use a separate v5
namespace. Existing phone selections refresh only recreation tiles, including
when coverage expands to Alaska across the date line. Source-specific values
and conflicts remain in `source_records`. Basemap OSM peaks and saddles now
participate in client matching alongside the existing facility groups/members.
