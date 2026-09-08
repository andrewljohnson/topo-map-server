# Trail route symbols and data

The included SVGs are original compact route-reference badges. They are **not official trail logos**. NPS official trail emblems are protected federal marks and require permission even for maps/electronic media. PCTA also directs logo users to request permission. Those are distinct from open trail geometry licenses. The app uses the original badges until an authorized official asset can replace each manifest entry.

- NPS logo permissions: https://www.nps.gov/pohe/learn/management/tools-route-marking-graphic-identity.htm
- PCTA media/logo request: https://www.pcta.org/about-us/media/media-images/

## PCT centerline

`services/tiles/regions/pct-centerline-2026.geojson.gz` is the full 94-part centerline downloaded September 6, 2026, from PCTA's official public data share (January 2026 annual update). Geometry is rounded to six decimals and gzip-compressed; no route simplification. The downloadable Full_PCT.geojson file is ID1503926212639 in their public Box share. This data is CC BY 4.0, including commercial reuse, per https://www.pcta.org/discover-the-trail/maps/pct-data/ . Credit: **Pacific Crest Trail Association**, https://www.pcta.org/ . License https://creativecommons.org/licenses/by/4.0/ .

Official download entry: https://pcta.app.box.com/s/wsv09z18lw4kwptjrxd79kj07xm6ufsr/folder/305401160536 .

## Other trails and vehicle designations

- USFS National Forest System Trails: https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0
- NPS public visitor trails: https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_Trails_Geographic/FeatureServer/0
- USFS published Motor Vehicle Use Map roads/trails: https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_MVUM_02/MapServer/1 and /2

Credit US Forest Service and National Park Service. Public agency GIS data are not live closure notices. MVUM route properties retain separate vehicle permissions and dates-open fields; seasonal does not mean currently open. Official trails are agency coverage, not all trails nationwide. At zoom13+ a merged OSM/agency network draws each matched stretch once and retains unmatched agency trails. Long-distance overview route lines stop at zoom13; badges remain from zoom6 upward. MVUM roads and motorized trails participate in conflation, with source-specific permissions preserved. See [data-sources.md](../../docs/data-sources.md) for tolerances and limitations. Named AT/CDT/JMT/TRT and other scenic route segments are recognized from explicit agency trail names; only PCT currently has a separately complete continuous centerline. No trail permission inferred from missing attributes. The renderer excludes non-public NPS and non-terra USFS paths.

## Tile contract

Dataset `us-official-trails-v3`, zooms5–14, bounds[-180,18,-60,72]. Layers `network`, `trails`, `roads`, `routes` (line geometries). Common properties `id,name,kind,agency,ref,surface,trail_class,use,seasonal,season_description,access,mvum_symbol,route_ref,source_url`. Routes additionally `badge` (`trail-PCT`, etc.). MVUM includes exact published `passengervehicle`, `highclearancevehicle`, `motorcycle`, `atv`, `fourwd_gt50inches` and corresponding `*_datesopen` strings where provided. Preserve these strings without interpreting calendar status. Overview z5–10 queries only recognized long-distance names, details z11–14 include all agency trails and MVUM. Detail responses are fetched per z11cell, persisted across adjacent tile requests; IDs first then batches of100 prevent transfer-limit truncation. Failed requests never create successful empty cache entries.
