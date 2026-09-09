# Overnight map refinement — September 9

Window: 06:05–14:05 UTC (8 hours). Starting public release: `topo-z12-pilot-20260909-r5`. Active goal and hourly heartbeat `map-publication-progress` continue this work. Keep working between updates; pause the heartbeat at the deadline and write the morning report. Do not claim tasks complete without their evidence.

## Scope and permissions

Implement all review suggestions and keep identifying evidenced improvements in the existing Tahoe/San Francisco pilot. Commit directly to main and publish tested immutable Cloudflare releases; keep Expo/web behavior aligned. Preserve raw data, personal notes/GPS/downloads and unrelated workloads. No CONUS rollout, new paid compute, destructive cache resets, or invented geographic connections. No subagents currently authorized for this overnight pass. Use 16 workers for pilot production; 32 was slower. Maintain 50 GB free disk reserve.

## Checklist

- [ ] Lake labels: Fallen Leaf missing at z11, Desolation lakes missing at z12, horizontal label returns at z13. Trace upstream availability and thresholds; stable shape-aware anchors, no word stacking, preserve zoom-dependent horizontal fit.
- [ ] Area prominence: Golden Gate Park unnamed amid paths at z12–14; Presidio visitor-center name dominates park. Improve area anchors/ranking/fills using general rules.
- [ ] Roads and paths: campground parking spurs too heavy; agency-style uppercase/repeated road names clutter; urban paths form spaghetti at z12. Context-sensitive detail without hiding remote hiking paths.
- [ ] POI hierarchy: too many urban shops/information icons at z14; prioritize outdoor destinations, entrances, toilets/water and sparse remote features.
- [ ] Land cover/buildings: blocky vegetation patches compete with terrain; city buildings too dark. Soften and simplify by scale while preserving class boundaries and small meaningful features.
- [ ] Loading: coarse fallback lingers before detail. Measure request/decode/render stages for web and Expo, then fix bottlenecks with foreground priority.
- [ ] Trail metadata: Church Peak's unnamed informal OSM spur wrongly receives MT. ROSE PEAK from a different component. Scope names/routes/provenance to matched segments.
- [ ] Connectivity audits: identify gaps introduced by processing separately from original-source gaps. Church Peak ~68 m gap exists in current OSM way 1370986499; do not fabricate a connection.
- [ ] Systematic visual proof at multiple scales, tile edges, bearings and contexts. Keep before/after evidence, delivery/offline checks, regression fixtures, performance comparisons, and a morning summary.

## Reference views

Tahoe overview z11 (38.947,-120.055); Fallen Leaf z13 (38.902,-120.061); campground z16 (38.927,-120.05); Desolation z12 (38.934,-120.158); Golden Gate Park z14 (37.7694,-122.4862), SF z12 (37.77,-122.465). Retest TRT z17.584979 (39.325772,-119.931727), Mt Rose z15.863674 (39.333869,-119.923561), Church Peak z15.505985 (39.349311,-119.922), and repaired boundary views in docs/qa/systematic-conflation.

## Current work

06:05 UTC: goal and hourly continuation configured. Beginning lake-label source/threshold investigation. No overnight code changes published yet.

## Operational notes

Repo `/home/andrew/proj/topo-map-server`; Python `services/tiles/.venv/bin/python`; Node/pnpm via `source scripts/env.sh`. Cloud publication `services/tiles/publish_combined.py publish --release NEW_ID`, then cloud/offline checks before `promote`. Do not alter processing code after freezing an immutable release. Website deploy via `scripts/deploy.sh` (user-selected Cloudflare), mobile bundle via its `bundle:map` script. Existing `/tmp/check-combined-island-r5.mjs` exercises actual TileStore with an in-memory FS and real cloud data; adapt the release ID. Current browser map tab 5, browser 1; CUA bindings may need reinitialization. Browser screenshots can lag or time out; confirm loaded state and avoid treating initial fallback as final rendering.

### 06:40 UTC implementation checkpoint

