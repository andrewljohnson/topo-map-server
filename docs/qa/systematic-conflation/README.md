# Systematic trail and shared-boundary matching

The September 9 TRT, Mt. Rose, and forest-boundary map notes are regression cases for general processing rules. There are no production coordinate exceptions, trail-name aliases, or hidden map rectangles.

## Trail matching (official trails v6)

Start with the existing strict, directional pair match. A named agency trail can extend that match to a differently named OSM trail only when at least 30 m of the strict match lies inside the OSM line, more than 25 m from either end. The reference must exceed 200 m. The expanded directional match must cover at least 150 m and 60% of that reference. Only that confirmed pair receives a maximum 50 m offset allowance. Newly cut agency endpoints reconnect to their matched OSM trace; original endpoints stay fixed. Route metadata and provenance survive on the retained trace.

This handles differently named, generalized agency surveys without globally equating their names. It does not authorize removing arbitrary nearby trails. Parallel traces without an interior seed, short shared junctions, crossings, and unmatched extensions have regression coverage. A historical reroute close to its replacement can still be ambiguous: this is conservative cartographic conflation, not evidence of current trail access.

## Forest boundary matching (agency boundaries v3)

Forest administrations must have intersecting polygons and a coherent edge of at least 1 km within 250 m of the earlier forest outline. Along roughly 1–3 km sections, at least eight of nine side probes must show the two interiors on opposite sides. This identifies a shared administrative edge rather than merely nearby lines. Real gaps, nested designations, short edges, and crossings remain. Wilderness and park designations do not enter this wider forest-pair rule.

All designation polygons are retained. Only the redundant stroke is suppressed. A 1 cm subtraction buffer avoids floating-point fragments from substring operations in normalized map coordinates.

## Evidence

- 30 trail-matching tests and 100 national-data tests pass, including four captured real trail pairs and synthetic false-positive cases.
- All 640 Tahoe fine-source tiles checked: 8,031 OSM feature occurrences retain identical geometry.
- All eight designation polygons in the Tahoe source cell remain identical; all three non-forest outlines remain identical.
- TRT note: secondary agency line 310.8 m → 0; OSM 357.0 m unchanged.
- Mt. Rose note: secondary agency line 1,066.1 m → 0; OSM 1,103.0 m unchanged.
- Forest note: redundant basin outline 14,190 m → 742 m, retaining separate branches. Wilderness and the retained forest outline are unchanged.

[Before/after geometry proof](before-after.png) is a data-level drawing, not a renderer screenshot. [Reported viewport measurements](reported-views.json) and [Tahoe-wide audit](tahoe-audit.json) accompany it.

Re-run `experiments/tahoe/audit_conflation.py --help` for the baseline/candidate geometry audit. The real trail pairs are checked into `services/tiles/fixtures/tahoe-trail-alignment.json`; ordinary trail-matching tests require no network or large source cache. These checks cover this Tahoe build and matching safeguards, not every duplicate nationwide.
