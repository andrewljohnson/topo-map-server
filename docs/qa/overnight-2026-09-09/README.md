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
