# Topo mobile

The Expo app opens directly on the map. It shares the web cartography and embeds
MapLibre, workers, icons, and local font rendering for offline use. The default
server is the [public cloud map](https://topo-map.andrewljohnson.workers.dev/), whose
current detailed coverage is the Tahoe/San Francisco pilot.

## Development

From the repository root:

```sh
./scripts/mobile.sh
# Explicitly use the local on-demand tile server instead of published cloud tiles:
EXPO_PUBLIC_TILE_SERVER=http://YOUR_LAN_IP:3001 ./scripts/mobile.sh
```

Use Expo Go matching the SDK in `package.json`, signed into the same Expo account
as the CLI. The phone must reach the Expo development server; local tile testing
also requires access to port 3001. Never use `localhost` as a physical phone's
server address. If another Expo project is running, select a different Metro port.

Full Expo development reloads clear map caches and download selections so stale
LAN or cloud tiles cannot mask loading problems. Fast Refresh does not repeatedly
erase the active session. Notes and GPS files are retained. Installed release
builds retain offline maps. An explicit `EXPO_PUBLIC_TILE_SERVER` overrides the
cloud default; saved connection overrides are ignored on development launch.

## Download behavior

The small map button opens the selection grid. Entering download mode moves to the
grid's useful zoom once; selecting a cell does not change zoom. Select cells to
queue them, tap again to remove a selection, and use the panel to see progress
and downloaded size. The icon shimmers while phone downloads are active.

Current combined releases have **two physical datasets**: one base vector MVT
and one raw DEM. Each selected z12 cell includes its detailed base, published
low-zoom ancestors, and DEM neighbors needed for terrain continuity. Shared tiles
are downloaded once. Counts depend on the exact coverage manifest and neighboring
selections; the old fixed “33 base plus 22 contour tiles” calculation does not
apply. Contours and shading are generated on the device from the DEM.

Native document storage holds versioned tile files. The WebView bridge reads them
as base64 and hands ArrayBuffers to MapLibre; network requests go through native
code to the configured server. Selected maps reopen offline after metadata and
all required tiles have been saved. An uncached area cannot supply missing detail
without a connection. Use an installed build for offline cold-launch acceptance;
Expo Go also depends on having its development bundle available.

Deselecting a cell cancels remaining work but retains shared cached files. Clear
map storage is available when loading and queued work have stopped. Notes and GPS
are separate. Compatible combined releases with unchanged format/coverage preserve
selected regions and refresh their base/DEM data; incompatible coverage or format
changes may reset selections. This is not an atomic offline rollback guarantee
while a release refresh is only partially downloaded.

## Scheduling and background work

Published combined metadata requests batches of four tiles; the generic client
supports up to eight when advertised. Foreground offline work has two batch lanes.
Visible base and DEM requests each reserve two direct lanes, and offline batches
yield to them. Reservations deduplicate viewport and saved-region requests.
Completed files remain reusable; partial responses retry only missing tiles.

Leaving the foreground submits selected work to native background transfers. A
persisted journal recovers completed batches after relaunch, and returning to the
foreground restores the bounded scheduler. Platform scheduling determines when
background transfers run. See [background behavior and physical-device acceptance](../../docs/background-downloads.md).

Contour rendering uses a separate worker. One transient worker crash is retried
with a fresh worker; persistent failure stops retrying and settles requests rather
than creating an endless restart or wait. Stale worker replies cannot populate a
replacement worker's requests. This does not change the base-map or raw-DEM cache.

## Standalone distribution

`eas.json` provides `preview` (internal iOS build / Android APK) and `production`
(store distribution). Both embed the JavaScript and MapLibre and default to the
cloud API, so they do not need Metro or Expo Go.

From this directory, after `source ../../scripts/env.sh`:

```sh
pnpm dlx eas-cli device:create
pnpm dlx eas-cli build --platform ios --profile preview
# Android APK:
pnpm dlx eas-cli build --platform android --profile preview
```

For iOS internal distribution, use the registered phones and active developer
membership. EAS handles signing prompts; keep account passwords and signing keys
out of Git and chat. The build dashboard provides installation links after a build
succeeds. Adding another device can require refreshed provisioning and a new or
re-signed build.

[Project/build dashboard](https://expo.dev/accounts/andrewljohnson/projects/topo-map-server)

For store/TestFlight distribution, use `--profile production` and the corresponding
EAS submit command. Follow the current platform enrollment, signing, and review
requirements. Native builds still need real-device checks for rotation, background
location, offline cold launch, and lock-screen transfers; a JS export is not a
signed build or proof of OS background scheduling.

## Checks and generated assets

```sh
pnpm bundle:map
pnpm test
pnpm typecheck
pnpm export
```

The tests cover queue ownership/priority, cancellation, batch recovery, release
migration, contour transport, style contracts, POI handoff/matching, notes, and GPS.
Typechecks and web map renders complement them. Physical acceptance includes
saving a cell, disconnecting all networking, reopening and browsing it, then
reconnecting and checking cancellation/resume and background behavior.

Cloud builds regenerate the ignored MapLibre asset module after dependency install.
Other generated map helpers are tracked; run `pnpm bundle:map` before committing.
Full [source attribution](../../docs/data-sources.md) remains available from the
map's circular information button together with the viewport legend.
