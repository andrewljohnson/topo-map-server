# California r3 cloud release gate

Generation completed in6,112.94seconds (101.9minutes), first attempt. Immutable ledger contains31,572 verified objects totaling12,876,147,992bytes:17,838base/overview and13,734DEM.

Actual mobile TileStore test against the cloud candidate passed eight regions: Tahoe, Yosemite, San Francisco, Los Angeles, San Diego, Shasta, northern coast, Joshua Tree.134unique tiles,36requests,20.96seconds; offline store reload,1024pixel DEMs, and notes/GPS fixture preservation passed. See offline.json.

Cloud candidate browser checks passed the original Tahoe and southern California PCT duplicates, Halfmoon (onecampground marker plusrestroom), ThreeBrothers (oneformation plusdistinctMiddleBrother), and quieter MountainRoom/Yosemite walkways. SanFranciscoz13 renders streets/parks/labels; Shastaz11 rendersregionalfeatures. Known newer TwinPeaks PCT report is not included in r3 and is queued in trailsv16 for the next immutable release. NearbyTRT overlap remainsseparateQA.

Shasta z13 also passed: detailed contours, hillshade and MountShasta label. Public promotion succeeded; default metadata and publication both report complete `topo-california-20260910-r3`.
