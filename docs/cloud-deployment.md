# Public map v1 deployment

## Hosting decision (researched 2026-09-07; not purchased)

Use one Linux server with local storage for v1: Caddy serves the static map over
HTTPS and proxies tile requests to the Python service. The cache and source
indexes live outside release checkouts. No accounts or feedback backend yet.
The existing Sites/Vinext development configuration is retained; the portable
production build uses `TOPO_STATIC_EXPORT=1` and serves `dist/client`.
Sites' Worker runtime cannot host this Python/GDAL filesystem workload.

Current low-cost shortlist, before location/network options and applicable tax:

| Option | Indicative monthly cost | Tradeoff |
| --- | --- | --- |
| Netcup VPS 1000 G12 (4 vCPU, 8 GB, 256 GB) + 2,048 GB block storage | €33.29 excluding VAT | Cheapest practical starting configuration here; less import/render headroom |
| Netcup VPS 8000 G12 (16 vCPU, 64 GB, 2,048 GB NVMe) | €40.29 excluding VAT (€47.95 with 19%) | Recommended for the country-wide import and many small cached files |
| Hetzner Server Auction with at least 2 TB **usable** disk | Quote from live inventory | Compare SSD/HDD, latency, RAM and actual usable disk; two mirrored 1 TB disks provide only 1 TB |
| Compute server + Cloudflare R2 | Compute + $15/TB-month standard storage + operations | Free R2 egress, but needs an object-storage cache adapter; current code uses local files |

