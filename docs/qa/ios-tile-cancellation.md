# iOS tile cancellation stall — 2026-09-07

A physical Expo iPhone trace reproduced the foreground stall after rapid zooming.
Two basemap and two DEM overview requests were aborted and had no live owners,
but remained in flight for more than 25 seconds. All four core scheduler slots
stayed occupied. Visible zoom-10 requests remained unstarted. Backgrounding
allowed overlays to dispatch, explaining the apparent lifecycle-dependent recovery.

The transport had been signalled to abort, but its fetch or body-read promise did
not settle. Timeouts that only called AbortController.abort could not release it.
The loader now races fetch and response-body waits against the abort signal, cleans
up listeners, and rejects its own waiter independently of native transport behavior.
Late network completion cannot resume the cancelled job and write its tile.

Regression tests leave native header/body promises pending after abort, cancel both
foreground basemap requests, and require new detail to finish within 500 ms without
calling setForeground. They then resolve the old promises and check no stale tiles
were written. The mobile suite passes 97 tests and TypeScript checks.

A second physical-phone trace downloaded zoom-11 OSM and zoom-12 DEM while AppState
was active; rendered features increased from 4 to 187 before backgrounding. Aborted
flights no longer retained the core slots. Temporary LAN tracing was removed after
verification. Cloud publication gaps are separate and still produce missing tiles.
