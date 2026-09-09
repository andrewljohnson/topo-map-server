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

### 09:15 UTC fourth batch promoted

r12 verified352 cloud objects in129.68s. Strict source-branch audit:3571 endpoint observations,289 source dead ends and7 duplicate termini preserved;127 lost-source-junction endpoint warnings and2 new disconnected cuts reduced to0. These are endpoint observations, not127 unique physical junctions. All640 OSM geometry checks unchanged.41 matching,109 national and109 mobile tests passed before final style-only peak anchor adjustment. Real cloud TileStore37-tile/two-cell offline test4.04s;1024px DEMs and personal-data fixtures intact. r12 promoted; matching client commit/deploy pending.

Durable phone-sized map renders now saved through a localhost-only proof server, with bounds/release/time/style SHA256 and attribution footer. `experiments/tahoe/proof_server.py` serves port3004; stop it with3002/3003 at deadline. The exporter is gated out of normal production builds. Desolationz12 shows all five named lakes; Phipps Peak is a normal collision omission atz12 (candidate and final filter verified), then appears atz13. No new one-off coordinate change. NLCD fade now remains canonical with and without DEM setup; close-zoom cover is quieter. Public access button waits for access metadata rather than flashing a login control on the public map.

### 09:42 UTC client reliability and rotated proofing

Public r12/client186b4d3 deployed,Cloudflare97cc0ca7. New uncommitted client batch: saved-region migration now recognizes compatible combined-base revisions with unchanged coverage/format, preserving selections and refreshing both physical tilesets. A regression failed before the fix and passes after; old files remain intact and refreshed maps reopen offline.

A separate native cancellation regression reproduced a promoted visible tile waiting indefinitely when iOS downloadAsync/cancelAsync promises never settle. Native batch waiting now uses the same independently abortable wrapper as fetch; late envelopes are removed and cannot overwrite canonical cache.35 queue/native tests pass. These are simulated native failure conditions, not an observed physical-phone timing measurement.

Major-water names now use stronger typography while reconstructing the importer’s font-fit capacity for orientation. Rotated phone-sized proof exposed upside-down point labels; shared lake-orientation handling flips them at rotateend and restores the original expression north-up, without changing coordinates or relayout during dragging. Bearing/zoom/style-replacement tests and visual before/after proof pass. One redundant owned DEM buffer copy removed; transfer/cache integrity tests pass. Final batch suite/typechecks/deploy pending.

### 10:05 UTC fifth client batch verified

117 mobile tests, both typechecks and static web build pass. Golden Gate Bridge proof exposed highway decks beneath water: the first non-contour symbol can belong to a coarse overview or regional contour group before detailed water/roads. Decks now insert after road geometry. Regional/non-regional regression and identical-camera before/after proof pass.

Legend review found feature-dependent local-road widths becoming NaN, so white fill obscured its casing. Legend paint now evaluates feature properties; all current line/fill expressions are compared against MapLibre across classes, surfaces, tunnel flags and zooms. The drawer visibly restores local-road casing and aligned column headings.

Batch includes compatible combined-release selection preservation, independently abortable native downloads with late-file cleanup, stronger major-water typography, upright rotated lake names, and removal of one redundant DEM copy. Automatic review requested verified GitHub ownership and a secret scan before commit/push: authenticated account and repository owner are bothandrewljohnson,main is the default branch,push/admin permissions confirmed. Secret scan/publication follow. Data remains r12. Continue until14:05 UTC.

### 10:10 UTC publication approval pending — continue local work

Local main commit6706795 contains the fifth client batch; it is NOT pushed or deployed. Public main remains186b4d3,Cloudflare97cc0ca7,r12 tiles. Automatic review rejected the public push twice,including after gh verified authenticated user/ownerandrewljohnson with push/admin permissions and Gitleaks scanned all38 changed/new files with zero findings. The second rejection said that evidence was insufficiently trusted. Do not bypass or retry public publication until the user answers the pending async approval question. Local work/commits are permitted and continue. This does not block map QA or local candidates.

Pending question: “Approve publishing the verified overnight client changes and map-proof images to your public topo-map-server GitHub repo on main, then deploying the website?” No response yet. Secret scan evidence:/tmp/topo-overnight-secret-scan.json (empty findings),file manifest:/tmp/topo-overnight-publication-files.json.

SF640-source-tile connectivity audit is running locally:/tmp/overnight-sf-junctions-current.log/json; parents:/tmp/topo-sf-parents.json. No nationwide expansion.

### 10:35 UTC local packing optimization and wider connectivity proof

The strict SF audit now completes: 640 source tiles, 1,300 output endpoint observations, 135 original source dead ends and nine duplicate termini; zero lost-source-junction or new-cut warnings. The same R10 baseline has 37 and three warnings respectively. Original source gaps remain unchanged. Reports are saved alongside Tahoe evidence.

