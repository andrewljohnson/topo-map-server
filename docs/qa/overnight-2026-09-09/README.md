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
