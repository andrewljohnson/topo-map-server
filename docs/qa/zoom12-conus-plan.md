# Zoom-12 pipeline: measured CONUS plan

Measured September 8, 2026 PDT on the existing i9-13900KS machine, with both AI
training jobs left running. The target is a broad worldwide base map through z7,
CONUS native overviews at z8–11, and full-detail CONUS vectors plus raw DEMs at z12.
Higher display zooms overzoom z12. Contours and relief remain device-generated.

**Recommendation: keep generation local and publish to the existing Cloudflare
R2 setup. Budget 36–60 hours for the first nationwide run, including production
preparation/validation reserve. No rented compute is indicated by these tests.**
This is a measured planning range, not a completed national warm or a guaranteed
source-service SLA. The release-contract pilot below must pass first.

## Measurements

| Fixture / test | Result | What the timing includes |
|---|---:|---|
| Original four Tahoe parents | 10.52 s | Full vector regeneration from retained inputs, packing, 16 halo DEMs; selected prefetch/process path |
| Tahoe 40 parents | 35.79 s | Earlier retained-input build, before the final DEM pool change |
| Sierra 400 parents | 110.94 s | Retained-input regeneration with 8 processes; 484 DEMs |
| Western 4,000 parents | 14 min 38 s | First output build, mixed raw-input hits/misses; 4,264 DEMs; 6.91 GB final files |
| San Francisco 40 parents | 91 s | Mixed source acquisition, dense vectors, packing and 70 DEMs |
| Smokies 40 parents | 170 s | Mixed source acquisition, vectors, packing and 70 DEMs |
| Mojave 40 parents | 59 s | Mixed source acquisition, vectors, packing and 70 DEMs |
| NYC four-parent stress test | Largest base tile 1.48 MB gzip / 2.55 MB raw | Preserves detailed buildings, roads and POIs within a single z12 base tile |
| Empty-cache DEM, 144 parents each | 93–95 s | Eight processes, tested separately in Tahoe, Kansas and the Cascades |
| Empty-cache DEM, 144 parents each | 66–67 s | Sixteen threads, repeated in Tahoe and Kansas |
| Empty-cache DEM, 32 threads | 134 s | Tahoe trial had a slower completion tail |
| Empty-cache DEM, prefetch + processes | 50–60 s | 16 I/O threads followed by 8 render processes; Tahoe and Kansas |
| Warm western DEM phase, 4,264 parents | 119.54 s | Selected prefetch/process path; all output files identical |

The large western build reused most native DEM windows. Its DEM timing is useful
for sustained processing, while the isolated empty-cache probes supply the cold
acquisition estimate. The cold probes preserved pinned catalog selections where
available and used completely empty native raster caches. They fetched 108–120
native windows and 373–385 MB of compressed native data per region. Global
fallback caching was retained; these were mainland USGS tests.

The CPU changes include process workers, spatially grouped jobs, parallel parent
packing, reuse of repaired boundary polygons and projected agency trails, and
reuse of normalized OSM during conflation. Cold NLCD acquisition now requests
256 aligned fine rasters at once. Level-3 DEM PNG encoding is lossless and about
4.5× faster than level 6 on the small encoding test, at roughly 6% more bytes.
Vector work, native DEM acquisition, and DEM rendering use separate pools.
Native acquisition uses 16 threads; raster reprojection/encoding uses 8
processes. A full warm 4,264-DEM thread-only test took 561 seconds, compared with
120 seconds using processes. This prevents the cold-I/O optimization from
slowing CPU-bound warm processing. Only missing native chunks are prefetched.

Correctness checks include all **4,000 reference vector parents and 4,264
unchanged DEM files (4,471,128,064 elevation samples)**; 6,400 unchanged boundary children; 6,400 unchanged
trail children; and 17,583,260 identical NLCD pixels. Cold-fetch and threaded
Tahoe outputs also match the retained-input reference byte-for-byte. Native
z10–11 sample overviews preserve source MVT geometry, properties, IDs and buffers
while changing only layer namespaces. Full evidence is under
[`experiments/tahoe/results`](../../experiments/tahoe/results/).

## National arithmetic

The existing CONUS coverage mask enumerates **144,027 detailed vector parents**
and **146,681 detailed DEM parents** including the geographic halo. Worldwide
z0–7 requires 21,845 base tiles; CONUS z8–11 adds 48,750 base tiles.

- Detailed vectors: the large western pass projects linearly to 5.34 hours.
  Reserve **8–12 hours** for denser regions and additional source acquisition.
- Cold detailed DEM: the selected prefetch/process probes project to **14.2–17.0 hours**.
  Reserve **19–27 hours** for sustained service variability, including the slower
  eight-process regional result.
- Native overviews: reserve **3–6 hours**. The bounded 30-tile, mixed-source
  overview sample took 62.5 seconds with one worker; its urban/mountain samples
  are not a population-weighted national sample.
- Production preparation, inspection, retries and final verification: reserve
  **6–12 hours**. Rounded combined planning range: **36–60 hours**.

