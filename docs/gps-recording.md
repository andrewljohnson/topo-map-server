# Foreground GPS recording

The Expo app automatically requests foreground location access and subscribes at
high accuracy while active (2-second time interval on Android; iOS delivers fixes
at its supported cadence). It stops the subscription on inactive/background and
on unmount. The locate button still centers the map; recording never recenters it.
Background recording is off by default; the stats-screen switch opts into a native location task. Points are never uploaded.

`gps-track.jsonl` lives in Expo FileSystem's documents directory. Each JSON line
contains `x` (WGS84 longitude degrees), `y` (latitude degrees), `z` (device-reported
altitude in metres, null if unavailable), `time` (Unix milliseconds), `accuracy`
and `altitudeAccuracy` (metres or null), `speed` (m/s or null), `heading` (degrees
or null), `mocked` (device flag), and a foreground `segment` identifier. Device
altitude is recorded without asserting a cross-platform vertical datum.

Points stay in memory until 50 accumulate, then append to the flat file. Leaving
the foreground or unmounting flushes a partial batch too. Up to 49 recent points
can still be lost if the OS kills the app before a lifecycle callback. Failed
writes retain their buffer and expose an error. Appends begin with a newline so
a torn final record cannot swallow the next batch. Replay skips malformed rows
and ignores duplicate/out-of-order timestamps.

The lower-right bar-chart button opens three stats: distance (mi), moving time,
and elevation gain (ft). Recalculate flushes pending points and rebuilds the
same incremental accumulator from the file, preserving fixes arriving during the
rebuild. App startup also replays the file. Reset clears the file, buffer, and
stats after confirmation; subsequent foreground fixes start a new recording.

Statistics are hiking-oriented estimates, not raw GPS sums. Unknown or >50 m
horizontal accuracy doesn't contribute. Distance needs displacement beyond a
3 m/accuracy-based deadband and inferred speed between 0.5 and 12 m/s. Gaps over
30 seconds or foreground-segment changes never connect. Elevation gain uses a
5 m hysteresis threshold, requires altitude accuracy of 15 m or better, and only
updates during accepted horizontal movement. Raw fixes remain available to
recalculate with improved filters later. Missing altitude leaves gain unchanged.

Tests cover 50-point batching, partial flushing, exact live/replay stats equality,
stationary noise, jumps, missing altitude, segment gaps, file failures, corruption,
reset during replay, and subscription stop/resume. Expo iOS/Android exports verify
bundling. Actual receiver accuracy and lock/unlock behavior still need a phone walk.


## Optional background recording

The stats drawer has a **Record in background** switch. Enabling it requests
foreground then background (Always / Allow all the time) permission and starts
`topo-map-background-gps-v1`. Android shows an ongoing recording notification;
iOS shows the background location indicator. Turning the switch off stops native
updates and continues foreground-only recording. Native task registration restores
the switch state after relaunch; failed permission/start requests never imply success.

The task is defined at module scope in `backgroundLocation.ts`, imported by the
entry point before React. UI and headless deliveries share one recorder and await
any file replay. Foreground watch fixes are not recorded twice while the native
background task is enabled. OS batches are timestamp-sorted and flushed before
returning, even when shorter than 50 points, so suspension does not strand them.
Foreground/background transitions do not split an opted-in continuous recording;
large GPS gaps still do. Disabling rejects late task deliveries, and fixes predating
a reset are rejected in the current runtime.

**Expo Go cannot run background location.** The switch displays a development-build
requirement there and does not pretend to enable it. A new native development or
standalone build is needed for the configured iOS location background mode and
Android background-location/foreground-service permissions. An Expo JS export is
only a bundling check, not an installed/signed native build. Permission denial,
force-quitting, and OS battery policies can interrupt recording; a lock-screen walk
on both platforms is still required for end-to-end verification.

Reference: https://docs.expo.dev/versions/latest/sdk/location/
