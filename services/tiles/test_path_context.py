import unittest
from unittest.mock import patch
from shapely.geometry import shape,LineString,mapping,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
import path_context as p

class PathContextTests(unittest.TestCase):
 def setUp(self):
  self.developed=patch.object(p,'developed_at',return_value=False).start();self.addCleanup(patch.stopall)
 def tearDown(self):p.urban_at.cache_clear();p.street_index.cache_clear();p.street_mass.cache_clear();p.context_grid.cache_clear()
 def test_sparse_roads_stay_backcountry_dense_street_grid_is_urban(self):
  for count,expected in [(1,False),(7,True)]:
   p.urban_at.cache_clear();p.street_mass.cache_clear();p.context_grid.cache_clear();roads=[LineString([(.5+(i-count//2)*.000002,.49998),(.5+(i-count//2)*.000002,.50002)]) for i in range(count)]
   with patch.object(p,'street_index',return_value=(roads,STRtree(roads))):self.assertEqual(p.urban_at(.5,.5),expected)
 def test_multiline_context_is_scoped_without_geometry_loss(self):
  f={'id':1,'properties':{'class':'path','name':'Example'},'geometry':{'type':'MultiLineString','coordinates':[[[0,0],[100,0]],[[0,200],[100,200]]]}}
  with patch.object(p,'urban_at',side_effect=[True,True,True,False]):out,changed=p.annotate([f],14,100,100)
  self.assertTrue(changed);self.assertEqual(len(out),2);self.assertTrue(unary_union([shape(v['geometry']) for v in out]).equals(shape(f['geometry'])))
  urban=[v for v in out if v['properties'].get('path_context')=='urban'];self.assertEqual(len(urban),1);self.assertEqual(shape(urban[0]['geometry']).bounds,(0,0,100,0));self.assertEqual(urban[0]['properties']['name'],'Example');self.assertNotIn('path_context',f['properties'])
 def test_no_context_queries_for_overviews_or_roads(self):
  road={'geometry':mapping(LineString([(0,0),(100,0)])),'properties':{'class':'residential'}}
  with patch.object(p,'urban_at') as query:
   self.assertEqual(p.annotate([road],12,0,0),([road],False));self.assertEqual(p.annotate([road],11,0,0),([road],False));query.assert_not_called()
 def test_mixed_path_is_conservatively_retained(self):
  f={'geometry':mapping(LineString([(0,0),(100,0)])),'properties':{'class':'path'}}
  with patch.object(p,'urban_at',side_effect=[True,False]):out,changed=p.annotate([f],14,100,100)
  self.assertFalse(changed);self.assertEqual(out,[f])
 def test_urban_paths_do_not_fetch_redundant_building_context(self):
  feature={'geometry':mapping(LineString([(0,0),(100,0)])),'properties':{'class':'footway'}}
  with patch.object(p,'urban_at',return_value=True):
   out,changed=p.annotate([feature],14,100,100)
  self.assertTrue(changed);self.assertEqual(out[0]['properties']['path_context'],'urban');self.developed.assert_not_called()
 def test_building_context_requires_whole_path_and_keeps_named_routes(self):
  feature={'geometry':mapping(LineString([(0,0),(100,0)])),'properties':{'class':'footway'}}
  self.developed.return_value=True
  with patch.object(p,'urban_at',return_value=False):
   out,changed=p.annotate([feature],14,100,100)
   self.assertTrue(changed);self.assertEqual(out[0]['properties']['path_context'],'developed')
   self.assertTrue(shape(out[0]['geometry']).equals(shape(feature['geometry'])))
   for key,value in [('name','Yosemite Falls Trail'),('ref','17E05'),('route_ref','PCT')]:
    route={**feature,'properties':{**feature['properties'],key:value}}
    self.assertEqual(p.annotate([route],14,100,100),([route],False))
   self.developed.side_effect=[True,False]
   self.assertEqual(p.annotate([feature],14,100,100),([feature],False))

class DevelopedContextTests(unittest.TestCase):
 def tearDown(self):p.developed_at.cache_clear();p.building_index.cache_clear()
 def test_invalid_building_rings_are_repaired_before_clipping(self):
  geometry={'type':'Polygon','coordinates':[[[0,0],[200,200],[0,200],[200,0],[0,0]]]}
  self.assertFalse(shape(geometry).is_valid)
  layer={'buildings':{'extent':4096,'features':[{'geometry':geometry,'properties':{}}]}}
  with patch('national_basemap.archive') as archive,patch.object(p.mapbox_vector_tile,'decode',return_value=layer):
   archive.return_value.get.return_value=b'fixture'
   geoms,tree=p.building_index(2631,6352)
  self.assertEqual(len(geoms),2)
  self.assertTrue(all(g.is_valid and g.area>0 for g in geoms))
  self.assertAlmostEqual(sum(g.area for g in geoms)*(4096*16384)**2,20000,places=3)
 def test_isolated_hut_is_not_resort_but_building_group_is(self):
  metre=1/40075016.686
  buildings=[box(.5+(i*30-40)*metre,.5-10*metre,.5+(i*30-20)*metre,.5+10*metre) for i in range(3)]
  for geoms,expected in [(buildings[:1],False),(buildings,True)]:
   p.developed_at.cache_clear()
   with patch.object(p,'building_index',side_effect=lambda x,y:(geoms,STRtree(geoms)) if (x,y)==(8192,8192) else ([],STRtree([]))):
    self.assertEqual(p.developed_at(.5,.5),expected)

if __name__=='__main__':unittest.main()
