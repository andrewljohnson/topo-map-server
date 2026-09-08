# Land cover basemap source

The `landcover` vector tileset uses **USGS Annual NLCD 2024, Collection 1.1**, 30 m categorical land cover. It is a permanent part of the base map and can be cached/downloaded independently like contours.

- Product/access: https://www.usgs.gov/centers/eros/science/annual-nlcd-data-access
- Public service: https://imagery.geoplatform.gov/iipp/rest/services/Vegetation/USFS_EDW_NLCD_Landcover_CONUS/ImageServer
- Checked service catalog: object 40 is `Annual_NLCD_LndCov_2024_CU_C1V1`, begin/end year 2024. Requests lock this object and use raster function None; they do not download a colorized rendering or mix years.
- Coverage: contiguous US only. Alaska, Hawaii, and other uncovered areas keep existing OSM cover. The service's rectangular metadata extent includes nodata surrounding CONUS; it does **not** imply classification throughout that rectangle.
- USGS S3 access was requester-pays during validation; this pipeline uses the public USFS/GeoPlatform service without credentials.

`national_landcover.render_tile(z,x,y)` supports zoom 6–14 and MVT source layer `landcover`. Client overzoom provides higher display zooms. Every request is bounded to at most 256×256 categorical pixels, with nearest-neighbor resampling and no more than native 30 m sampling at zoom 14. At lower zooms this is a generalized depiction, not analytical area statistics. Four-pixel sieving reduces isolated speckles while retaining the water/nodata mask; polygons are simplified by a quarter output pixel. This deliberately favors compact, readable map tiles over every source raster cell.

Properties: `class`, `subclass`, original numeric `nlcd`, `year=2024`, and `source`. Classes are `forest`, `scrub`, `grass`, `wetland`, `farmland`, `rock`, `ice`, and `developed`. Open water is omitted so more precise vector lake/river polygons remain authoritative. Render the terrestrial cover below roads, contours, water, and labels; do not use it as a replacement for protected-land boundaries.

Raw categorical TIFFs persist under `data/national-landcover/<dataset>/rasters/z/x/y.tif`, protected by process locks and atomic writes. Server integration also caches resulting MVTs. Failed downloads and invalid rasters never become cached empty coverage. A dataset-version change is needed when changing source year or polygonization.

Validation: live Yosemite tile 12/687/1583 fetched and vectorized in 1.25 seconds, 41,836 bytes, 339 polygons across developed, forest, grass, rock, scrub, and wetland. Tests verify water/nodata exclusion, coverage, coordinate validation, categorical properties, MVT geometry, and persistent raw-cache reuse.