Sources: [Netcup plans](https://www.netcup.com/en/server/vps),
[block storage (€0.012/GB before VAT)](https://www.netcup.com/en/server/local-block-storage),
[Hetzner auction](https://www.hetzner.com/sb/),
[R2 pricing](https://developers.cloudflare.com/r2/pricing/).
Netcup headline monthly rates use a 12-month contract; hourly/no-term rates are
higher. US location and IPv4 pricing must be checked in the actual order. Do not
order on the strength of the headline price alone. This is not a provider quote.

The previous measured estimate was 650 GB–1 TB for all-50-state basemap plus DEM,
including reusable DEM source chunks. It excluded supplementary datasets. Allow
2 TB usable capacity initially and measure growth; this is not a guarantee that
all overlays fit. The development filesystem has only 133 GiB free, so no full
nationwide job has been started there. Warming can take days to weeks or longer
on a small server; the previous 5–14 day range was basemap+DEM on this workstation,
not a benchmark of this cloud machine or all overlays.

## One-time server setup

Use Ubuntu 24.04 LTS x86-64, Docker Engine with Compose v2, curl and util-linux
(flock). Install Docker using its official distribution instructions. Only SSH,
HTTP and HTTPS need inbound access. The tile container has no published port;
job inspection stays behind SSH. Configure a DNS A record (and AAAA only if IPv6
works) for the desired hostname. Caddy obtains and renews the certificate.

Mount the data disk persistently through fstab before deploying. Do not format
an existing disk without checking its contents. `DATA_DIR` must already exist.
A deploy user needs permission to run Docker and write `/srv/topo-map`.
Docker access is administrative access to the server.

Create `/srv/topo-map/server.env` from `deploy/server.env.example` and set:

```sh
SITE_ADDRESS=maps.your-domain.com
DATA_DIR=/srv/topo-map/data
```

On the developer computer, copy `deploy/deploy.env.example` to ignored
`deploy/deploy.env`. Set an SSH host/alias and optionally the release root.
The script uses your normal SSH credentials; no passwords or provider tokens
are stored in the repository.

## Release from main

```sh
# Commit work to main. Push main too when origin is configured.
./scripts/deploy.sh --dry-run
./scripts/deploy.sh
```

With an `origin` remote, the script fetches and deploys its latest `main`, even
when another branch is checked out locally. Without a remote it uses committed
local `main`. Uncommitted files are never deployed. It refuses a main revision
that does not contain the deployment implementation.

Each deployment uploads a git archive into a new release directory, builds
images tagged by the resolved main SHA, then replaces the running containers.
The old service stays up during the build. Cutover can briefly interrupt cold
requests; this is not a zero-downtime cluster. A single deployment lock prevents
concurrent cutovers. Health checks cover containers and the actual HTTPS page
and metadata endpoint. Failure attempts to restore the previous images.
`current` is changed only after checks pass. Old images/checkouts are retained
for rollback, so periodically remove old **release artifacts** after checking
which ones are live; never run `docker compose down -v` or wipe the data volume.
Base images and Python version ranges can resolve differently on a later build;
source revisions are fixed, but dependency artifacts are not fully reproducible.

No Git remote, production server, domain or release credentials have been set
up by this change. Docker is unavailable on the development host, so the Compose
stack still needs its first real container build and server smoke test.

## Automatic source import and warming

After a healthy release the detached warmer first downloads the official US
Geofabrik PBF (~11.3 GiB in the listing at time of research), verifies the
publisher's MD5, and records its source identity. Interrupted transfers resume;
a changed source fails checksum validation and downloads afresh. The PBF is
retained so restarting does not download it again.

`osm_bulk.py` streams amenity nodes/ways/areas and all waterway tags into a local
SQLite spatial index, preserving OSM identities, full site polygons, seasonal
and intermittent tags. Node locations use a disk-backed index. The completed
index is installed atomically. Missing local data is an explicit production
error, not a request to public Overpass. Development retains its previous
on-demand fallback until a bulk index is installed.

Then `warm_us.py` runs through basemap z0–14 and raw DEM z3–13 first, followed by
boundaries, land cover, official trails, recreation, waterways and amenities at
their advertised zooms. A Natural Earth 10m US mask includes Alaska and Hawaii
and avoids warming an enormous rectangular ocean area. Each dataset is clipped
to its actual advertised extent: notably the current NLCD service is CONUS, not
all 50 states. This mask is a warming aid, not a legal boundary. Tiles beyond
the mask remain available on demand.

Batches contain at most eight tiles and use the same low-priority rendering
gates as phone downloads. Only one batch runs at a time. Active viewport
requests and a two-second quiet period take precedence. Importing the initial
PBF also consumes resources; it is not a measured nationwide performance run.

SQLite stores a cursor per dataset/zoom and a separate retry queue. Failed or
missing batch results are never marked successful. Finished cursor ranges are
skipped on restart; failed keys remain visible with backoff. Dataset or mask
changes create separate runs. The worker and renderer preserve a 50 GB free
space reserve. No old cache is deleted automatically.

Status is stored under `DATA_DIR/jobs`:

- `us-prepare-status.json`: initial source preparation and import errors.
- `us-status.json`: warm state, successful count, remaining failed keys, per-source cursors.
- `us-warming.sqlite`: durable checkpoints. Do not edit while the worker runs.

`complete` means all planned tiles succeeded for the active manifest, at its
configured zooms and coverage. It does not mean every real-world feature exists
in every provider's data, or that a future dataset is already warm. Supplementary
ArcGIS services may take much longer than the core terrain; failures remain
retryable. In particular, NLCD currently uses per-tile raster exports, so full
coverage may take weeks or longer. A bulk NLCD COG ingestion path is the next
optimization if that source becomes the bottleneck.

Commands on the server (from the release directory):

```sh
cd /srv/topo-map/current
set -a
source /srv/topo-map/server.env
export RELEASE_SHA=$(cat .release-sha)
set +a
docker compose -f deploy/compose.yaml --profile warm logs --tail 100 warmer
# Pause across deployments:
touch /srv/topo-map/warming-paused
docker compose -f deploy/compose.yaml --profile warm stop warmer
# Resume:
rm /srv/topo-map/warming-paused
docker compose -f deploy/compose.yaml --profile warm up -d warmer
```

Read-only planning without warming any tiles:

```sh
services/tiles/.venv/bin/python services/tiles/warm_us.py \
  --api http://localhost:3001 --data /tmp/topo-plan --plan
```

The dry plan can take time at high zooms. It does not download the PBF or write a
job database. `--max-zoom 6` is a small coverage check. For a controlled warm test,
use `--sources osm --max-zoom 0 --once` with a temporary job directory.

## Before opening to substantial traffic

The server is public read-only v1. Add a measured request-rate limit at the edge
and monitor disk, inodes, render latency, HTTP errors and upstream failures
before promotion. A single machine has no failover. Cache files are regenerable;
keep source manifests/configuration off-host. When accounts and submitted notes
arrive, their database will require automated backups and tested restores.
