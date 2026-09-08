# Product and release roadmap

## V1: public map, one server

A public map with no sign-in. Vector basemap plus separately composed terrain,
land cover, agency boundaries/trails and recreation. The browser generates
contours in feet and relief from DEM samples. Warm the US in a resumable
background job; serve misses immediately with foreground priority. Publish
manual releases from committed main using `scripts/deploy.sh`. No scheduled
source updates yet. Device notes stay private/local in this version.

## V2: accounts and a documented tile API

Add a small application backend and PostgreSQL for users, API clients, scoped
hashed tokens, usage, quotas and audit records. The first-party app and website
use registered API clients through the same API path as external customers.
Publish OpenAPI docs and token management on the website. No privileged bypass
for our app. A mobile app cannot keep an embedded shared API secret: users sign
in and receive revocable credentials; the public web map uses a constrained
public client/session with its own limits.

Introduce scheduled dataset ingestion as separate jobs. Download into staging,
validate completeness/provenance, generate and visually proof sample tiles,
then atomically publish a new versioned manifest. Keep the previous generation
available long enough for offline clients and rollback. Never silently replace
raw data under an existing dataset ID. Put authentication before cache lookup;
cache tile content by dataset/z/x/y rather than by user token.

A later object-storage adapter can move immutable tile payloads to R2 or similar,
while the rendering workers retain a bounded local source cache. This is an
incremental extension; the v1 filesystem layout is not an S3 mount.

## Public notes, ideas and voting

Reuse the existing map-note snapshot (text, WGS84 bounds/corners, center, zoom,
bearing, pitch, viewport and dataset versions). Public submission is an explicit
action; never upload existing private notes or GPS tracks automatically. Allow
freeform ideas without map bounds. Each record has an author, timestamps,
status and optional related PRs. Enforce one vote per account per idea.

Add moderation, reporting and an admin queue. Track notification preferences
separately from votes so closing an idea can notify consenting authors and
voters exactly once via a durable email outbox with retries and deduplication.
Deleting a vote must not leave an unremovable email subscription.

## Admin-directed agent work

Admins can select an idea, write a concrete assignment and enqueue a coding
job. A separate isolated worker runs the agent in a disposable checkout and
creates a branch/PR. Public submissions are untrusted task data and cannot
execute commands or assign themselves. The worker has narrowly scoped repo
credentials and no production database, email or deployment credentials.

The admin interface shows job progress, changes, tests and PR links. An admin
reviews and merges the PR into main, then runs the release script to deploy.
An agent may propose closing an idea with a summary; only the explicit admin
close action changes public status and enqueues notification emails. Record
who authorized the action and link the relevant deployed release. Account for
agent runtime/API costs separately from the map server hosting bill.

This roadmap records intended stages; none of the accounts, public submissions,
voting, email delivery or admin-agent backend is implemented by v1.
