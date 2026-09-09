# Local generation, Cloudflare delivery

> Historical September 7 design. Worker delivery is now implemented. The current
> two-dataset z12 pilot, commands and limits are documented in
> [combined publication](combined-publication.md). The zoom ranges and pending
> implementation statements below describe the superseded design.

Decision: 2026-09-07. This document records the architecture. See [current operations](../services/cloud/README.md) for the implemented commands and limitations.
It replaces the continuously running Python cloud server. No cloud resources have
been purchased and no full-country job has been launched on this computer.
The existing S3-compatible adapter, coverage policy and client-key work can be reused;
the cloud Worker and local publishing workflow still need implementation.

## Architecture

- This Linux workstation imports source data, generates vector tiles and raw DEM
  tiles, validates them, and uploads them to a private Cloudflare R2 Standard bucket.
- A Cloudflare Worker serves the static website and the existing metadata/tile/batch
  API from R2. It performs no geographic processing. Finished maps remain available
  when the workstation is off. No VPS or Cloudflare Container is required.
- The mobile app keeps generating contours and relief from raw DEM on the device.
- Separate versioned datasets remain independently composable: basemap, DEM,
  boundaries, land cover, trails, recreation, waterways and amenities.
- Broad global basemap: zooms 0–7 (21,845 XYZ tiles). Detailed CONUS basemap through
  zoom 14; DEM zooms 3–13 with needed neighbor samples; supplemental layers within
  CONUS at their supported zooms. Alaska, Hawaii and other countries get overview.
  Outside detail coverage, overzoom the overview rather than request detailed tiles.

## Local pipeline

1. Inventory and reuse existing validated cache tiles and source indexes. Pin the
   source versions and output dataset identifiers before starting a publication.
2. Benchmark representative mountain, flat and urban regions, recording output
   bytes, render seconds, upstream bytes and upload throughput. Establish the total
   storage estimate and completion estimate from measured samples, not a promised TB.
3. Generate a bounded spatial batch, validate vector decoding/DEM dimensions, upload
   with a checksum, verify receipt, journal success, then permit eviction of that
   batch's generated local copy. Never evict unpublished data or unrelated dev files.
4. Use a durable SQLite cursor and upload journal. Resume after network failures or
   restarts without rerendering or uploading verified output. Limit CPU and concurrent
   transfers so normal development and foreground map viewing remain responsive.
5. Keep source indexes and provenance separately from replaceable output/scratch.
   This computer currently has 133 GiB free, so do not assemble the full output here.
   Start with a 30 GB publication spool and a 50 GB free-space reserve. Reusable source
   caches need a separate bounded allowance; pause if imports require more room.
6. Publish the global overview first, then California and CONUS low/medium zooms,
   followed by detailed CONUS and supplementary layers. Keep layer and region progress
   visible, with actual uploaded bytes and remaining work. Verify before marking warm.

Initially upload individual tiles with small batches of concurrent PUTs, retaining
our existing XYZ and mobile batch API. Request batching does not reduce R2's per-object
write count. Benchmark regional PMTiles/raster archives as a subsequent storage
optimization if object count materially affects cost; do not require a full-country
archive to fit locally or rebuild it for each small update.

## Missing tiles and publication safety

While warming, the cloud service serves already published parent basemap/DEM tiles
where useful, and clearly indicates unavailable detail. Missing keys must not cause
an endless client retry loop. Explicit empty overlay tiles count as valid coverage.
A bounded, deduplicated priority queue can let this workstation poll for recently
requested missing CONUS tiles, ahead of the bulk traversal. No inbound connection to
this computer is needed. If it is off, new detail waits; finished cloud maps keep working.

Publish immutable objects under dataset versions. Publish metadata/coverage manifests
only after their referenced objects are verified. Promote a release with one manifest
pointer update; keep the previous release for rollback. Initial partial coverage is
explicit in the manifest. Retention must avoid charging indefinitely for obsolete data.

## Fast delivery and cost controls

- R2 has no public bucket domain. Requests go through the Worker, which checks the
  revocable client key before retrieving either an edge-cached or R2 response.
- Cache immutable tile data behind that check. Do not put publicly reusable signed
  URLs or a shared public CDN cache in front of authorization/quota enforcement.
- Use durable, atomic request/download allowances (Durable Objects), bounded batch
  sizes, Worker CPU limits, rate limits and a global circuit breaker. Batch quota
  reservations to avoid a separate accounting trip for every tile where practical.
- Only the local publisher has write access. Browsing cannot invoke cloud generation
  or create unbounded R2 objects. Cap publication bytes and priority-queue size.
- Validate cached and uncached paths with invalid/revoked keys and exhausted quotas.
  Measure latency from the phone and verify cached requests do not hit R2 unnecessarily.
- These controls bound application workloads, not the complete provider invoice:
  standing storage and requests rejected during abuse can still incur charges.

## Cost model, checked 2026-09-07

R2 Standard is $0.015/GB-month, with 10 GB storage, 1 million Class A operations and
10 million Class B operations included monthly. Egress is free. Workers Paid starts
at $5/month, including 10 million requests and 30 million CPU milliseconds. Durable
Object metering and any overages must also be measured; low single-user usage is
expected to fit largely within the included allowances.

| Stored finished data | Approximate monthly R2 + $5 Workers baseline |
| --- | --- |
| 500 GB | $12.35 |
| 1,000 GB | $19.85 |
| 2,000 GB | $34.85 |

These are storage scenarios, not measured final dataset sizes. Excludes taxes, domain,
local electricity, source transfer costs/data caps, and operation/compute overages.
One-time 10 million tile PUTs within one month cost approximately $40.50 after the
1-million included writes, assuming no other Class A operations. Multipart writes,
listing, retries and larger datasets change this. Initial generation/upload may take
days or weeks; benchmark before giving a completion date.

Sources: [R2 pricing](https://developers.cloudflare.com/r2/pricing/),
[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/).
Cloudflare Containers are unnecessary in this plan.

## Credentials and release workflow to implement

Keep local credentials outside the repository, in
`~/.config/topo-map/cloudflare.env` with mode 600:

- CLOUDFLARE_ACCOUNT_ID; deployment authorization is saved separately by `wrangler login`.
- `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_ENDPOINT_URL`;
  use a bucket-scoped Object Read & Write credential. Endpoint `https://ACCOUNT_ID.r2.cloudflarestorage.com`, region `auto`.
  This credential is for the local publisher only, never the website or phone.
- A generated client map key, entered into the phone's secure storage and browser
  session; deploy its verification hash as a Worker secret. No user accounts yet.

No AWS account, SSH key or rented server is needed. The exact deployment token
permissions should be documented alongside the final Wrangler configuration.
R2 credential instructions: https://developers.cloudflare.com/r2/get-started/s3/

Replace the old SSH deployment script with a release command that reads committed
main, builds/tests the Worker and static site, deploys an immutable code version,
smoke-tests authorized browsing, then promotes the published dataset manifest.
Data publication is resumable and independent of code releases; a code deploy must
not restart country-wide generation. Use local-main when no Git remote is configured,
otherwise fetch main explicitly. Never upload uncommitted files or local secrets.

## Delivery sequence

1. Build the private Worker/R2 serving path and local resumable publisher.
2. Deploy a small real sample; test on the browser and Expo, quotas, batches and
   offline downloads. Compare rendered layers with the local service.
3. Measure sample output and throughput; set an explicit storage ceiling.
4. Start worldwide overview and CONUS publication locally, with California priority.
5. Verify geographic/zoom completeness and report completion from the upload journal.