A local packing prototype replaces Python polygon-ring reconstruction with equivalent NumPy rounding and GEOS orientation. All 80 Tahoe/SF parents are byte-identical to the previous encoder; summed packing-task elapsed time fell from 121.1 to 101.9 seconds across parallel tasks (about 16%). The first complete-pipeline pair was 55.5 versus 50.5 seconds, packing wall time 11.7 versus 9.9 seconds. Reverse-order repeats are underway to separate source timing noise. Ten packing tests pass, including half-integer rounding, reversed rings, holes, tiny collapsed polygons and multipart geometry. Existing immutable releases remain unchanged; publication approval is still pending.

Alternative compression levels and dropping unused waterline payload were measured but not adopted: gzip level 6 saves only about one CPU second across 83 tiles at a small byte penalty; raw waterline removal saves 0–2.5% in three samples. Original road layers remain for overview/zoom-transition compatibility.

### 11:05 UTC local verification checkpoint

All new work remains local: public r12/client186b4d3 is unchanged; public push approval remains pending. Local6706795 plus the uncommitted sixth batch are ready for further review, not published.

Packing repeat: baseline full runs55.475/53.529s; optimized50.539/51.876s (about6% average improvement). Packing wall time11.723/11.266s becomes9.948/9.694s. All220 outputs (80 base,140 DEM) are byte-identical. The reproducible paired packing benchmark separately measures actual CPU:125.352s before,102.636s after (18.1% less), all80 parent bytes identical. This is retained-input local cutting, not a cloud-publication or cold-CONUS timing. `experiments/tahoe/benchmark_packing.py` saves the exact comparison.

New terrain-worker recovery restarts once after a fatal worker error and replays still-needed contour jobs. A second failure settles requests without a restart loop; retired replies and reused DEM request IDs cannot contaminate the replacement. Cancellation and failed replay are covered. Handled errors prevent default reporting.121 mobile tests, both typechecks, and static build pass.

Actual local production DEMs were audited using the bundled device contour worker:24 pairs across six Tahoe/SF parent boundaries,zooms12–15,both seam directions.950 contour crossings matched exactly (zero MVT-unit error),using50 DEMs. Reproducible script:`experiments/tahoe/audit_contour_seams.mjs`; timings include audit transport and are not phone measurements.

A suspected native-zoom label issue was NOT confirmed: installed MapLibre sets reparseOverscaled=true and supplies overscaledZ to workers. Church Peak renders both on a close-zoom load and after loading the same area atz12 then zooming to15.5. No workaround added. All1,280 raw source tiles also contain zero supported features excluded by the min_zoom>15 guard. Corrected an inaccurate old code comment. A single TRT collision box confirms the apparent stacked badge was its internal rule, not duplicate route geometry.

Root/mobile documentation now explains the current two-dataset pilot, cloud-default Expo and development cache reset, native background scheduling, source preservation and immutable releases. Removed obsolete instructions claiming precomputed contour downloads, fixed tile counts, removed Explore Areas UI, and no background service. Internal documentation links pass. Continue substantive local work until14:05 UTC.

### 11:35 UTC landscape and scale verification

Local main8003b1f now contains packing, terrain-worker recovery, seam proofs and documentation updates. Public push/deploy approval remains pending. New layout fixes are local: web maps no longer force a420px minimum in393px landscape viewports; scoped SDK overrides retain44px controls even when MapLibre CSS loads later. Portrait393×852 and landscape852×393 DOM checks show no page overflow and16px bottom margins. Web app controls are hidden while either modal drawer is open; native DownloadStatus now also hides/closes its expanded panel when the legend opens. Native TypeScript passes. The actual mobile map HTML was visually reviewed with simulated portrait/landscape safe insets through a browser transport harness; this is not physical iPhone or React Native overlay verification.

A current400-parent Sierra rerun finished in57.901s at16 workers, using484 DEMs with zero missing native DEM chunks. An8-worker repeat took69.097s and all884 base/DEM outputs match. A second16-worker run is underway. These are retained-source local cuts, excluding overview/upload phases; they cannot establish cold nationwide completion time. Scratch is separate and raw sources/live releases remain intact.

### 11:52 UTC dense-city interaction improvement

Indexed POI matching replaces whole-list scans with candidate buckets while the original matching rules, distance/ambiguity checks, ordering and source records remain authoritative. Twelve real-tile/zoom comparisons give exactly identical full filters, layout expressions, merged details and statistics. Median Node CPU per refresh falls1070.8→56.3ms for a dense nine-parent SF fixture and26.7→4.1ms for Tahoe.123 mobile tests and both typechecks/static build pass; new cases cover canonical records gaining IDs and conflicting GNIS records. Golden Gate Parkz15 visual proof is saved. These are client matching CPU measurements, not physical-phone frame times.

Sierra16/8/16 runs complete57.901/69.097/57.953s;884 identical outputs. Wider6400-source-tile connectivity audit found9 source-junction warnings plus1 new cut. Geometry review confirms3 duplicate-survey dead ends. An isolated, uncommitted `/tmp/topo-trail-retained-junction-candidate.py` connects only proven partners within existing tolerances and removes an exactly collapsed short out-and-back:6 real gaps and1 false spur resolved;3373 original source dead ends unchanged,3 reviewed duplicate warnings remain. Production matcher is not yet edited; tests and actual local candidate generation follow. No public publication while approval remains pending.

### 12:03 UTC wider junction fixes verified locally

