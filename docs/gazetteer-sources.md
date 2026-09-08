# GNIS and GeoNames hiking landmarks

The nationwide import is part of the existing `recreation` vector tileset,
processing version `us-agency-recreation-v8`. It adds named natural landmarks;
it does not introduce a toggleable overlay or another phone download queue.
The local source index covers US features inside the map's latitude range 18–72,
including Alaska on both sides of the date line and Hawaii. Its envelope is
[-180,18,180,72]; records are restricted to US/domestic sources, not other countries
inside that envelope. Territorial features outside that latitude range are omitted.

## Pinned inputs and import totals

- [USGS GNIS Domestic Names](https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data):
  the National text archive, released 2026-08-28. Read 981,706 records; retain 117,404
  named, valid-coordinate landmarks in the selected classes. This is the current
  DomesticNames product, not the unmaintained 2021 administrative-feature archive.
- [GeoNames US gazetteer](https://download.geonames.org/export/dump/):
  US.zip released 2026-09-07 UTC. Read 2,241,394 records; retain 113,517 selected US
  landmarks. This is the gazetteer dump, not the similarly named postal-code ZIP.
- Merge 102,951 duplicate records, leaving127,970 indexed landmarks. Retain 54
  ambiguous matches separately. These are gazetteer-to-gazetteer counts;
  additional NPS/USFS/OSM matching happens during tile generation and rendering.

Exact URLs, archive SHA-256 checksums, byte sizes and import totals are recorded in
[`gazetteer-sources.json`](../services/tiles/regions/gazetteer-sources.json).

| Map kind | GNIS classes | GeoNames codes | Retained features | First zoom |
| --- | --- | --- | ---: | ---: |
| Summit | Summit | T.MT, T.PK, T.HLL | 77,493 | 13 |
| Pass / saddle | Gap | T.PASS, T.GAP, T.SDL | 8,447 | 13 |
| Spring | Spring | H.SPNG, H.SPNT, H.SPNS | 36,715 | 14 |
| Waterfall | Falls | H.FLLS | 2,543 | 13 |
| Natural arch | Arch | none | 712 | 14 |
| Rock landmark | Pillar | T.RK | 2,042 | 14 |
| Cave | Cave | S.CAVE | 18 | 14 |

GNIS has no cave records in this imported extract; those 18 are GeoNames additions.
A spring marker does not claim potable water, reliable flow, or legal access.
Hot/sulphur spring classifications remain attributes. Source coordinates are
preserved; no representative site points are invented from nearby facilities.

Excluded: historical names, invalid/nonfinite coordinates, settlements, area
centroids, ranges/groups of peaks, lake/stream centroids, generic camps/huts,
mines, administrative facilities, and trail gazetteer points. A trail point is
not an alignment or a trailhead. GeoNames S.ARCH may include constructed arches,
so it is not imported as a natural arch. Existing lake polygon labels and park
boundaries remain their own geometry-based products.

## Matching and display

1. GNIS official feature IDs remain distinct. GeoNames matches compatible kinds,
   normalized distinctive names and positions within 300m for summits, rock landmarks
   and passes, and 120m for springs/falls/other features. Summit and rock
   classifications can match the same named landform; a pass never matches a peak. If two candidates are
   within 30m of one another in match distance, retain the ambiguous record. It
   carries a flag so a partial viewport cannot later guess the match again.
2. The tile server combines the local index with NPS, USFS and RIDB points.
   Agency records take precedence; missing details can be filled. Conflicting
   source-specific values and original coordinates remain in `source_records`.
   Shared external IDs can match within 5km; conflicting GNIS IDs prevent merging.
3. The client matches both OSM amenity groups/members and basemap POIs, including
   peaks and saddles. It keeps the existing eligible OSM representation and
   attaches gazetteer details to its tap popup. Tile-local OSM numeric IDs are not
   mistaken for globally unique IDs. Loaded coordinates/class/name identify those
   popup associations. Matching reruns when sources arrive and works offline.
4. A [nationwide label hierarchy](label-ranking.md) admits isolated regional
   summits from z6, then progressively adds smaller peaks and destinations.
   Detailed OSM peak geometry takes over from z14 when a matching point exists.
   Other landmarks enter at z11–14 according to type and spacing. Circular
   natural-feature symbols appear in the current-viewport legend.

Stable `gnis_id`/`geonames_id`, source class, state/county, source update date,
alternate GeoNames names, license, and source links remain in the point metadata.
GeoNames alternate names are retained for inspection, not blindly treated as
modern-name aliases. Only the supplied elevation field becomes a reported spot
height in feet; GeoNames' separate coarse DEM field is not used as a summit height.
GNIS's current text product does not supply elevation. Neither source establishes
trail conditions, current facilities, or access permission.

## Storage, refresh and cloud preparation

Implementation: [`national_gazetteers.py`](../services/tiles/national_gazetteers.py).
`services/tiles/data/gazetteers/landmarks-v1.sqlite` is a local SQLite/R-tree
index. Viewport requests perform indexed local queries, never GNIS/GeoNames API
calls. The raw ZIPs remain under `data/gazetteers/raw/`. Both locations follow
`TILE_DATA_DIR`. Data files are excluded from Git; the importer and manifest are
versioned in the repository.

To rebuild from the retained source archives:

```sh
services/tiles/.venv/bin/python services/tiles/national_gazetteers.py \
  --gnis services/tiles/data/gazetteers/raw/gnis.zip \
  --geonames services/tiles/data/gazetteers/raw/geonames.zip
```

The importer checks schema, imports both sources, builds indexes, and checks the
SQLite database before atomically replacing the prior index. Failed imports leave
the previous index usable. A missing required index raises an error for landmark
coverage rather than caching a successful empty detail tile.

For a source refresh, verify the downloaded archive checksums against the manifest
when reproducing this snapshot. If intentionally accepting newer archives, update
the manifest, rebuild `poi_ranking.py`, and bump `national_recreation.DATASET_ID`
before serving generated tiles.
Source URLs point to upstream current releases and are not immutable snapshot URLs.
Persist/copy the built index and raw archives to the cloud deployment's data volume
or artifact store; each server needs this index and the derived
`data/label-ranking/hierarchy-v1.sqlite` described in [label ranking](label-ranking.md). The index can be shared
read-only across workers. This import does not imply all generated nationwide MVTs
are warm; those are built and cached as needed.

Phone downloads reuse the existing recreation batches. Saved regions survive this
processing revision and its expanded date-line bounds; only recreation files
refresh. Basemap, contours and other compatible cached source files remain intact.

## Attribution

GNIS is USGS federal/public-domain geographic names data. GeoNames is
[CC BY 4.0](https://download.geonames.org/export/dump/readme.txt). Credit and license
links appear on the map's recreation source and information drawer, and source IDs
and links are retained in offline feature details. Existing OSM/agency credits
remain. See the main [data-source guide](data-sources.md) for complete composition.
