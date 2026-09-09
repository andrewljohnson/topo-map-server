import unittest
from unittest.mock import patch
from shapely.geometry import shape
import area_tiles

class AreaTileTests(unittest.TestCase):
 def setUp(self):
  self.feature={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[-121,38],[-119,38],[-119,40],[-121,40],[-121,38]]]},'properties':{'id':'forest-1','name':'Example Forest','kind':'forest','bounds':[-121,38,-119,40],'label_center':[-120,39],'min_zoom':5,'priority':1}}
  self.mock=patch.object(area_tiles,'area_data',return_value=([],{'features':[self.feature]}));self.mock.start();area_tiles.index.cache_clear();area_tiles.projected_geometry.cache_clear()
 def tearDown(self):
  self.mock.stop();area_tiles.index.cache_clear();area_tiles.projected_geometry.cache_clear()
 def tile(self,z):
  x,y=area_tiles.project(-120,39);return z,int(x*2**z),int(y*2**z)
 def test_reviewed_anchor_and_properties_survive(self):
  z,x,y=self.tile(12);out=area_tiles.features_for_tile(z,x,y)
  self.assertEqual(len(out),1);f=out[0];self.assertEqual(f['properties']['label_source'],'agency');self.assertEqual(f['properties']['name'],'Example Forest')
  wx,wy=area_tiles.project(-120,39);gx,gy=f['geometry']['coordinates'];self.assertAlmostEqual(gx,4096*(wx*2**z-x));self.assertAlmostEqual(gy,4096*(wy*2**z-y))
 def test_label_is_owned_by_one_tile(self):
  z,x,y=self.tile(12)
  out=[f for dx in (-1,0,1) for dy in (-1,0,1) for f in area_tiles.features_for_tile(z,x+dx,y+dy) if f['geometry']['type']=='Point']
  self.assertEqual(len(out),1)
 def test_coarse_fill_replaced_by_fine_boundary_source(self):
  self.assertTrue(any(f['geometry']['type']=='Polygon' for f in area_tiles.features_for_tile(*self.tile(6))))
  self.assertTrue(all(f['geometry']['type']=='Point' for f in area_tiles.features_for_tile(*self.tile(8))))
 def test_name_dedupe_requires_matching_name_and_location(self):
  x,y=area_tiles.project(-120,39);self.assertTrue(area_tiles.owns_name('Example forest',x,y));self.assertFalse(area_tiles.owns_name('Other Forest',x,y));self.assertFalse(area_tiles.owns_name('Example Forest',*area_tiles.project(-80,39)))
 def test_invalid_catalog_ring_is_repaired_before_clipping(self):
  self.feature['geometry']['coordinates']=[[[-121,38],[-119,40],[-121,40],[-119,38],[-121,38]]]
  self.assertTrue(area_tiles.projected_geometry(0).is_valid)
  out=area_tiles.features_for_tile(*self.tile(6));self.assertTrue(any(f['geometry']['type'] in ('Polygon','MultiPolygon') for f in out))
 def test_early_label_does_not_enter_low_zoom_tiles(self):
  self.assertFalse(any(f['geometry']['type']=='Point' for f in area_tiles.features_for_tile(*self.tile(3))))

if __name__=='__main__':unittest.main()
