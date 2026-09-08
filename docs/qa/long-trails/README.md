# Long-distance route styling

PCT: blue (#296a91), long dashes. TRT: purple (#775595), short dashes.
Other named long-distance routes: ochre (#996337). Cream casing separates
routes from terrain. PCT/TRT labels and original route-reference badges use
the matching colors. The legend includes each visible route style and casing.

Overview strokes use the routes layer; at z13 they switch to the existing
conflated network and retain route identity. Ordinary trail strokes exclude
these designated routes. Separate agency geometry is not reintroduced at detail.
Where routes share a conflated feature, its retained route_ref selects the stroke;
existing route badges may still identify both routes.

Focused phone-sized visual proof (unrelated terrain/POI overlays omitted): PCT
at [-120.105,38.84], z11/z14; TRT overview at [-119.91,39.07], z11; TRT detail at
[-120.223775,39.130327], z14. Line features render across the z13 handoff and the
TRT legend includes the route sample. All 76 client tests passed; final style
composition tests and both TypeScript checks passed after color matching.
