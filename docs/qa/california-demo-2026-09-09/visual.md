# California r1 visual release gate — 2026-09-10

Candidate: `topo-california-20260909-r1`, public website with explicit `?release=topo-california-20260909-r1` (not promoted during this inspection).

Read-only CUA browser pass after publisher completion. All screenshots were actually viewed via CUA at the normal 1280×720 browser viewport. An initial phone viewport preparation did not persist through subagent tab creation; do not claim mobile-size/native visual proof. No production mutations. Screenshots are in tool outputs, not saved files. Browser warning/error log returned empty after regional inspections.

## Result

No release-blocking rendering/coverage problem found in these representative views. All eight regions rendered detailed roads/trails/land features and DEM-derived contours/shading without persistent missing squares. San Diego geometry preceded labels; labels and amenity icons appeared on their own at a follow-up screenshot without reload or background/foreground. This is a bounded visual smoke test, not exhaustive statewide geometry correctness or measured load-time proof.

| Region | Center longitude, latitude | Zoom | Observed |
|---|---|---:|---|
| Yosemite Valley | -119.59, 37.745 | 14 | Detailed canyon relief, feet contours, Merced River, waterfalls, trails, camps and amenities; continuous full viewport. |
| San Francisco/Golden Gate Park | -122.466, 37.7695 | 14 | Buildings, local road names, parks, lake labels and amenities, terrain; continuous full viewport. Known garden path clutter remains. |
| Los Angeles/Griffith Park | -118.303, 34.119 | 14 | Observatory, trail network, peaks, dense contours and residential roads/buildings; full viewport. New POI clutter finding below. |
| San Diego/Balboa Park | -117.145, 32.734 | 14 | Buildings, paths, roads, terrain, park/museum labels and amenity icons after settling. |
| Mount Shasta southern slopes | -122.2, 41.38 | 13 | Detailed volcanic relief, named drainage, peaks, trails and Old Ski Bowl trailhead. |
| North coast/Prairie Creek Redwoods | -124.024, 41.365 | 14 | Detailed forest relief, creeks, trails, campground amenities, scenic parkway and highway. |
| Joshua Tree/Hidden Valley | -116.166, 34.013 | 14 | Detailed rock relief/contours, trail network, campground amenity cluster, parking and roads. |
| Tahoe/Fallen Leaf Campground | -120.056, 38.924 | 14 | Lake shoreline, relief, trails, campground roads and six-symbol amenity grid. |
| Central California overview | -119.5, 37.25 | 7 | Cities/roads, named national parks/forests/wildernesses, land cover and state boundary; no persistent blank tiles. |

## Separate nonblocking cartography follow-ups

1. **P2 — residential swimming POI overload in Los Angeles.** At Griffith Park view, residential hills west/south/east are blanketed by swimming icons, apparently backyard pools. This overwhelms useful outdoor amenities. Verify OSM access/residential context and suppress private pools or rank them far lower; preserve public swimming areas. This is a visual suspicion about pool access, not a proven source-tag classification.
2. **P2 — garden/zoo path hierarchy.** Golden Gate Park and Balboa Park garden/zoo areas show dense bold red dashed path meshes. Lighter urban pedestrian path styling would improve hierarchy; do not blanket-change mountain hiking trails.
3. Prior uncertainty about Cathedral Spur source duplication remains outside this bounded statewide pass; no unsupported geometry deletion recommended.

No native Expo/iOS, offline/download, exhaustive grid coverage, or mobile performance pass is claimed here. Root agent owns those separate release gates. Temporary viewport override reset at end.
