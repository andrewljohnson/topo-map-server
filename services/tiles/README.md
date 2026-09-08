# National on-demand mode

National mode now serves raw DEM PNGs (`/dem`, `/dem-batch`) for device-generated
contours and hillshade. See [device terrain](../../docs/device-terrain.md);
regional contour commands below are the legacy pipeline.

The CLI now defaults to nationwide on-demand generation. See the repository README for current setup, source provenance, California job commands, cache locations and deployment. `/tiles` and `/tile-batch` supply normalized Protomaps OSM vectors at zooms 0–14; `/contours` and `/contour-batch` supply USGS-derived contours at zooms 11–14. `/metadata` advertises independent source IDs and `/jobs/california` reports the background job. `TILE_DATA_DIR` relocates all data.

The sections below document the retained **regional Maryland importer**. Use `--mode regional` with its commands; these bounds and preprocessing requirements do not constrain national mode.

# Maryland vector tile pipeline

Downloads the Maryland **OpenStreetMap source extract** from Geofabrik, indexes real geometry in SQLite and generates **Mapbox Vector Tile protobuf (MVT/PBF)** files. Every feature remains vector geometry. The service never requests the public OpenStreetMap rendered tile service.

Coverage bounds: `[-79.49, 37.88, -75.03, 39.73]`. Initial view: Baltimore. The extract includes surrounding features only where supplied by Geofabrik; coverage is regional, not a complete world basemap.

## Setup

```sh
cd services/tiles
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tile_service.py prepare
.venv/bin/python contours.py --workers 3
.venv/bin/python tile_service.py warm --min-zoom 6 --max-zoom 8
.venv/bin/python tile_service.py serve
```

The server binds `0.0.0.0:3001` for web and same-Wi-Fi mobile clients. `PORT` and `TILE_DATA_DIR` can override those settings. The pipeline also downloads the small Geofabrik extract boundary file, `maryland.poly`. The source snapshot is about 204 MB; allow several minutes and a few GB of disk space for the indexed database and growing tile cache.

## API and vector schema

- `GET /health`: readiness and format
- `GET /metadata`: region, center, initial zoom, bounds, versioned tile URL, dataset version, contour availability and attribution
- `GET /tiles/{z}/{x}/{y}.pbf`: OSM-only MVT
- `GET /contours/{z}/{x}/{y}.pbf`: contour-only MVT (ready DEM required)
- `GET /tile-batch`: OSM tile batches
- `GET /contour-batch`: contour tile batches

Both tilesets use `application/vnd.mapbox-vector-tile` and negotiate gzip. Metadata advertises them separately under `tilesets.osm` and, when ready, `tilesets.contours`. Each entry contains its own `datasetId`, versioned `tileUrl`, `batchUrl`, `batchSize`, `minZoom`, `maxZoom` and `bounds`. Top-level tile fields remain aliases for OSM compatibility. Clients compose the two vector sources in one map style.

CORS is enabled. Supported source zooms are **6–14**; clients can overzoom for closer views. Tiles outside region bounds return 404. Grid downloads use zoom 12 regions, with child tiles through zoom 14. Source geometry is clipped with an eight-pixel buffer and quantized at extent 4096; road classes and small-area filtering reduce low-zoom payloads. Polygon holes remain holes. The OSM source layers are:

`land`, `residential`, `grass`, `forest`, `rock`, `water`, `waterline`, `building`, `rail`, `road`, `label`. The separate contour tileset contains only the `contour` source layer.

Base-map features have `class` and `name` properties. `label` features are place points; road class uses the OSM highway value. `water` includes OSM water polygons and reconstructed directed OSM coastal water, including Chesapeake Bay. The actual Geofabrik `.poly` extract boundary closes coastlines where extraction cuts them; no artificial shoreline is drawn between arbitrary endpoints. The `land` layer provides a regional background below other polygons. Styles should draw water after land cover.

Maps contain roads, paths, railways, buildings, water, land cover, place names and elevation contours in feet after the DEM pipeline completes. Hillshade, routing and search are not implemented. Coastlines use the regional extract and are tested at known land/water coordinates; generalizing this pipeline to arbitrary extracts may require a separately processed global coastline dataset, because incomplete coastline ways cannot reliably close polygons.

