# Canonical PCT source policy

The Twin Peaks report exposed generalized USFS main-PCT surveys offset by up to approximately 207 m from the OSM/PCTA route. This is not a reason to widen ordinary conflation tolerances.

For the main Pacific Crest Trail, the retained geometry is **OSM plus the dedicated checked-in PCTA centerline**. PCTA supplies sections not present in OSM. When the complete PCTA catalogue is available, USFS main-PCT records supply metadata through existing strict overlap matches but their unmatched survey geometry is not drawn as another trail. No new long connectors are constructed to reconcile the generalized survey.

`conflate(..., canonical_routes={'PCT'})` declares complete catalogue availability before tile clipping, preventing old survey tails from reappearing in neighboring tiles where the canonical line is outside the work halo. `canonical_routes=set()` leaves normal USFS fallback intact. The default `None` infers PCTA availability from local additions for standalone callers and fixtures.

This policy does not remove independent OSM paths, other agency trails, or named PCT spurs, connectors, alternates, alternatives, and bypasses. Original source data are retained. Strictly matched USFS descriptive metadata remain in source provenance; an unmatched survey is not automatically asserted to be the same physical geometry.

## Verification

- Retained metre-space source fixtures cover `14/2719/6254` and `14/2719/6255`.
- All original OSM linework survives to within numerical splitting tolerance.
- Both fine tiles have zero remaining USFS main-PCT geometry, including the exact reported viewport.
- Resulting PCT network equals the OSM+PCTA-only baseline: source selection adds no new PCT geometry or long synthetic connector.
- Tests cover no-OSM PCTA coverage, absent/empty canonical catalogue fallback, clipping-independent availability, and retained unsigned/different-route/spur/alternate/connector paths.
- 55 trail matching tests pass.

A rejected experimental approach attempted larger ordered-shape matching with short cut-end constraints. It was removed: clipped generalized surveys could not be fully reconciled without inventing long connections. The shipped candidate uses source selection instead.

Source selection does not independently validate every side trail's survey location or repair an agency branch whose original surveyed junction lies far from the canonical PCT. Such discrepancies remain QA findings; do not manufacture access paths to conceal them. No claim is made about nearby TRT linework from this PCT-specific correction.

Root verification: 113 national-source tests pass, including catalogue availability independent of the tile clip. A nine-parent preview built in13.8s alongside California publication. Browser proof at the user's exact center/zoom/pitch shows one PCT alignment through the switchbacks and northern approach. The one-parent connectivity audit reports53 agency ends,2 original source dead ends, and zero disconnected new cuts/lost source junctions. Nearby TRT overlap is visibly still present and is not covered by the PCT source policy. This is a local candidate, not yet published; frozen California r3 predates this change.
