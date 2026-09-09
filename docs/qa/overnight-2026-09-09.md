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
