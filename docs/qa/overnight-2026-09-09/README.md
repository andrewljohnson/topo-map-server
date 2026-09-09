# Overnight visual and data proof

Actual MapLibre canvas renders at393×852 CSS pixels. Adjacent JSON records camera,bounds,immutable tile release,time and style SHA256. These are browser map renders,not physical-iPhone screenshots. Full [data sources and licences](../../data-sources.md) accompany the attribution footer.

| View | Evidence | Finding |
|---|---|---|
| Desolationz12 | [Map](desolation-z12.png) | Fontanillis,Dicks and all three Velmas coexist with peaks and wilderness name. |
| Desolationz13 | [Map](desolation-z13.png) | Phipps Peak appears at the next zoom;z12 omission is collision placement. |
| Campgroundz17 | [Map](fallen-leaf-campground-z17.png) | Separated restrooms,restrained access roads/cover. |
| SFz12 | [Map](san-francisco-z12.png) | Golden Gate Park,Presidio and hills survive city density. |
| Tahoez10 | [Before](tahoe-overview-before.png),[after](tahoe-overview-after.png) | Clearer major-water typography with shape-fit preserved. |
| Lakes,bearing150° | [Before](rotated-lakes-before.png),[after](rotated-lakes-after.png) | Upright names along unchanged lake axes. |
| Golden Gate Bridge,z14,pitch35° | [Before](golden-gate-bridge-before.png),[after](golden-gate-bridge-after.png) | Highway decks above water;identical source geometry. |

Strict connectivity reports `junctions-distinct-before.json`/`junctions-distinct-after.json`:127 lost-source-junction endpoint observations and2 new-cut observations become0;289 source dead ends and7 duplicate termini remain. Older broad-audit reports use a different classification;do not combine counts. `r12-osm-geometry.json` checks640 Tahoe source tiles. Cloud/offline timings use real TileStore code with an in-memory filesystem and cloud data,not native-phone benchmarks.

SF strict connectivity proof: [before](sf-junctions-before.json) and [after](sf-junctions-after.json) cover 640 source tiles. Lost source-junction endpoint warnings fall from 37 to zero and new-cut warnings from three to zero; 135 source dead ends and nine duplicate termini remain.

[Mount Rose trail](mt-rose-trail-z15.png) confirms one rendered trail at the reported close-zoom location. [Packing equivalence](fast-pack-equivalence.json) records 80 byte-identical parent tiles with faster ring preparation; timings are local retained-input measurements.

## Additional local verification

- [Full pipeline comparison](full-pipeline-packing-equivalence.json): 220 byte-identical outputs, about 6% faster averaged full cutting time in reversed-order repeats. This excludes overviews and publication.
- [Measured packing CPU](packing-cpu-equivalence.json): 80 byte-identical parents, 18.1% less packing CPU. The earlier `fast-pack-equivalence.json` labels summed task elapsed time as CPU; use this newer report for actual CPU measurements. Reproduce with `experiments/tahoe/benchmark_packing.py`.
- [Real contour seams](real-contour-seams.json): 950 exactly aligned crossings across 24 pairs at z12–15, using actual 1024px DEMs and the bundled device worker. Reproduce with `experiments/tahoe/audit_contour_seams.mjs`.
- [Church Peak after overzoom](church-peak-after-overzoom.png): label remains visible after starting at z12, with the original informal trail unchanged.
- [Late-detail source audit](late-detail-source-audit.json): no supported features were discarded by the finest-level zoom guard in 1,280 pilot source tiles.

These are desktop/local measurements and browser map renders. Physical Expo/background/lock-screen acceptance remains separate. The latest client changes await public publication approval; the live release still uses r12 data and client186b4d3.

## Late-morning interaction and scale checks

- [Golden Gate Park z15](golden-gate-park-z15.png), [view and rendered-symbol metadata](golden-gate-park-z15.json): actual browser map render after POI indexing; exported canvas does not include app controls.
- [POI matching equivalence](poi-matching-equivalence.json): nine actual z12 parents per SF/Tahoe fixture, six zooms, three repeats. All hidden-marker filters, sort expressions, merged detail records and matching statistics exactly equal the previous matcher. Median Node refresh CPU: SF1070.8→56.3ms; Tahoe26.7→4.1ms. These are not physical-phone timings. Reproduce with `experiments/tahoe/benchmark_poi_matching.mjs`.
- [Current Sierra worker comparison](sierra-current-worker-comparison.json):400 base parents plus484 DEMs,58/69/58seconds at16/8/16workers;884 byte-identical outputs. Sources retained; zero missing native DEM chunks. This is not cold nationwide throughput.

