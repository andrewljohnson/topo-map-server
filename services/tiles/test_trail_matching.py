import copy, json, unittest
from shapely.geometry import LineString
from trail_matching import conflate

def feature(coords, name='', agency='OSM', ident='one', **props):
 return {'id':ident,'geometry':LineString(coords),'properties':{'id':ident,'name':name,'agency':agency,'class':'path',**props}}

class TrailMatchingTest(unittest.TestCase):
 def test_offset_named_copy_merges_metadata(self):
  base=feature([(0,0),(200,0)],'Eagle Trail')
  agency=feature([(0,9),(200,9)],'EAGLE TRL','USFS','two',motorcycle='N')
  result=conflate([base],[agency])
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]['geometry'].wkt,base['geometry'].wkt)
  self.assertEqual(result[0]['properties']['source_count'],2)
  self.assertEqual(result[0]['properties']['motorcycle'],'N')
 def test_unmatched_extension_remains_connected(self):
  result=conflate([feature([(0,0),(100,0)],'Eagle')],[feature([(0,7),(160,7)],'Eagle','USFS','two')])
  self.assertEqual(len(result),2)
  self.assertLess(result[1]['geometry'].length,70)
  self.assertEqual(list(result[1]['geometry'].coords)[0],(100,0))
  self.assertEqual(list(result[1]['geometry'].coords)[-1],(160,7))
 def test_crossing_is_not_a_duplicate(self):
  result=conflate([feature([(0,0),(200,0)])],[feature([(100,-100),(100,100)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2);self.assertAlmostEqual(result[1]['geometry'].length,200)
 def test_nearby_different_names_remain(self):
  result=conflate([feature([(0,0),(200,0)],'Upper')],[feature([(0,8),(200,8)],'Lower','USFS','two')])
  self.assertEqual(len(result),2);self.assertAlmostEqual(result[1]['geometry'].length,200)
 def test_parallel_unnamed_paths_remain_outside_strict_tolerance(self):
  result=conflate([feature([(0,0),(200,0)])],[feature([(0,8),(200,8)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2)
 def test_bridge_and_surface_path_remain(self):
  result=conflate([feature([(0,0),(200,0)],is_bridge=True)],[feature([(0,0),(200,0)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2)
 def test_reverse_digitization_matches(self):
  result=conflate([feature([(0,0),(200,0)])],[feature([(200,1),(0,1)],agency='USFS',ident='two')])
  self.assertEqual(len(result),1)
 def test_agency_only_and_agency_duplicates(self):
  result=conflate([],[feature([(0,0),(200,0)],'Eagle','NPS'),feature([(0,7),(200,7)],'Eagle','USFS','two'),feature([(500,0),(600,0)],'Remote','USFS','three')])
  self.assertEqual(len(result),2);self.assertEqual(result[0]['properties']['source_count'],2)
 def test_switchback_shortcut_not_removed(self):
  result=conflate([feature([(0,0),(100,0),(100,12),(0,12)],'Eagle')],[feature([(0,0),(0,12)],'Eagle','USFS','two')])
  self.assertEqual(len(result),2)
 def test_conflicting_permissions_preserved(self):
  result=conflate([feature([(0,0),(200,0)],motorcycle='no')],[feature([(0,0),(200,0)],agency='MVUM',ident='two',motorcycle='yes')])
  p=result[0]['properties'];self.assertEqual(p['motorcycle'],'no')
  self.assertEqual({r['details']['motorcycle'] for r in json.loads(p['source_records'])},{'no','yes'})
 def test_distinct_road_and_path_remain(self):
  result=conflate([feature([(0,0),(200,0)],**{'class':'track'})],[feature([(0,1),(200,1)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2)

 def test_closed_loop_duplicates_merge(self):
  coords=[(0,0),(100,0),(100,100),(0,100),(0,0)]
  result=conflate([feature(coords,'Loop')],[feature([(x+4,y+4) for x,y in coords],'Loop','USFS','two')])
  self.assertEqual(len(result),1)
 def test_exact_short_duplicate_merges(self):
  result=conflate([feature([(0,0),(2,0)])],[feature([(2,0),(0,0)],agency='USFS',ident='two')])
  self.assertEqual(len(result),1)

 def test_shared_long_route_identity_matches_name_variants(self):
  result=conflate([feature([(0,0),(200,0)],'Pacific Crest National Scenic Trail',route_ref='PCT')],[feature([(0,8),(200,8)],'PACIFIC CREST (PCT)','USFS','two',route_ref='PCT')])
  self.assertEqual(len(result),1)