Local production matcher now includes proven retained-partner reconnection near a trimmed mask and removal of exactly retraced short three-vertex excursions with two cut endpoints. Derived trail revision12; raw cache version remains1.43 matching tests pass, including two new real-source regressions that failed before.109 national-source tests pass after isolating two existing Overpass fallback tests from this machine’s real bulk-OSM index.

Sierra6400-source audit:39,576 agency endpoint observations,3373 original source dead ends,305 previously classified duplicate termini,3 review warnings; zero disconnected new cuts. Six real gaps and one collapsed false spur resolved. Three residual warnings are visually confirmed duplicate surveys ending on the same retained line (Squirrel Mine,Gibson,Chapman); source records explicitly identify the merged partner. Audit keeps them visible for review.

Local pilot candidate`services/tiles/data/publication/combined/overnight-junction-v12` built in50.917s. All44,703 OSM occurrences across1280 fine tiles are exactly unchanged;27 designation polygons and22 nonforest outlines unchanged.217/220 files identical;three base changes remove small collapsed terminal remnants on Cathedral Spur,Middle Meadow Loop and Campground Spur H. No new public data or client publication while approval remains pending. Current local client1e9e224 has the POI-index speedup. Next:source-tag-based sign priority and continued visual/reliability checks until14:05 UTC.

### 12:21 UTC sign priority and unpublished-candidate proofing

Source amenity revision3 retains information subtypes and gives standalone direction signs close-zoom priority. General guidepostsz16;unnamed bicycle-guideposts/route markersz17. Ordinary boards/maps unchanged;clustered members stillsplitatz15. Fixed agency/OSM visibility handoff so a counterpart is not hidden before the actual replacement layer becomes eligible.125 mobile tests,7 amenity source/bundling tests,both typechecks/static build pass. Refreshed retained-source bundled data and fixed embed-amenities.py’s stale whitespace assumption.

All29,438 amenity occurrences across1280 fine tiles match exactly apart from the2 new priority properties;coordinates,IDs andgroup membership unchanged. Actual browser proofs atsameGoldenGateParkz15camera show lesssignclutter;selectedguidepostID5381225690370605 absentz16,presentz17atitsoriginalcoordinate.FallenLeafz15bathrooms/membersremainvisible. Localcandidate`overnight-sign-priority`built62.326s,includingsource-cellreprocessing13.257s.

Newoptionalcandidate mode inproof_server.py serves only selectedlocalbase/DEMXYZfilesplusadaptedpublicmetadata,z12only,Cache-Control:no-store,gzipmetadata,and127.0.0.1binding. Metadata,1024DEMs,MVTdecode,andfiveinvalidroutechecks passed. Additionalownpreviewserveron3005,currentexecsession23261(log/tmp/topo-candidate-proof-server.log);stopitatthe14:05deadlinealongwith3002/3003/3004. CurrentIABtab12ishttp://localhost:3005/?proof=1#15/38.927/-120.05,portrait393×852. StaticwebbuildnowusesoriginAPI;3004doesnothavecandidatemetadata,so use3005forfurtherreloads.3000/originalExpo/servicesunchanged.

Publicpush/deployapprovalstillpending.Allnewchangesremainlocal.Next:reviewnew-sourceworking-cachegrowth(PMTilesrangesandagencysourcewindowscurrentlyescapeper-shardspool)andboundedlocalverification.NoCONUSrolloutorpaidcompute.Continueuntil14:05 UTC.


### 12:52 UTC bounded source acquisition and terrain memory

Newly acquired PMTiles ranges, agency JSON, amenity cells and stream tags now use the explicitly disposable per-shard scratch directory. Canonical existing inputs always win and remain intact. Overview child processes receive their own scratch root without changing the parent environment. Eight spawned cold range readers previously made eight fetches; a cross-process file lock reduces that to one. Eight cache tests, 109 national tests and three publication tests pass. A warm 52.807-second pilot has all 220 files byte-identical; actual misses were absent, so cold routing is proven by fixtures rather than claimed as a national measurement.

POI refresh now takes one style snapshot instead of 33 in the Tahoe fixture. All 12 real-tile/zoom output comparisons remain exact; browser style-serialization CPU is not measured by the fake-map benchmark.

A long-pan audit of the actual bundled contour worker confirmed retained abort listeners holding older 1024px DEMs: after 48 disjoint views, worker external memory reached 919 MiB. A pinned maplibre-contour ESM/CJS/source patch removes listeners on settlement and guards stale request deletion by entry identity. The same probe now levels at 107 MiB (about 88% lower). Five lifecycle regressions fail before and pass after, including late cancellation/rejection of an evicted request and pre-aborted consumers. All 131 mobile tests, both typechecks and static web build pass. Real DEM seam audit still matches 950 crossings exactly across 24 pairs; browser campground view renders detailed terrain and separated facilities. These are not physical-phone benchmarks.

New source-cache, style-snapshot and terrain patch changes are still uncommitted at this checkpoint. Public main remains 186b4d3/r12 and public approval remains pending. Continue local improvement until 14:05 UTC; next hourly summary around 13:05. Preserve original services and user data.
