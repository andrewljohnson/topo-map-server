# Cathedral Trail survey overlap

Reported in r13 at [-120.074048, 38.89009], zoom 15.457. Two z14 source children (2727/6267 and 2727/6268) reproduce a retained USFS Cathedral Trail survey alongside the unnamed OSM reference path. The northern OSM path carries ref 17E05, also present on the agency trail. The pinned source inputs are retained in `services/tiles/fixtures/cathedral-trail-alignment.json` in local ground metres.

The existing 50 m refinement required both names and calculated coverage over entire batched MultiLineStrings. It now evaluates each connected line independently, including unnamed lines. It still requires at least 30 m of tight (2.5 m) interior alignment, excluding 25 m at either end, directional agreement, and at least 60% / 150 m reference coverage. Different explicit trail numbers disallow widening. Names or proximity alone do not authorize removal. Original OSM geometry is unchanged; metadata is partitioned only onto matched portions.

All 47 conflation tests and 109 national tile tests pass. The real-source regression checks both OSM geometry directions, retained main-survey length below 350 m per source tile, and preservation of the unconfirmed Cathedral Spur. Tahoe connectivity audit has no new cut-end or lost-junction findings. Remaining source dead ends are not automatically connected.

Cathedral Spur (17E05A) remains deliberately separate: its nearby unnamed OSM path lacks sustained tight alignment. Endpoint proximity alone cannot distinguish survey error from a legitimate alternate path. This change addresses the confirmed main-trail duplication without silently deleting that uncertain geometry.
