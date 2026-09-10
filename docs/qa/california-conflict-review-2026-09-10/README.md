# California source-conflict audit — 2026-09-10

## Findings

Audited published release `topo-california-20260910-r4`. All 34 deliberately selected regional z12 tiles downloaded and decoded successfully. The scanner found **51 named cross-source overlap candidates: 46 trail and 5 road groups, across 19 sampled regions**. These are review candidates, not 51 confirmed errors or an estimate of statewide error prevalence. Counts are per sampled tile, not unique physical trails.

Visual review of the live map found competing trail alignments at:

- [Meysan Lakes Trail](https://topo-map.andrewljohnson.workers.dev/#16/36.573009/-118.234568): repeated near-parallel alignments and intersecting switchback shapes.
- [Chapman Trail](https://topo-map.andrewljohnson.workers.dev/#16/34.252681/-117.617730): competing parallel lines and switchbacks.
- [Shackleford Trail](https://topo-map.andrewljohnson.workers.dev/#16/41.541229/-123.118120): long competing representations with similar names and different geometry detail.
- [Carmel River Trail](https://topo-map.andrewljohnson.workers.dev/#16/36.314931/-121.656182): competing smooth and more detailed alignments.

Mount Whitney Trail also has suspicious overlapping switchback geometry. Visual inspection establishes a source-selection problem; it does not establish which surveyed route is correct on the ground.

The recurring failure mode is that an agency feature that cannot be confidently matched can survive as an additional rendered trail. Increasing matching distance indiscriminately would also erase legitimate parallel trails and branches.

## Reproduction and limits

Run from the repository root:

```sh
services/tiles/.venv/bin/python experiments/tahoe/audit_published_conflicts.py \
  --release topo-california-20260910-r4 --output /tmp/california-conflict-audit
```

The read-only scanner downloads 34 regional tiles, groups `trails__network` fragments by normalized name, agency, and road/trail family, and unions fragments before comparing different agencies. It flags bilateral proximity overlap of at least 100 m within 50 m, covering at least half the shorter grouped geometry. It does not count intentional replacement of another rendering layer as duplication. A cached replay reproduced 34 successful tiles and 51 candidates. Full candidate evidence is in `candidates.json` beside this document.

This is not a California census. It misses unnamed or differently named matches, same-source duplicates, large offsets, and features outside the sampled tiles. It does not audit POIs or boundaries. Legitimate parallel paths, grade separation, and route alternatives can be flagged. The 50 m threshold is for triage, never automatic deletion. Coordinates use an approximate local metric scale suitable for candidate detection.

## Proposed systematic QA (not yet implemented)

We can enumerate every decision our algorithms make, and every candidate considered by defined searches. We cannot guarantee discovery of every real-world conflict: source omissions, inconsistent names, and displaced geometry can evade candidate generation. Therefore combine decision accounting, independent residual-conflict detection, and visual/source review.

### 1. Canonical source preparation before tile clipping

Retain immutable raw inputs and a manifest of versions and coverage. Resolve entities and networks regionally with neighbor halos before clipping tiles. Use stable upstream feature identities rather than tile-local fragment IDs. Separate the choice of geometry from names, route membership, elevation, access restrictions, and other attributes; no source is universally best for every field.

For example, a dedicated route source may establish PCT identity and membership while a more detailed underlying path supplies geometry. Record the policy explicitly, preserve alternatives and access paths, and do not silently overwrite disagreeing access information.

### 2. Exhaustive decision ledger

Use an indexed SQLite audit database containing input identities, source versions, geometry hashes, input coverage, rule/version, candidate identities, measured overlap/distance/shape evidence, thresholds, selected geometry, attribute provenance, suppressed portions, and affected regions/tiles. Store geometry once and reference it.

Record successful matches, rejected candidate matches, ambiguous near-matches, and features retained without a candidate. Separate entity merging, source precedence, boundary-stroke suppression, and temporary POI display clustering. Decisions should be reproducible; overrides must be reconsidered when their input geometry or policy changes.

Current blind spots include `feature_matching.merge_into` retaining source records but not full rejected alternatives; trail conflation retaining unmatched agency remnants; boundary stroke suppression without per-segment accounting; and POI outcomes that can depend on available neighbor tiles. Different official identifiers require explicit conflict handling rather than an unexplained name-and-distance merge.

### 3. Explicit ambiguity policy and review queue

Keep conflicting records in the audit catalog. Classify outcomes as confidently same, confidently separate, or review required. A suspicious supplement should not automatically produce a second equally styled path: retain the established primary representation pending review, while preserving confidently novel agency-only coverage. Apply that policy only to candidates with sufficient conflict evidence; do not remove all unmatched agency trails.

Rank review by length/area affected, source disagreement, new or changed decisions, proximity to thresholds, important routes, and likely user exposure. Review all high-risk decisions plus a stratified sample of accepted decisions. A review record should show both inputs, selected output, reason, and before/after views.

### 4. Release gates

- Every suppression or replacement has an explicit reason and retained counterpart, or a documented removal decision.
- Original OSM linework, official identities, and legal designation polygons have preservation checks with narrowly audited exceptions.
- Detect new disconnected cuts, lost junctions, tile-edge differences, and nondeterministic results under shuffled processing order.
- Run a separate residual conflict scanner on the final output; matching logic must not be its own only test.
- Check POIs under missing neighbors, different tile-arrival order, offline reload, and cluster breakup across zoom levels.
- Preserve distinct park/forest/wilderness designations even when shared visible boundary strokes are consolidated.
- Block unexplained regressions and new unresolved high-risk conflicts; do not claim that an empty queue proves the map error-free.

Existing `audit_conflation.py`, `audit_connectivity.py`, and `audit_roads.py` are useful foundations. They should feed one release report alongside the new published-overlap scanner. Before/after tests alone are insufficient because they can preserve existing errors.

### 5. Scale and regression coverage

First instrument the Tahoe/California preparation pipeline and register all reported locations as permanent fixtures. Then scan every California output tile with neighbor-aware grouping and stable identities, deduplicate the review queue across tile boundaries, and extend detectors to unnamed trails, POIs, and boundary strokes. Re-run against every new source snapshot and publish decision-count changes with releases.

The acceptance target is no unexplained high-risk conflict and no destructive geometry regression, with a measured review queue—not simply fewer visible lines.

## Scope of this change

This review adds an audit tool, candidate evidence, and this proposal. It does not change production matching policies, regenerate tiles, or deploy a new map release.
