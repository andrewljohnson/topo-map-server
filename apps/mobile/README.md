# Standalone app distribution

EAS profiles in `eas.json` build a real app with embedded JavaScript and MapLibre.
`preview` produces an iOS ad hoc install or Android APK; `production` produces an
App Store/TestFlight or Play Store binary. Both default to the public cloud map and
need neither Metro nor Expo Go. Expo development also defaults to the cloud server and ignores saved connection overrides on launch. Tile caches are separated by server origin, so LAN tiles cannot mask missing cloud coverage. Set EXPO_PUBLIC_TILE_SERVER explicitly to test a local server.

Run from this directory after sourcing `../../scripts/env.sh`:

```
pnpm dlx eas-cli device:create
pnpm dlx eas-cli build --platform ios --profile preview
```

For iOS, first use an active Apple Developer Program membership and register both
phones through the device-registration link. EAS can manage signing credentials;
complete Apple sign-in yourself when prompted. Adding a phone later requires a new
provisioning profile and a rebuilt/re-signed install. Keep Apple passwords and signing
keys out of Git and chat. A family member need not buy a developer membership.

For TestFlight, build with `--profile production`, then submit with
`pnpm dlx eas-cli submit --platform ios --profile production`. External testers need
Apple beta review; TestFlight builds expire after 90 days. App Store publication is
not required to use TestFlight. App Store Connect app setup/signing remain required.

Android can use `pnpm dlx eas-cli build --platform android --profile preview` to
produce an APK. No Play Store listing is needed for direct APK installs.

Build status: profiles and asset generation are configured, and the project is linked
to https://expo.dev/accounts/andrewljohnson/projects/topo-map-server. A signed install
is not available until platform credentials and a native build succeed. Native builds require separate device acceptance for offline maps, background
location, background downloads and rotation; a JS export is not a signed native build.

Cloud builds regenerate the ignored MapLibre asset module after dependency install.
Other generated map modules are tracked in Git and should be regenerated locally
with `pnpm bundle:map` before committing a release.

---

# Topo mobile

Expo Go app for iOS and Android. Opens straight to your local map, with a bottom-right Download button. Download mode overlays a zoom-12 grid. Tap cells to enqueue, tap again to cancel/deselect. Amber is queued/downloading, green is saved. Failed cells remain selectable for retry. Downloads use two concurrent requests of up to eight tiles each, retry missing tiles up to three times, save queue metadata after each batch, and resume when the app opens.

```sh
pnpm install
pnpm exec expo install --fix
EXPO_PUBLIC_TILE_SERVER=http://YOUR_LAN_IP:3001 pnpm start
```

Scan the Expo QR code with Expo Go on Android or Camera on iOS. Phone and computer must be on the same Wi-Fi; allow inbound ports 8081 and 3001. The default tile-server hostname is inferred from Expo's LAN host, so the environment setting is optional for the usual setup. Never use localhost for a physical phone.

Use the Expo Go version matching this project's SDK (see package.json); https://expo.dev/go lists downloads. SDK compatibility must match the installed Expo Go app.

## Offline behavior

The app embeds MapLibre GL JS, CSS, and its worker in its bundle; it does not load a CDN, public OSM tile server, or external map style. Native persistent document storage holds downloaded binary protobuf vector tiles. A WebView bridge reads these files as base64, then a custom MapLibre protocol decodes them into ArrayBuffers; all network requests run through native code exclusively to the configured server. Selected cells include low-zoom ancestors and descendants through zoom 14 (display overzooms through 18), clipped to dataset bounds. A full cell contains 33 basemap tiles and 22 contour tiles with the current zoom ranges; disk use depends on vector tile size. Downloading neighboring cells reuses shared tiles. A separate vector tile source supplies USGS 3DEP elevation contours: 20-foot lines from zoom 13, with 100-foot index lines from zoom 11 and labels from zoom 12. The renderer composes basemap and contour sources. Grid selections download both through compressed batches, with independent cache namespaces and dataset versions. Download regions again after a dataset update; unchanged source tiles are reused.

Deselecting a region cancels its remaining queue work and removes its selection. Already downloaded tiles and tiles loaded while browsing stay cached because adjacent regions share them. Use Clear device storage to reclaim all tiles after cancelling active queues. Downloads run while the app is open; mobile OS suspension pauses work, and queued regions resume on reopening. Expo Go itself must have loaded the JavaScript bundle at least once; for a dependable offline cold launch after restarting the phone, create a development/production build later.

The first launch requires the tile server to fetch metadata. Later launches can use saved metadata and tiles without the tile server. Uncached areas show a neutral background when offline. Each source cache is versioned by its own datasetId. A changed source invalidates saved selections for the composition, while unchanged source tiles stay reusable. This initial version has no background download service or regional cache eviction.

## Checks

`pnpm test` tests tile enumeration, deduplication, bounds, persisted queue state, cache reuse, and cancellation during a download using a mocked filesystem. `pnpm typecheck` checks TypeScript. `pnpm export` builds iOS and Android bundles. Physical phone acceptance: download one cell, wait for green, disconnect Wi-Fi/cellular while keeping Expo Go open, pan and zoom inside the cell, then reconnect and test queue cancellation/retry.

Map labels use built-in device fonts; the style omits a glyph URL, so glyphs are generated locally, including offline. The CSP worker is bundled into a Blob URL and does not require a worker CDN. WebGL support is required in the device WebView; renderer errors are shown in the app.

## Batched downloads

When metadata advertises `batchUrl`, the offline queue uses two concurrent HTTP batches with at most eight tiles each. A full zoom-12 national cell downloads 33 basemap tiles and 22 contour tiles, using five basemap and three contour batches when uncached. Successful tiles are written immediately even when other tiles in the response fail; retries request only missing tiles. Cached tiles are skipped. The map viewport and downloads share per-tile reservations, so an interactive request joins an existing queued or in-flight request instead of duplicating traffic. Fresh viewport requests use a separate lane of up to two direct tile requests, which the server can prioritize over offline rendering; they do not wait behind the offline queue. The combined network limit is four requests (two interactive plus two offline). Servers without batching use at most two concurrent individual requests.

Cancellation prevents new chunks from being scheduled and aborts an in-flight batch when none of its tiles have an active owner. An interactive map request keeps a shared batch alive. Completed files remain reusable. Native filesystem writes happen sequentially within each worker (at most two offline and two interactive workers), and queue metadata writes are serialized separately. UI progress refreshes at most every 150 ms while tiles arrive. Batches group tiles by source, and each source dataset identifier is checked before writing results.

`pnpm test` includes delayed-network checks for the two-request cap, four-round-trip cell downloads, partial retry isolation, viewport/queue deduplication, cancellation, restored queues, and the individual-download fallback.
