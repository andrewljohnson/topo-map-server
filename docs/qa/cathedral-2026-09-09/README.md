# Cathedral Trail survey overlap

Reported in r13 at [-120.074048, 38.89009], zoom 15.457. Two z14 source children (2727/6267 and 2727/6268) reproduce a retained USFS Cathedral Trail survey alongside the unnamed OSM reference path. The northern OSM path carries ref 17E05, also present on the agency trail. The pinned source inputs are retained in `services/tiles/fixtures/cathedral-trail-alignment.json` in local ground metres.

The existing 50 m refinement required both names and calculated coverage over entire batched MultiLineStrings. It now evaluates each connected line independently, including unnamed lines. It still requires at least 30 m of tight (2.5 m) interior alignment, excluding 25 m at either end, directional agreement, and at least 60% / 150 m reference coverage. Different explicit trail numbers disallow widening. Names or proximity alone do not authorize removal. Original OSM geometry is unchanged; metadata is partitioned only onto matched portions.

All 47 conflation tests and 109 national tile tests pass. The real-source regression checks both OSM geometry directions, retained main-survey length below 350 m per source tile, and preservation of the unconfirmed Cathedral Spur. Tahoe connectivity audit has no new cut-end or lost-junction findings. Remaining source dead ends are not automatically connected.

Cathedral Spur (17E05A) remains deliberately separate: its nearby unnamed OSM path lacks sustained tight alignment. Endpoint proximity alone cannot distinguish survey error from a legitimate alternate path. This change addresses the confirmed main-trail duplication without silently deleting that uncertain geometry.

San Francisco's independent connectivity audit also has no new cut-end or lost-junction findings. The two reported source children retain 281 m and 222 m of the main agency trail (previously 443 m and 648 m); unmatched extensions remain, while the OSM path is retained in full. Lengths include the source processing halo and must not be interpreted as deduplicated ground distance across adjacent tiles.

Published and promoted `topo-z12-pilot-20260909-r14`: 212 base / 140 DEM objects, 352 verified, publication 121.0 seconds. Browser proof at the reported center/zoom confirms one main shoreline trail, with terrain restored after DEM rendering. Actual mobile TileStore downloaded two regions (37 unique objects) in 8.04 seconds; offline reload, 1024-pixel DEMs and notes/GPS preservation passed. Live `/metadata` confirms r14. Expo remains available at `exp://192.168.1.107:8081`; reload to pick up the new release.