- Lake importer now retains named water POIs (Dicks, Fontanillis, Velmas), merges identical anchors using the earliest source zoom, and keeps nine decimal places when looking up shape-aware axes. Fallen Leaf angle −69.9°, horizontal transition z13 in real source inspection.
- Trail metadata is deferred until geometric matches are known, then applied only to matched segments. The Church Peak informal spur stays unnamed; its original ~68m gap remains. TRT/Mt Rose report views retain zero unmatched USFS duplicates. Across 640 source tiles, 7,294 OSM feature occurrences are exact and 737 differ only within half-pixel split rounding (maximum .688 tile units); none are missing. `/tmp/overnight-geometry-audit.json`.
- Combined clients had requested an unavailable cloud `/areas.geojson`. New `osm__area` tiles carry reviewed agency anchors and municipal OSM park names; coarse agency fills end at z8. Shared style generator prevents mobile/web drift. Combined clients skip the obsolete GeoJSON request.
- Buildings/land cover softened; access roads get narrower widths and less repetitive labeling than through streets. Visual comparison pending.
- Tests: 108 national source, 33 trail matching, 9 packing, 6 new area-tile, 102 mobile tests; mobile/web typechecks passed before latest styling changes.
- Candidate r6 failed safely on an invalid bundled catalog polygon; never promoted. Added make-valid repair and regression. Candidate r7 is building at `/tmp/topo-publish-r7.log`. Public remains r5. Freeze tile processing code until candidate completes; further processing changes require a new release ID.

### 06:55 UTC first-batch verification

Candidate r7: all 352 cloud objects verified in 115.4 seconds. Real mobile TileStore downloaded two cells (37 unique base/DEM objects) in 3.78 seconds, then restored offline; 1024px DEMs and personal-data fixtures intact. Cloud boundary regression still has 2,722.4m of the continuous Humboldt outline with no basin island. Actual published tiles contain Fallen Leaf/Dicks/Fontanillis/Velma labels and Golden Gate Park's OSM label.

Production-style and development screenshots reviewed at 393×852: Golden Gate Park now named at z12 and z14, Presidio named at z12, buildings softer, fewer competing business labels at z14. Desolation has wilderness name, peaks and PCT. Final lake priority now shows Middle/Upper Velma and Dicks Lake (axis-oriented) that route badges had crowded out. Fontanillis still needs a closer collision/anchor review. Dense urban paths remain visibly excessive at z12; next batch needs a general context-sensitive path hierarchy. Browser first load sometimes takes over a minute despite sub-four-second direct downloads; instrumentation is next. Browser automation itself also has intermittent CDP timeouts, so distinguish these causes.

104 mobile tests passed (including installed MapLibre style validation and native-z12 amenity handoff). Production web build and typechecks passed. Shared style/helper bundles regenerated. No CONUS expansion.

Preview servers: 3002 Vite with cloud API; 3003 static `apps/web/dist/client` build with cloud API. Static preview avoids HMR resets. Stop only these added preview servers at end; preserve original 3000/3001/3012/8081. Browser proof tab 12; temporary viewport override393×852 must reset before finishing.

### 07:15 UTC second batch in progress

Public r7 and matching website main commit `5e3164d` are deployed (Cloudflare version9a25f0a1). Urban path context + readable display names are uncommitted for next candidate. `path_context.py` uses fixed z12 through streets, a500m neighborhood and4km street threshold; walking path geometry never changes. Context applies to individual MultiLine components, conservatively retaining rural presentation if any sampled point is outside the dense grid. Display names retain source names and route codes separately.

Exact context candidate r8 verified352 objects in160.9s but was not promoted. Its source stage increased from12.5s(r7) to53.8s. A standalone network unit fixture lacked surrounding-road bytes; fixed and108 national tests pass. Candidate r9 now building after optimizing context into sampled street-length grids with scipy convolution and a sparse-network upper-bound fast path. Grid comparison across8 places: same rural classifications; urban differing lengths73/76,144 and86/86,556 tile units (<0.1%). Prototype city lookup materially faster. `/tmp/overnight-grid-comparison.json`, `/tmp/topo-publish-r9.log`. Do not change tile-processing inputs until candidate completes; immutable fingerprint includes Python tests as well as processor code.

Client style: urban local walking paths fade in z12–14, route layers keep their normal styles; z14 all geometry remains visible. Major area labels must come after water names so Blue Heron Lake does not suppress Golden Gate Park. Some dense red paths remain immediately around that lake; inspect before further changes (could be threshold/classification or another source). 104 mobile tests passed before final area-priority adjustment; rerun after final bundle.

Loading investigation: opt-in local `apps/web/app/mapDiagnostics.ts`, enabled only with VITE_MAP_DIAGNOSTICS=1 and `?diagnostics=1`, displays bootstrap/source/tile/request timings. Preview static build3003 uses cloud API. First observed load~94s despite metadata130ms and main-thread DEMfetch<1s. Map constructor~6.8s, first source events43s, firstbase tile53s, DEMfetch starts82s, max timer gap43s. Must determine renderer work vs background-IAB throttling; long-task and visibility instrumentation has just been built and needs reload/observation. Worker resource startTime uses a different time origin: do not compare worker start values directly to window timestamps. Duration remains useful. All diagnostic changes are uncommitted and absent from normal cloud UI.

