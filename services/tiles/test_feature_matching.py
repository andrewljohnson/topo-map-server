import unittest, json
from feature_matching import name_key,match_reason,merge_into
def point(name,kind='campground',lon=-120,**props):
 return {'geometry':{'type':'Point','coordinates':[lon,39]},'properties':{'id':name+str(lon),'name':name,'kind':kind,**props}}
class MatchingTests(unittest.TestCase):
 def test_alias_accents_and_suffix(self):
  self.assertEqual(name_key('Mt. Ádams Camp Ground','campground'),name_key('Mount Adams','campground'))
  self.assertTrue(match_reason(point('Fallen Leaf'),point('Fallen Leaf Campground')))
 def test_semantics_distance_generic_and_loops(self):
  for a,b in [(point('Campground'),point('Campground')),(point('Bayview'),point('Bayview','trailhead')),(point('Loop A'),point('Loop B')),(point('Fallen Leaf'),point('Fallen Leaf',lon=-120.1))]:self.assertIsNone(match_reason(a,b))
 def test_source_provenance_and_conflicts(self):
  a,b=point('Fallen Leaf',ridb_id='1',water='Yes'),point('Fallen Leaf Campground',lon=-120.005,ridb_id='1',water='Seasonal',phone='555')
  self.assertEqual(match_reason(a,b),'ridb_id');merge_into(a,b,'ridb_id')
  self.assertEqual(a['properties']['water'],'Yes');self.assertEqual(a['properties']['phone'],'555');self.assertEqual(len(json.loads(a['properties']['source_records'])),2)

 def test_ambiguous_import_is_not_resolved_again_by_a_partial_viewport(self):
  a=point('Example Peak','summit',match_ambiguous=True,geonames_id='9')
  self.assertIsNone(match_reason(a,point('Example Peak','summit',gnis_id='1')))
  self.assertEqual(match_reason(a,point('Other Name','summit',geonames_id='9')),'geonames_id')

 def test_landform_anchors_have_more_tolerance_than_water_points(self):
  self.assertTrue(match_reason(point('Cadillac Mountain','summit'),point('Cadillac Mountain','summit',lon=-120.003)))
  self.assertTrue(match_reason(point('Washington Column','summit'),point('Washington Column','rock',lon=-120.001)))
  self.assertIsNone(match_reason(point('Iron Spring','spring'),point('Iron Spring','spring',lon=-120.003)))
  self.assertIsNone(match_reason(point('Mountain A','summit',gnis_id='1'),point('Mountain A','summit',gnis_id='2')))
 def test_date_line_matching_uses_the_short_distance(self):
  self.assertTrue(match_reason(point('Example Mountain','summit',lon=179.9999),point('Example Mountain','summit',lon=-179.9999)))