The persistent cache path includes source SHA256 and encoder version (`datasetId` in metadata), so changed source data has a separate cache. Clients must also namespace their offline downloads by `datasetId`. Increment `STYLE_VERSION` for OSM geometry output changes and `CONTOUR_STYLE_VERSION` for contour geometry output changes. Each tileset has an independent cache namespace. Styling itself lives in the clients and does not require rerendering vector tiles.

## Elevation contours in feet

Run `.venv/bin/python contours.py --workers 3` after the OSM preparation. The pinned, version-controlled `dem_sources.json` lists the 15 official dated USGS 3DEP **1/3 arc-second DEM** Cloud Optimized GeoTIFF sources covering Maryland, including source IDs, acquisition-product dates in titles/URLs, catalog URLs, vertical units and datum. A `--manifest` override supports a reviewed updated snapshot. The service reads small HTTP range windows from these COGs; it does not download all fifteen complete rasters.

The source resolution is **1/3 arc-second (approximately 10 m north-south and 8 m east-west at Maryland latitudes)**. These are USGS 3DEP elevation grids, not fabricated terrain or a 1 m lidar product. Heights are NAVD88 orthometric elevations in meters, converted using **exactly 0.3048 meters per international foot**. Contours occur every **20 ft** (6.096 m), with **100 ft** index lines. Source resolution and contour interval do not imply survey accuracy. The pipeline aligns sources on one common native-resolution NAD83 grid using bilinear resampling where alignment requires it, then explicitly transforms output coordinates to WGS84/Web Mercator for map tiles.

Processing is bounded to 1024×1024-pixel cores plus a two-pixel halo by default. Neighboring chunks use the same global grid, source precedence and halo, and contour lines are clipped to their exact core boundary and the Maryland extract coverage. Synthetic tests compare split-chunk results against a continuous plane to catch seam gaps. Raster NoData remains masked with `corner_mask=False`; no interpolation is performed across missing-data edges. Flat zero-elevation sea cells do not generate a misleading coastline contour; only positive 20-foot levels are generated.

Each completed chunk writes a resumable DEM window and SQLite checkpoint under `data/dem/checkpoints/<build hash>`. A failed network request or interrupted build can be rerun with the same manifest/grid to reuse completed chunks. The live `data/contours.sqlite` is replaced atomically only when **all** selected coverage chunks have completed. Old OSM data and tile caches remain intact. Final provenance, source URLs, valid/coverage pixel counts and a hash incorporating the actual DEM window bytes are recorded in that database and `data/dem/contours-provenance.json`. NoData coverage can include offshore water; it is recorded rather than silently filled.

The `contour` MVT source layer contains line geometry and:

- `ele_ft`: integer elevation in feet
- `index`: boolean, true for a 100-foot index contour
- `name`: display label such as `100 ft`

At source zooms **11–12**, only 100-foot index lines are included; at **13–14**, all 20-foot lines are included. The contour API accepts zooms **11–14** and contains only contour geometry. OSM accepts zooms **6–14** and never includes contour geometry. Clients overlay both sources and download/cache each tileset independently for offline use. Use `/contour-batch` with the contour dataset ID for elevation downloads.

Metadata reports `contours.status` (`not-ready` or `ready`), contour intervals, source resolution and vertical datum. `tilesets.contours` is advertised only after the DEM build completes. Its dataset ID depends on the terrain source hash and contour encoder version; OSM IDs depend only on OSM data and the OSM encoder version. Updating either source preserves the other tileset’s offline cache. Each advertised tile URL includes `?datasetId=...` to avoid older browser responses. A stale or cross-tileset ID returns HTTP 409 independently on single-tile and batch endpoints. Without a ready DEM, contour endpoints return HTTP 503. Stop and restart the server when publishing a newly completed database to keep all in-flight requests on one snapshot.

## Batched offline downloads

Each metadata tileset advertises its batch URL and `batchSize: 8`: `/tile-batch` for OSM and `/contour-batch` for contours. Request up to eight distinct in-coverage keys from one tileset:

```text
GET /tile-batch?datasetId=maryland-…-mvt-v3-osm&tiles=12/1176/1561,14/4705/6244
```