## Wider source-junction review

[Before](sierra-junctions-before.json) and [after](sierra-junctions-after.json) cover6400 source tiles. Six source-connected gaps and one false collapsed spur are repaired; all3373 original source dead-end observations remain. Three warnings remain for duplicate surveys at the same physical dead end, with matching source records attached. Counts are endpoint observations, not unique physical junctions.

[Geometry review](sierra-junction-review.png):blue is the original subject,green its original source partner,thin black the retained pre-repair result,red the flagged point;10m grid. These are local ground-metre source plots, not map screenshots. Source data:OpenStreetMap contributors,USFS and MVUM. Squirrel Mine,Gibson and Chapman remain unchanged after review.

The new local pilot passes [all1280 source-tile geometry checks](junction-v12-pilot-geometry.json):44,703 OSM feature occurrences exactly unchanged,27 designation polygons and22 nonforest outlines unchanged. [217 of220 physical files match](junction-v12-pilot-equivalence.json); the three base differences remove small collapsed terminal remnants on Cathedral Spur,Middle Meadow Loop and Campground Spur H. The public r12 data remains unchanged while publication approval is pending.43 matching and109 national-source tests pass.

## Source-tagged sign priority

[Before](golden-gate-park-z15.png) and [after](sign-priority-park-z15.png) use the same Golden Gate Parkz15 camera. Actual OSM guidepost tags defer small signs:general guidepostsz16,anonymous bicycle-guideposts and route markersz17. Ordinary maps and boards retain their previous priority. [z16](guidepost-z16.png) and [z17](guidepost-z17.png) show the selected bicycle guidepost returning at its original coordinate; exported rendered-symbol ID5381225690370605 is absent at16 and present at17. [Fallen Leafz15](sign-priority-campground-z15.png) verifies that grouped facilities still split normally.

[All29,438 amenity occurrences](sign-priority-geometry-equivalence.json) preserve coordinates,IDs,group membership and all other properties across1280 fine tiles. Only information_type/detail_minzoom are added;228 sign occurrences receive priority metadata. Source amenity revision3 reuses retained raw extracts. Both clients pass125 tests;7 source grouping/bundling tests and both typechecks pass.

`proof_server.py --tiles <local-combined-root> --metadata <compatible-public-metadata.json> --candidate-id <unique-id>` optionally serves a z12-only local candidate, including gzip MVTs and1024 DEMs, without uploading it. The server remains bound to127.0.0.1. Three candidate flags are required together; routes are restricted to the selected base/DEM XYZ paths. HTTP metadata/encoding/dimensions and invalid-path checks pass.

To reproduce the earlier POI speed comparison after later intentional visibility changes, pass `--baseline-ref c84402e --candidate-ref 1e9e224` to `benchmark_poi_matching.mjs`. Both local Git revisions are pinned; matching source hashes are recorded.

## Bounded source and client caches

- [Working-source equivalence](working-cache-equivalence.json): the retained-input pilot takes 52.8 seconds and all 220 base/DEM files match. No real source misses occurred in that run; eight dedicated tests exercise source miss routing, canonical preservation, disposable cleanup and cross-process range locking. Eight simultaneous cold range readers fetch once instead of eight times.
- [POI style-snapshot equivalence](poi-style-snapshot-equivalence.json): the matcher reads one coherent style snapshot per refresh, down from 33 in the Tahoe fixture. All 12 actual-tile/zoom outputs match. This avoids repeated MapLibre style serialization; the fake-map benchmark does not measure that browser CPU saving.
- Terrain memory [before](terrain-memory-before.json) / [after](terrain-memory-after.json): 48 synthetic, nonoverlapping z12 views through the actual bundled worker. At the end, worker external memory drops from 919 to 107 MiB and remains bounded. This is a Node/GC memory probe with transferred 1024px DEMs, not an iPhone measurement.
- [Post-patch real contour seams](real-contour-seams-after-cache.json): all 950 crossings across 24 pairs still match exactly. Three actual-worker contour tests and five cache lifecycle regressions pass; each new lifecycle regression fails against the original dependency.

The pinned `maplibre-contour` patch releases settled abort listeners, prevents stale cancellation/failure from evicting a replacement entry, and avoids starting work for already-cancelled callers. Both clients embed the same patched ESM worker. Full mobile suite: 131 tests; both typechecks and static web build pass. Public deployment approval remains pending.

[Campground after the terrain-cache fix](terrain-cache-campground-z15.png) confirms detailed contours and separated facilities in the rebuilt shared client.
