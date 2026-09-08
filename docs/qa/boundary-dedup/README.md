# Yosemite east-edge boundary proof — 2026-09-07

User note center: [-119.260788, 37.743606], zoom 12.229378, viewport 393×852.
Compared the actual mobile MapLibre renderer at zooms 10, 12.229378 and 14.
This focused proof keeps the basemap, protected-area fills, boundaries and labels;
DEM and unrelated overlays are omitted to isolate boundary changes. All six
frames settled without a tile timeout or browser error. See [comparison](comparison.jpg).

The exact report contains the Yosemite NP edge, nearly identical Yosemite and
Ansel Adams wilderness edges (0–3 m displacement), and coarser Inyo/Sierra forest
edges. Shared park/wilderness strokes and sustained nearby coarse forest strokes
are suppressed; distinct forest branches remain visible. Original designation
polygons and labels remain available. See the processing thresholds in
[the data-source guide](../../data-sources.md#shared-protected-area-outlines).

Validation: 12 boundary Python tests, 21 mobile download tests, 2 boundary-style
tests and mobile TypeScript pass. A new boundary-revision regression confirms
saved regions retain basemap tiles and refresh only boundaries, including offline
reads after the upgrade. Local services advertise us-agency-boundaries-v2.

The reported tile took 1.99 s on first processing with agency objects already on
disk, and 0.34 s with shared-cell geometry prepared. Rendered tiles are then served
from the server disk cache. This does not measure first-time agency network fetches.
