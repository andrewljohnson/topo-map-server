# Walking-path presentation

Map note captured 2026-09-09T04:04:39.310Z, center [-120.124005,38.837026],
bounds [-120.131122,38.825006,-120.116887,38.849045], zoom 14.244639.
The user asked whether footpaths and trails should look the same to a normal hiker.

Inspection found both `path` and `footway` in the same walking network, including
Blue Dot Trail, Pyramid Trail and the Lake of the Woods route. The footway records
in this viewport did not establish a difference in paving, difficulty or visibility.

Both classes now share the existing trail stroke, dash spacing, width, label color,
and single "Trail" legend entry in web and mobile. Explicit steps, sidewalks,
cycleways, bridleways and designated long-distance route treatments remain distinct.
A generic path/footway tag is not used to imply hiking difficulty or trail quality.
Future surface/difficulty treatment should require explicit supporting attributes.

No tile regeneration or dataset change is required. All 101 mobile tests and both
client typechecks pass, including consistency checks across the three style copies.

## Resort and urban circulation (California follow-up, September 10)

The Mountain Room/Yosemite Valley Lodge report exposed a hierarchy issue: short
access paths between buildings used the same strong red dash and pale casing as
backcountry trails. The street-density fade also stopped at zoom 14, so it did not
help at the reported zoom 15.18.

Unlabelled paths wholly within a group of buildings now receive `developed`
context. The fixed z14 building source includes small lodge buildings missing at
z12. Each ~50m sample must be within 70m of a building and a 150m neighborhood
with at least three substantial buildings and 600 square metres of footprints.
Checks use stable geographic cells across output tile edges; actual path
coordinates stay unchanged. A name, reference, badge or route designation prevents
this classification. Isolated huts and trails leaving the built area retain hiking
presentation. `path` and `footway` continue to follow identical rules.

Unnamed developed/urban circulation uses a thinner, quieter stroke and restrained
casing through zoom 15–17, reaching full opacity at zoom 18. Named hiking routes and
PCT/TRT styling remain prominent. Source checks cover Yosemite lodge, Yosemite
Falls hiking paths, Golden Gate Park, Balboa Park and the Tahoe PCT; unit tests
protect named/ref/signed hikes, isolated huts and exact geometry preservation.

Visual proof compared the live California r1 map with the combined candidate on
localhost:3004 at the exact Mountain Room center, zooms 15.18 and 17. The lodge
network recedes at regional-detail scale and remains individually readable at 17;
Yosemite Falls/Valley Loop hiking and bike routes retain emphasis. At Golden Gate
Park (37.770,-122.470, zoom 15.18), Botanical Garden and Blue Heron Lake circulation
no longer dominates POIs and lake labels; named perimeter trails remain strong.
The conservative context leaves some central Music Concourse paths emphasized.
For the Mountain Room source tile, 21 path components / 1,565m receive developed
context; 25 components / 9,625m retain hiking presentation. Original road geometry
unions compare exactly equal before/after annotation. Seven path-context tests and
five style/legend tests passed.
