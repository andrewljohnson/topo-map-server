# Overnight map work — September 9

**Approved publication follow-up:** the user approved the push and deployment.
Commit `89c0260` is deployed (Cloudflare version
`db095d7d-4978-4253-81a7-8c3cbbaa4ce9`); `topo-z12-pilot-20260909-r13`
is now promoted. All 352 objects were read-back verified in 148.4 seconds.
The actual mobile TileStore downloaded 37 unique tiles for Tahoe/SF in 10.94
seconds and reopened them offline with personal-data fixtures intact. Expo was
restarted on LAN port 8081, signed in, and its iOS manifest and bundle returned
200. Browser verification shows terrain, lake labels and PCT styling on r13.
No native production build was requested or cut. The report below preserves the
earlier overnight state and its session-gap disclosure.

## What you can use now

The [live map](https://topo-map.andrewljohnson.workers.dev/) serves
`topo-z12-pilot-20260909-r12`, with public client commit `186b4d3`.
It includes the earlier overnight lake/park label, road hierarchy, land-cover
and source-junction improvements. Coverage is still Tahoe/San Francisco detail
plus the pilot overview. It is not a nationwide warm.

Additional verified changes are committed locally but **not pushed or deployed**.
Automatic publication review rejected the public GitHub push even after ownership
verification and a clean secret scan. The pending user approval is the remaining
publication gate. No production iPhone build was cut in this overnight pass.

## Main improvements

- Lake labels share collision priority, retain single-line shape-aware placement,
  become horizontal when they fit, and remain upright after rotation. Desolation
  shows Fontanillis, Dicks and all three Velmas together at z12.
- Parks and forests have clearer labels and fills. Urban paths, information signs,
  campground access spurs, buildings and land cover compete less with terrain.
  Source-tagged guideposts wait for closer zooms; campground members still split.
- Trail metadata stays on matched segments. Source-connected junctions are
  preserved systematically; genuine source gaps, including Church Peak, remain.
- Golden Gate Bridge road decks render above water. Legend casings match actual
  feature paint. Landscape/safe-area controls and modal overlays were checked.
- Dense-city POI matching is indexed: the actual SF fixture falls from roughly
  1,071 to 56 ms per refresh in Node with identical outputs. One style snapshot
  replaces repeated serialization. These are not physical-phone frame times.
- Contour-worker external memory levels around 107 MiB instead of 919 MiB after
  48 disjoint synthetic views. Settled cancellation listeners are released;
  stale requests cannot evict replacements. One bounded worker restart recovers
  pending jobs. Native downloads also settle cancellation independently of
  stalled iOS promises, and compatible map revisions preserve saved selections.
- New source windows stay with their disposable publication shard. Eight cold
  PMTiles readers fetch a shared block once. Existing raw inputs are preserved.
- The locally fixed `/publication` endpoint follows the served combined manifest,
  rather than reporting a retired nationwide job as still warming.

## Evidence and performance

[Visual proofs and reproducible reports](overnight-2026-09-09/README.md) include
same-camera before/after renders, actual source geometry and data invariants.
131 mobile tests, both typechecks and the static web build passed before the
final isolated status/doc change; all nine Worker tests pass with that change.
The source-cache suite has eight tests, national-source suite 109, and matching
suite 43. Real DEM contours match all 950 checked seam crossings exactly.

The 400-parent Sierra fixture repeats at 58 / 69 / 58 seconds with 16 / 8 / 16
workers and identical outputs. A fresh local cut of the existing 4,000-parent
western fixture takes **5m 23s**, producing 4,000 base tiles and 4,264 unique DEMs,
**6.91 GB** total. Every tile decodes and fits delivery limits; 736 duplicated
shard-halo copies have identical bytes. These runs reuse source inputs and
exclude overviews and uploads. The 4,000-parent run uses the default persistent
source cache, not a cold rolling-publication simulation.

The larger connectivity audit covers 64,000 source tiles. It finds zero newly
disconnected cut endpoints and five source-junction review candidates. Three
MVUM cases near Merrill Springs and the eastern Sierra still need geometry
review; two others contain merged-partner records. We have not declared those
warnings resolved or started a national run.

## Next steps

1. Approve publication of the verified local commits, then deploy the web client
   and a fresh immutable pilot dataset; validate it in Expo and offline.
2. Review the five broader connectivity candidates, then run a varied cold
   4,000-parent publication trial using the bounded source/output spool.
3. Measure source acquisition, peak disk use and real R2 throughput before
   confirming a US completion time. The older 36–60 hour range is still a
   planning estimate, not a revalidated promise. No rented compute is justified
   by warm local processing alone.

## Session closure

The authorized window was 06:05–14:05 UTC. Active work and the final regional
audit are evidenced through about 13:08 UTC. The session next resumed at 21:57
UTC; that gap is not counted as continuous work. Temporary QA servers were then
stopped, the hourly heartbeat paused, and the unverified badge trial reverted.
The original app, Expo and tile services were preserved. Browser QA tabs were
already gone on resume. Source data, notes, GPS files and downloaded maps were
not deleted. The 9.3 GB regional experiment is retained locally with its evidence.
