# Background map downloads

Saved-map batches use Expo FileSystem legacy native DownloadResumable with the iOS BACKGROUND session; Android uses native transfers too. While browsing, only two offline batches may run, with at most eight tiles each. Visible requests pause those transfers and requeue unfinished tiles without failing selected regions. On leaving the foreground, all selected regions are submitted to the OS queue so transfers can continue without JavaScript. Returning to the app cancels and requeues outstanding batches into the bounded foreground scheduler. OS networking schedules transfers; the server retains its render gates and interactive priority. Viewport requests retain their separate foreground lanes.

The app persists selections and a batch-file journal before starting each transfer. Completed JSON batches are validated against the current dataset and installed into the existing per-tile cache. After relaunch, completed journaled files are recovered; missing transfers are requested again. Removing a selection cancels transfers without other owners. Partial batches retry only missing tiles. UI progress and installation catch up when JavaScript resumes.

This works with the existing Expo FileSystem module in Expo Go and needs no background location permission. iOS may defer native network work; force-quitting is not a promise of continued downloading. Android may suspend or kill the process under battery restrictions. On reopening, saved selections resume from cached tiles. The local server must remain reachable (leaving its Wi-Fi prevents downloads). There is no periodic background task or guaranteed completion deadline.

Validation: background-downloads.test.mjs models suspended JavaScript completions, submission of multiple full regions, cancellation, and recovery. Existing queue/batch tests cover retry, dataset upgrades, cache reuse, and interactive priority. Actual lock-screen execution must also be checked on a physical phone; a Node test cannot establish OS scheduling behavior.

References: https://docs.expo.dev/versions/v57.0.0/sdk/filesystem-legacy/ and https://developer.apple.com/documentation/Foundation/downloading-files-in-the-background


## Foreground priority (2026-09-07)

Basemap and raw DEM each reserve two direct request slots. New overlay requests
wait while visible terrain is pending, then run at most two at a time across all
overlay sources. A tile already inside an offline batch is promoted to a direct
request by yielding that batch. Partial files are cleaned before requeueing, and
completed files remain cached. Viewport ownership is tracked separately from
saved-region ownership so panning away removes foreground priority without
losing the saved download.

Server download batches now leave one render slot available per source, just
like speculative warming. Render admission precedes the tile lock, preventing
a queued low-priority batch from locking out a visible request for that same tile.
Warming pauses while foreground HTTP requests are running and for two seconds
afterward; when resumed it favors the most recently viewed area. An already
running upstream fetch is allowed to finish, so cold-source latency still applies.
