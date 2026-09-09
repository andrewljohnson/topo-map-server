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
