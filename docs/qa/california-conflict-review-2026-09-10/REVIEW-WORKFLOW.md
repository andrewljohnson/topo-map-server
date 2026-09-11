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
