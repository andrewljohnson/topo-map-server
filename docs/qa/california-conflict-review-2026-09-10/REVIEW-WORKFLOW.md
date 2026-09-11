# Human source-conflict review

Open `/review` on the public site. The initial queue contains the 51 candidates from this audit, sorted by detected overlap length. Every case freezes the published source fragments, properties, dataset version and deterministic case ID. This is a reviewed-tile fragment comparison, not a complete upstream feature viewer.

## Review

1. Toggle each source to compare its geometry. Fit source fragments for the broader shape; return to the conflict center for the detector location.
2. Open topo context for terrain, neighboring features and labels. The context is the current public map; source comparison stays frozen to r4.
3. Choose same feature/preferred source, distinct features, partial merge, neither, or insufficient evidence. Record confidence and why. Partial decisions should describe the relevant branch/section; they are not executable edits.
4. Save, then move to the next case. Skip reviewed advances past saved cases. Saved judgments can be edited or cleared.
5. Export reviews periodically. State is local to the browser; importing the JSON on another device merges newer timestamps and rejects invalid or mismatched datasets. Import files only from the intended reviewer, since importing is a deliberate merge.

No review writes production tiles or creates an automatic suppression rule. Source geometry attribution is retained. Export contains no credentials.

## Independent comparison protocol

The first human pass does not display an AI recommendation. After a useful sample, an agent should independently review the same frozen case IDs **before reading the human decisions**, using the same action/source/confidence categories and citing evidence. Preserve its predictions separately before comparing.

Compare exact action agreement, preferred-source agreement for matching `prefer` decisions, disagreements by confidence and feature type, and coverage (uncertain cases are abstentions, not successful automation). Review disagreements together. Derive candidate rules from a subset, then evaluate on held-out cases and new geographic regions. Report false removals and lost connectivity separately from retained duplicates; reducing visible lines is not sufficient evidence of correctness.

Use high-confidence agreement as a proposal for a rule, not permission to rewrite tiles. Partial merges and unresolved cases remain human review items until geometry-level evidence and connectivity checks support an implementation.

## Rebuild the frozen evidence

```sh
services/tiles/.venv/bin/python experiments/tahoe/build_review_cases.py \
  --report docs/qa/california-conflict-review-2026-09-10/candidates.json \
  --tiles /tmp/ca-conflict-audit \
  --output apps/web/public/review/candidates.json
```

The tile cache must belong to the report's release. The review JSON includes the matched network features only; matching uses the same normalized-name/agency/class grouping as the audit. It intentionally preserves both sides for review.

## Imagery underlay

At the user's explicit request, the QA page uses Google satellite imagery through `https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}` (256-pixel XYZ tiles, zoom 0–20). This is an undocumented endpoint, not an integration with Google's supported authenticated Map Tiles API; availability and compatibility are not guaranteed. Do not describe it as public-domain or licensed for derivative mapping. The user was informed of Google's licensing restrictions before requesting this change.

The browser fetches imagery directly; no server warming, R2 copies, or app offline downloads are added. The attribution names Google and imagery providers. Dates and resolution vary. The opacity slider and DEM-generated contours remain available; source comparisons and saved review decisions remain unchanged.

## Round 2: input evidence correction

The original review compared post-conflation survivors and could bias source preferences against agency fragments. Round 2 (`pre-conflation-v2`, export schema 2) defaults to inputs before our matching. `candidates-v1.json` retains the earlier geometry; every case's `processedGeometry` is copied unchanged from it. The `Inputs before merging` / `Published output` selector changes selected source lines; pale neighboring paths always represent input context.

- OSM evidence is the pinned 2026-08-11 Protomaps z14 input, obtained via `osm_network` before our conflation. It is **not original OSM ways**. A 6×6 z14 window surrounds each audited z12 tile. A white dashed rectangle shows its bounds. Internal tile cuts remain and must not be treated as surveyed endpoints.
- USFS/NPS/MVUM evidence consists of complete geometries of intersecting records in existing raw cache cells. No final tile clipping or conflation is applied. This is not a fresh agency census. Cache paths and SHA-256 hashes are retained in each case's coverage manifest. The PCTA case uses the checked-in centerline before our matching.
- Selected inputs use published source IDs or normalized matching names and class family. Other intersecting input features appear as pale context, including unnamed and differently named connections. Click a line to inspect its identity and properties. Context outside the input window is clipped.
- All 51 cases were checked for both selected agencies, no missing requested agency cache cells, exact preservation of old published geometry, and asset size limits. Longer input geometries reflect both removed portions and broader input coverage; raw length differences must not be reported as exact amounts removed by conflation.
- No inferred endpoint labels or exact removal reasons are invented. Distinguishing all actual trail endpoints and attributing each removed segment still requires stable upstream OSM identities and the proposed decision ledger.

Round 1 local storage remains untouched and appears in a collapsed previous-decision panel. Round 2 uses a separate storage key and exports `evidenceVersion`, original input IDs and published IDs. It does not count old decisions as new input-based judgments. New exports/imports require matching schema and evidence versions. No decisions modify production tiles.

Rebuild all round-2 evidence with:

```sh
services/tiles/.venv/bin/python experiments/tahoe/build_review_inputs.py
```

Evidence is loaded one case at a time from `/review/evidence-v2/`, so the browser need not download the full statewide review collection to start.

## Precomputed guidance

`recommend_reviews.py` adds a `geometry-dem-v1` suggestion to every evidence case. It never reads human decisions or imagery pixels and never edits map geometry. The dashboard shows the suggestion separately from the user's controls; saved decisions record `guidanceVersion` so these guided reviews cannot later be presented as blind evaluation.

Measurements compare source geometry clipped to the same input window: bilateral corridor coverage at 15/30/50 m, median and p90 nearest-line offset sampled every 25 m, line length, median vertex spacing, turns greater than 135 degrees at 25 m sampling, outlying geometry, and endpoint candidates away from the crop boundary and z14 seams. These are descriptive diagnostics, not accuracy scores or proof of GPS multipath. Overlapping tile fragments and upstream generalization can still influence shape metrics.

The DEM check uses the frozen review release's Terrarium DEM for the central audited z12 tile. Bilinear samples estimate absolute grade over 50 m along mutually nearby sections; the card reports sample counts and p90 grade. No interpolation outside that DEM tile is made. Terrain grade is ground-surface evidence, not surveyed trail grade, route safety, accessibility, or an objective to minimize. Fewer than ten samples is explicitly insufficient. DEM does not decide source priority automatically.

Rules abstain for weak overlap, request segment review for substantial outlying portions/endpoints, and provisionally prefer one representation for near-identical geometry or a strong detail difference without length inflation or reversal warning. Denser coordinates alone do not establish better ground accuracy. Suggestions are low/medium confidence and include their limitations. They are reproducible triage, not 51 independently ground-truthed expert verdicts.

Recompute after rebuilding evidence:

```sh
services/tiles/.venv/bin/python experiments/tahoe/recommend_reviews.py
services/tiles/.venv/bin/python experiments/tahoe/test_recommend_reviews.py
```

Synthetic regressions cover coincident paths, truly separated parallel paths, a unique extension, excessive length, and sharp-turn warnings. Follow-up evaluation must include reviewer disagreement and held-out geography; acceptance of a suggestion does not authorize automatic source removal.
