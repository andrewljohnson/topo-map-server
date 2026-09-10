# PCT duplicate survey regressions

Reports on California r1:
- Tahoe: longitude -120.126022, latitude38.897893, zoom16.3.
- Southern California: longitude -118.348933, latitude34.602795, zoom17.13.

Pinned source fixtures: `services/tiles/fixtures/pct-signed-route-alignment.json` (local ground metres before MVT quantization). OSM and PCTA follow one alignment. Tahoe's USFS PCT survey is displaced up to about80m and generalized; OSM ref2000 and USFS PC2000 also disagree syntactically. Southern California USFS calls its segment `PCT SAN FRANCISQUITO CYN`, previously missing the signed route identity despite close alignment.

Official trails v14 recognizes explicit long-route acronym prefixes (excluding spur/connector/access/approach names, and applying regional bounds). An additional conflation check requires both records to explicitly identify the same signed route, a30m tight interior seed, source/reference lengths above500m with comparable corresponding trace lengths, and an ordered Frechet shape distance within100m. Ordered shape comparison distinguishes traversals and is bounded to one million vertex pairs. It removes only the corresponding source trace; original OSM geometry is preserved in both directions, with unmatched tails and branch junction handling retained. It does not apply a global100m merging radius to unrelated paths. Unsigned/different-route and unseeded parallel survey tests retain their geometry.

49 trail-matching and14 national-trail tests pass. Real regressions leave only the OSM PCT alignment within both reported viewport neighborhoods. Independent640-source-tile Tahoe and640-source-tile SF connectivity audits have no newly cut disconnected ends or lost-junction warnings. Original source dead ends are retained; the reports are not a claim that every source trail is connected. Full rendered-candidate QA still required before publication.

Local combined preview `map-round2-proof` passed actual browser checks at both exact reported PCT hashes. The Tahoe arc and southern California duplicate are gone, leaving one continuous OSM-based signed route. Root also checked Halfmoon at18 (onecampground +separatebathroom) andThreeBrothers at15.2 (onecanonicalformation +MiddleBrother; source tests retainLowerBrother). Walkway agent verified MountainRoom at15.18/17 andGoldenGate at15.18: quieter circulation, hikingroutesstillprominent. Preview covers45parents andbuilt in84.5seconds acrossfive separated regions; this is not a statewide runtime estimate.