The JSON response is `{datasetId, tiles: [{key, data}], errors: [{key, error}]}`. Each `data` value contains base64-encoded original PBF bytes. Successful tiles remain cacheable by the client even when another tile fails; retry only keys in `errors`. Malformed keys, invalid coverage/zoom, duplicate keys, or more than eight keys return HTTP 400 before rendering. A stale dataset ID returns HTTP 409 with the current ID before rendering; refresh metadata and switch the offline cache namespace.

HTTP/1.1 keep-alive reduces connection setup. Both PBF and batch responses negotiate gzip (level 4); normal browser/Expo fetch transparently decompresses the response. `Vary: Accept-Encoding` prevents representation mixups. The persistent disk cache always stores original PBF bytes. Batch envelopes use `Cache-Control: no-store`; tile endpoint responses retain their normal cache lifetime.

CPU-intensive rendering is bounded to two concurrent tiles (`TILE_RENDER_CONCURRENCY` overrides it). The CLI server uses two spawned rendering processes by default, so Python encoding can use two CPU cores. Set `TILE_RENDER_WORKERS=0` to render inline; the pool is never created merely by importing the module. Ctrl-C/SIGTERM shuts down the worker pool. A batch processes one tile at a time; the mobile client may issue two requests concurrently. Interactive map requests waiting for rendering take precedence over queued download work. Cached responses bypass the render gate. A bounded cache reuses simplification of large source geometries across adjacent tiles; source bytes are part of its key so refreshed data cannot reuse stale geometry. Compression and fewer requests improve network transfer; generation of uncached vector tiles still requires CPU work.

Run actual HTTP integration tests and the reproducible benchmark from this directory:

```sh
.venv/bin/python -m unittest -v test_tiles.py test_http.py test_workers.py test_contours.py
.venv/bin/python benchmark.py --rounds 3
.venv/bin/python benchmark.py --compare-processes
```

The benchmark starts an ephemeral localhost server and uses an isolated temporary cache, leaving the live cache intact. It downloads the real 27-tile Baltimore cell (six ancestors plus 21 tiles at zooms 12–14), reports cold generation, cached serial and batched transfer sizes/times, and request counts. The optional process comparison measures cold encoding separately. Loopback timing does not represent phone Wi-Fi latency or bandwidth; use payload size and request count alongside measured network conditions.

## Refresh

`prepare` reuses `data/maryland.osm.pbf`. Remove that file to download the latest snapshot, or pass `prepare --source /path/to/maryland.osm.pbf`. The import atomically replaces `maryland.sqlite`; stop the server during a refresh to avoid serving mixed versions across concurrent requests. Previously generated caches can be removed after clients transition. The old Liechtenstein source/cache, if present from initial setup, is never selected by the Maryland service.

## Tests

```sh
.venv/bin/python -m unittest -v test_tiles.py
```

Checks cover zoom/bounds, MVT coordinate orientation, decoded polygon holes, actual Maryland roads/buildings, cache reuse and known coastal land/water points. Run `prepare` first for the real-data checks.

## Cloud

The Dockerfile runs the same pipeline without bundling a source snapshot. Mount persistent storage at `/data`, run `python tile_service.py prepare` once, then use the default command to serve. Put an HTTPS reverse proxy/CDN ahead of the service. The built-in Python HTTP server is intended for local development; replace it with a production serving layer before a public deployment. For larger regions and many concurrent requests, move preprocessing out of the serving path and upload prebuilt tiles or a tile archive to durable object storage.

## Attribution and provenance

Data: [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL. Source: [Geofabrik Maryland](https://download.geofabrik.de/north-america/us/maryland.html). Show attribution visibly in online and offline maps. Retain data provenance and license notices when distributing adapted databases.

Detailed protected-area boundaries use a separate `boundaries` vector tileset
(`/boundaries/{z}/{x}/{y}.pbf`, `/boundary-batch`, zooms 8–14, overzoomable).
The `areas` source layer contains both polygon fills and true boundary lines;
style each with its geometry-type filter. Official NPS, Forest Service and
Wilderness agency geometry is fetched at 0.000025 degree tolerance (roughly
3 m), cached per agency object, dissolved by unit, and simplified to 0.35 display
pixels per tile. The overview GeoJSON remains for low zooms, labels and search.
A durable zoom-8 spatial index bounds upstream requests; missing/truncated
responses fail for retry and never create empty success tiles. Boundary I/O has
its own two-request gate and never occupies terrain workers. These are official
administrative boundaries, not inferred terrain edges or guarantees of access.
