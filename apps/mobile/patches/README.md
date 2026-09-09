# Contour dependency patch

`maplibre-contour@0.1.0.patch` fixes the cancellation lifecycle of its internal
async LRU cache. Settled requests remove abort listeners, and an evicted request
cannot remove a replacement entry under the same key when it fails or cancels.
Already-aborted callers do not start new work. Shared pending callers still
cancel the supplier only when the last caller cancels.

The patch covers TypeScript source and the unminified ESM, CommonJS and UMD
builds. Our `scripts/build-terrain.mjs` bundles the **ESM entry**, then writes the
same offline worker into both apps. The package's pre-minified CDN bundle is not
used or patched. Do not switch this project to that entry without carrying the
fix. Upstream's BSD-3-Clause license is retained.

`pnpm install --frozen-lockfile` applies the pinned patch. Cache lifecycle tests
are in `tests/contour-cache.test.mjs`; the actual-worker long-pan measurement is
`experiments/tahoe/audit_terrain_memory.mjs`. Recheck these when updating the
upstream package; remove the patch once an upstream version includes the fixes.
