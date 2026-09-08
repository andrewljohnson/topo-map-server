import unittest
import mapbox_vector_tile as mvt
import numpy as np
from shapely.geometry import box,LineString,Point,shape
from build import merge_tiles,decode_png,encode_png
class PackingTests(unittest.TestCase):
 def tile(self,geometry):
  return mvt.encode({'name':'test','features':[{'id':7,'geometry':geometry,'properties':{'name':'continuous'}}]},default_options={'extents':4096,'y_coord_down':True})
 def test_polygon_and_line_seams(self):
  for geometry in (box(0,0,4096,4096),LineString([(0,2048),(4096,2048)])):
   result,_=merge_tiles([('osm',0,0,self.tile(geometry)),('osm',1,0,self.tile(geometry))])
   layer=mvt.decode(result,default_options={'y_coord_down':True})['osm__test']
   self.assertEqual(layer['extent'],16384);self.assertEqual(len(layer['features']),1)
   f=layer['features'][0];self.assertEqual(f['id'],7);self.assertEqual(f['properties']['name'],'continuous')
   g=shape(f['geometry']);self.assertEqual(g.bounds[2],8192)
   self.assertEqual(g.geom_type,geometry.geom_type)
   if geometry.geom_type=='Polygon':self.assertEqual(g.area,2*4096*4096)
 def test_distinct_points_stay_points(self):
  result,_=merge_tiles([('osm',0,0,self.tile(Point(20,30))),('osm',1,0,self.tile(Point(20,30)))])
  features=mvt.decode(result)['osm__test']['features']
  self.assertEqual(len(features),2);self.assertTrue(all(f['geometry']['type']=='Point' for f in features))
 def test_source_namespaces(self):
  result,_=merge_tiles([(source,0,0,self.tile(Point(20,30))) for source in ('osm','recreation')])
  self.assertEqual(set(mvt.decode(result)),{'osm__test','recreation__test'})
 def test_dem_mosaic_lossless(self):
  rows,cols=np.indices((1024,1024));values=(1000+rows/256+cols/128).astype('float32')
  np.testing.assert_array_equal(decode_png(encode_png(values)),values)
if __name__=='__main__':unittest.main()