Uploads must overlap generation. Three synthetic 16 MiB uploads to Cloudflare's
[public speed-test endpoint](https://github.com/cloudflare/speedtest) measured
97–165 Mbps, median **111 Mbps**. This measures the edge path, not sustained R2
object publication. At a conservative 50 Mbps, 210–320 GB needs about 9–14 hours
of transfer and fits behind generation. The initial R2 pilot must verify this.
At 20 Mbps that transfer takes 23–36 hours, so backpressure becomes important.

[`forecast_conus.py`](../../experiments/tahoe/forecast_conus.py) records the
arithmetic and assumptions in a reproducible JSON report.

## Storage and machine resources

Plan for **210–320 GB** of finished data, with approximately 250 GB a useful
working estimate. The final corpus will not fit alongside existing data in this
computer's roughly 90–100 GB remaining disk space. Use a rolling publication
spool rather than retaining the entire finished corpus locally.

Use **8 vector/render processes and 16 native DEM I/O threads**, in separate
phases per shard.
The large vector run's largest individual worker peaked around 1.1 GiB RSS;
the 16-thread acquisition comparison peaked around 1.1 GiB total. Warm DEM
render processes peaked around 397 MiB each in the final large test. Both training jobs
remained running. Available RAM stayed above 20 GB in the checked samples, with
no active swapping. Cold DEM probes consumed about one CPU core on average;
source I/O, rather than spare CPU, dominated that phase. Freeing the training
CPUs is not necessary for the present plan.

R2 Standard storage for 210–320 GB is approximately **$3–$4.65/month** after its
10 GB storage allowance, in addition to the existing Workers plan and any usage
above included operations. R2 has no internet egress charge. Current
[Cloudflare pricing](https://developers.cloudflare.com/r2/pricing/) is $0.015 per
GB-month, $4.50 per million Class A operations, and $0.36 per million Class B
operations, with monthly allowances of 1 million A and 10 million B operations.
These costs are for retained data, not paid generation servers.

## Production rollout to implement next

1. **Freeze a release contract from main.** Give the combined base and 1024-pixel
   detailed DEM new dataset IDs and an immutable source manifest. Support native
   lower zooms and explicit DEM dimensions. Preserve the seven logical vector
   namespaces and current static map assets. Update the cloud PNG validator,
   gzip response metadata, size limits, renderer source mapping, and offline
   download manifest together. The existing publisher only accepts 512-pixel
   detailed DEMs and cannot publish this format unchanged.
2. **Pass a candidate-release pilot in Tahoe and San Francisco.** Publish under
   a new release prefix, verify checksums/HTTP encoding, then point the website
   and Expo at that same candidate. Check z10–18, lake labels, trail continuity,
   POI breakup, contours, offline downloads, and interrupted-download recovery.
   Preserve GPS recordings and map notes during any tile-cache migration.
3. **Run resumable spatial shards of roughly 256–512 parents.** Use the measured
   process/thread counts, native overview composition, and a bounded upload
   queue. Keep an on-disk tile/hash completion ledger. Retry failed work without
   caching errors as empty tiles. Each shard must be independently restartable.
4. **Upload continuously and keep scratch bounded.** Cap new scratch/spool data
   around 25 GB and retain at least 50 GB free disk. Verify the remote object's
   checksum before removing its disposable local output. Retain existing raw
   sources and source catalogs; use a separate, evictable cache for newly fetched
   working windows. Apply backpressure if uploads fall behind. Do not delete
   original inputs, phone samples, notes, or GPS files to make space.
5. **Verify coverage, then publish the release manifest.** Require every planned
   key in the verified ledger, inspect representative regions/zooms, and test
   both online and offline app behavior. Keep the current public dataset usable
   while the new release is prepared, and retain a rollback manifest.

These are the next production changes; the experiment does not already provide
this national scheduler, rolling eviction, cloud contract or mobile migration.
No experimental map data has been uploaded to R2, no nationwide generation has
started, and the old publisher remains disabled.

## Deadline checkpoints and fallback

After the pilot, recompute completion time from sustained 30-minute rates and
remaining work for each phase, including retries and spool growth. Inspect at
least hourly. A projected finish beyond 60 hours warrants investigation while
there is still time inside the three-day target.

If CPU is the limiting stage, first evaluate the user's offer to free training
resources. If the limiting stage is upstream service latency or upload bandwidth,
freeing CPU will not resolve it. The same independently restartable shards can
then run on additional US compute after checking a current quote and obtaining
approval. Spot workers need durable checkpoints and retries; AWS normally gives
only a [two-minute interruption notice](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html).
No paid instance is needed or provisioned by this plan today.

## Try the local samples

- [Fallen Leaf fixture](http://192.168.1.107:3000/experiment)
- [Lake Tahoe, with overview zooms](http://192.168.1.107:3000/experiment?region=tahoe-10x)
- [San Francisco](http://192.168.1.107:3000/experiment?region=sf-10x)

These links are for a browser on the same Wi-Fi. Expo and the public cloud map
still use their existing production datasets. Browser visual checks reached
z12, z14, z16 and z18 using the same z12 detailed source keys. Development-tab
`idle` timings were affected by background browser scheduling and are not phone
rendering benchmarks. Dense city POI styling deserves a separate cartography
review, but its detailed data remained present while overzooming.

### Captured visual proof

Actual browser captures from the local sample: [Tahoe overview](zoom12-proof/tahoe-z10.png),
[Fallen Leaf campground at z14](zoom12-proof/tahoe-z14.png),
[individual amenities at z16](zoom12-proof/tahoe-z16.png), and
[San Francisco overzoomed to z18](zoom12-proof/sf-z18.png). Map attribution is
available through the visible information control; source licensing and credits
remain in the repository data-source documentation. The older SF capture includes
a development idle timer; it is not a phone performance measurement.