### 07:51 UTC second-batch verification

Candidate r10 is fully uploaded and verified (352 objects,116.49s). r8/r9 were superseded without promotion. Classification now runs after trail matching so it cannot split reference geometry before conflation. Real cloud mobile TileStore check:37 unique tiles,3.06s,two offline regions,1024px DEMs,notes/GPS fixtures preserved. Reported TRT/Mt Rose views contain only the retained OSM network; no USFS duplicate. Forest island remains absent with2722.4m continuous outline. Candidate still unpromoted pending final visual review.

Lazy icon generation and CPU-backed icon canvases removed a large startup stall in IAB: first base tiles improved from53–76s to10.8–13.8s;11 requested icons took0–2ms total. A remaining~30s stall is **graphics shader compilation/status synchronization**, not tile serving: opt-in wrappers measured28 slow getShaderParameter calls totaling25.4s and9 getProgramParameter calls totaling8.0s. Main DEM requests were1–1.8s. Worker PNG decoding is now off the main thread where OffscreenCanvas/createImageBitmap are supported, with a compatibility fallback; this did not solve the browser-specific shader pause. Never infer physical Expo timings from IAB.107 mobile tests pass, including encoded/decoded DEM contour equivalence, bitmap cleanup, raw buffer transfer/cache preservation and unified lake-priority behavior. Both typechecks/static build pass.

SF z12 visual review: Golden Gate Park/Presidio and major hills visible; paths quieter, some fine red paths near Blue Heron Lake remain. Desolation z12: peaks/passes,Middle/Upper Velma,Dicks labels present. Separate angled/horizontal symbol-layer priority was a systematic weakness, but unifying it did not restore Fontanillis in the z12 view. Its source candidate is present and not placed; continue anchor/collision diagnosis. Candidate style now uses one lake collision queue and a tenth-zoom rotation step, preserving source fit thresholds and single-line text; visual verification in progress. NLCD runtime opacity no longer overrides the softened style.

### 08:15 UTC junction audit and third candidate

Public r10/client commit0cdca73 deployed,Cloudflare version946315f6. New whole-area audit checks junctions before tile clipping/quantization, excludes route-badge-only geometry and halo endpoints, and separates source dead ends from new cuts. Corrected an initial audit-harness closure accumulation error before accepting measurements. Valid baseline:3571 agency endpoint observations,289 original dead ends,134 source-connected endpoint warnings,2 newly disconnected cut ends. Source-backed reconnection reduced134→6; original289 dead ends unchanged. Connections preserve the original agency branch and only extend to the established replacement of a source-connected segment, within its existing matching tolerance; OSM geometry and grade-separated/unknown gaps unchanged.

The2 cut-end cases (TRT and Capital to Tahoe) were tiny survey excursions whose two newly cut ends snapped to the same reference point, creating artificial17–50m spikes from1–10m source fragments. Those short collapsed excursions now disappear; actual source endpoints and loops remain.38 matching tests pass, including real source fixtures, preserved raw geometry, order independence, grade separation and original-gap preservation. Candidate r11 now building. Freeze processing inputs until completion/promotion. Six remaining source-junction warnings intentionally remain pending evidence review (largest Ellis Peak~82m).

Smaller lake names at z12 now allow Fontanillis, but Dicks then loses its collision slot. Trial modest center/top/bottom label alternatives are under visual review; no overlap forced and no label coordinates moved. R10 style stays live until the new style is verified.

### 08:25 UTC third batch promoted

r11 verified352 objects in128.15s,about12s more than r10 for source-junction protection. Mobile cloud/offline two-cell test3.83s,37 tiles; notes/GPS intact. All640 OSM geometry checks still pass with the same bounded split rounding.109 national,38 matching,108 mobile tests and both typechecks passed. Visual proof: TRT atz17.58 is one trail; Church Peak retains its original gap; Fallen Leaf campgroundz16 has separated restroom POIs and restrained access-road spurs. Small lake text plus limited center/top/bottom placement now renders Fontanillis,Dicks,all three Velmas together atz12 without forced overlap. Candidate r11 promoted; matching client commit/deploy follows.

Next: inspect the six remaining source-junction warnings, reduce coarse NLCD grid prominence at very close zoom, continue varied view/zoom proofing. Keep working until14:05 UTC. No national expansion or paid compute.
