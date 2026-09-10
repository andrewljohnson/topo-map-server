# Campground and gazetteer duplicate corrections

## Halfmoon Campground

Reported at `34.650261,-119.068342`, zoom 18. Live California r1 visibly draws two Halfmoon campsite icons plus a legitimate toilet.

- USFS `5075.003871`: `[-119.0681085743344,34.64981797272236]`.
- OSM campground `way/1347238220`: point-on-surface `[-119.0686906,34.6508616]`.
- Anchors are 127.8 m apart, beyond the existing 120 m point-match limit. USFS point lies approximately 4 m outside the actual campground polygon. Both source websites identify USFS recreation area 10985.
- OSM toilet `way/1347238219` is a distinct facility and remains visible.

The server now accepts an unambiguous, same-name/same-kind campground polygon match, with 10 m survey tolerance around the real outline. It reads retained raw geometry, including job-local source caches, without a new upstream query. Other kinds, different names/loops, and ambiguous overlapping candidates remain separate. No geometry or original source record is moved/deleted. Recreation dataset revision is `us-agency-recreation-v9`.

The shared web/Expo POI matcher now honors that explicit `matched_osm_id` when the corresponding OSM point is loaded and eligible. It restores the agency marker if the OSM point leaves loaded data. Toilet icons and details remain available.

Regression fixture: `services/tiles/fixtures/halfmoon-campground.json` (retained OSM and USFS records). Tests cover the actual anchors/outline, outside points, different names/types, ambiguous outlines, and client load/unload behavior.

## Three Brothers, Yosemite

GNIS `1659995` at `[-119.6148102,37.7460327]` and GeoNames `5402427` at `[-119.61517,37.74159]` represent the same named summit/formation, approximately 496 m apart. The old 300 m landmark match left both. Lower Brother (`gnis:253530`) and Middle Brother (`gnis:253546`) are distinct named pillars and must survive.

A new **offline catalogue-only** rule allows 750 m for matching exact normalized names and the same summit/rock class across GeoNames→GNIS, only with one eligible catalogue counterpart. A viewport never widens this tolerance or resolves ambiguity. Distinct official GNIS identities and coordinates are retained. Both source records survive in provenance. An elevation at the offset GeoNames point is not transferred as a spot height at the retained GNIS anchor.

Tests cover actual Three Brothers coordinates, Lower/Middle Brother retention, ambiguous official counterparts, and exclusion of springs/waterfalls and same-source records. Candidate nationwide import retained all 117,404 GNIS IDs and coordinates exactly; survey matching performed 3,261 additional merges. A broader sample included Hemlock Hill, Sawtooth Mountain, Huckleberry Mountain, Jones Mountain, and West Turkey Cone near the 750 m bound. This is identity matching based on catalogues, not independently surveyed terrain validation.

## Broader catalogue audit and installation

See `poi-survey-match-audit-2026-09-09.json`: 3,259 formerly separate pairs exceeding 300 m, median 464.65 m, 95th percentile 712.13 m, maximum 749.36 m. Full catalogue rechecks found exactly one official same-name/class candidate for every accepted pair. Reviewed 24 deterministic hash-selected examples and the 12 largest offsets. All 117,404 GNIS identities and coordinates were byte-equivalent numerically before/after.

Of these pairs, 56 have both an existing canonical elevation and an offset source elevation. The largest disagreements are Republic Mountain (260 m) and Sunset Peak (212 m). The new rule preserves existing canonical heights; offset measurements remain only in source provenance. Samples and limitations are in the audit JSON. Independent terrain/field verification remains outside this matching audit.

The candidate nationwide catalogue and recalculated hierarchy passed SQLite quick checks and were atomically installed; previous databases remain backed up in `/tmp/landmarks-v1.sqlite.pre-ca-r2-poi` and `/tmp/hierarchy-v1.sqlite.pre-ca-r2-poi`. Ranking rebuilt in 6.93 seconds. Three Brothers now has one official anchor and two source records; Middle Brother and Lower Brother retain their own IDs.
