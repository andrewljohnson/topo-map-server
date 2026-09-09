import unittest
from unittest.mock import patch
from shapely.geometry import shape,LineString,mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree
import path_context as p

class PathContextTests(unittest.TestCase):
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
if __name__=='__main__':unittest.main()
