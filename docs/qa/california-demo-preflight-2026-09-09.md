# r14 California preflight visual QA — 2026-09-09

Read-only CUA inspection of public live map pinned to topo-z12-pilot-20260909-r14. No production changes or source-cache mutations. Viewport 393x852 for phone-oriented density checks; reset after completion. Screenshots viewed through CUA tool output (not saved separately). Browser console captured no warning/error messages in this session. This is browser QA, not proof of native iOS behavior.

## Release-blocking findings

None confirmed in this bounded pass. Initial fresh-area rendering was noticeably progressive: blank background or a rectangular missing area, then base geometry, then labels. All tested areas filled without background/foreground or reload. Exact request latency was not instrumented; do not claim a measured load-time regression.

## Prioritized follow-ups

1. P2, existing unresolved: Cathedral Spur at center [-120.074048,38.89009], z14.46–15.46, bearing7.7 still shows close parallel dashed tracks above the junction. The main Cathedral Trail south of that junction is a single trace in r14. Existing source uncertainty documented in docs/qa/cathedral-2026-09-09/README.md remains valid; endpoint proximity is insufficient evidence to delete the Spur. Obtain independent geometry/topology evidence before loosening matching.

2. P2, newly observed presentation issue: Golden Gate Park center [-122.466,37.7695], z15. Dense internal paths in Japanese Tea Garden/San Francisco Botanical Garden display the same bold red dashed hiking treatment as major walking connections. This produces a dense red scribble and weakens the outdoor hierarchy despite reasonable POI collision handling. Suggest classify urban garden/park pedestrian paths as a lighter, narrower walking class (using surrounding landuse + access/path tags), retaining bold treatment for named through trails. This is a style suggestion, not evidence of duplicate source geometry. Keep mountain paths unaffected; compare z14/15/16 fixtures.

3. P2, performance follow-up: Fresh San Francisco z12 center [-122.45,37.77] initially had a large cream rectangle, then filled on its own. Fresh Desolation z12 center [-120.18,38.94] initially almost entirely flat green, then detailed correctly. Golden Gate z15 geometry appeared before POI/name labels. Instrument first-visible-base, first-label, DEM completion separately on actual iPhones, and check packed tile size/decode latency for dense city parents. Do not interpret this visual observation as proof of missing coverage or old foreground-only loading bug.

4. P3, newly observed label candidate: TRT vicinity [-119.931727,39.325772], z14 shows FR-17N03 label on a purple route segment, while z16 has TRT badges and Tahoe Rim Trail (Relay Peak). Could be legitimate shared route/road designation; verify provenance and establish label precedence for hiking users before changing. Geometry at the original reported duplicate center is now a single main trace with branches retained; no confirmed new duplication.

## Passed observations

- Cathedral main shoreline trail single at reported center (r13 issue improved).
- Fallen Leaf Lake shape-aware label aligned along lake at z12; horizontal at z13 when more room exists.
- Fallen Leaf Campground center [-120.056,38.924] z13/14 shows amenity grid; z15 splits into individual bathroom/parking markers. Center [-120.05,38.929] z16 shows multiple bathroom markers and named campground point. No all-POIs-disappear regression reproduced. Water/info icons from the grid were not individually reconciled across the entire campground in this bounded pass.
- Desolation Wilderness z12 [-120.18,38.94] has Middle Mountain, Dicks Peak, Jacks Peak, named lakes, wilderness label and PCT badge. It is no longer blank at this zoom once loaded.
- TRT original duplicate location z16 [-119.931727,39.325772] visibly continuous single main alignment, badges readable, real branch retained.
- San Francisco z12 [-122.45,37.77] after load has coherent urban road hierarchy, parks and prominent peaks (Lone Mountain, Twin Peaks, Mount Davidson).
- Golden Gate Park z15 has museums, drinking water, information, amenities and collision-managed labels after loading; no errors reported by browser console.

## Recommended California release gate

Do not delay California publication for the nonblocking style suggestions. Once candidate coverage is ready, smoke-test new regions (Yosemite, coast, desert, northern CA) plus these existing Tahoe/SF controls; run real mobile download/offline validation and confirm manifest coverage before cutting distributable app. Keep new findings in separate changes from frozen release inputs.
