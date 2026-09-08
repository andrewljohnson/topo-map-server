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
 def test_direct_recreation_preserves_fine_coordinates_and_later_zoom_details(self):
  import math,copy
  import national_recreation as recreation
  from unittest.mock import patch
  def point(u,v,ident):
   lon=u/16384*360-180;lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*v/16384))))
   return {'geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'id':ident,'name':ident,'min_zoom':15,'label_minzoom':14,'rank_family':'natural'}}
  # Include points on internal child seams and a point outside this parent.
  features=[point(2724.25,6264.75,'inside'),point(2725,6265,'seam'),point(2727.9,6267.9,'edge'),point(2728.2,6264.5,'outside')]
  before=copy.deepcopy(features)
  with patch.object(recreation,'prepare_cell',return_value=features) as prepare:
   child_tiles=[('recreation',dx,dy,recreation.render_tile(14,2724+dx,6264+dy)) for dy in range(4) for dx in range(4)]
   legacy,_=merge_tiles(child_tiles)
   parent=recreation.render_tile(12,681,1566,detail_zoom=14,extent=16384,prepared=features)
   direct,_=merge_tiles([('recreation',None,None,parent)])
  import json
  canonical=lambda b:sorted(json.dumps(f,sort_keys=True) for f in mvt.decode(b)['recreation__recreation']['features'])
  self.assertEqual(canonical(legacy),canonical(direct));self.assertEqual(len(canonical(direct)),3)
  self.assertEqual(features,before)
 def test_source_namespaces(self):
  result,_=merge_tiles([(source,0,0,self.tile(Point(20,30))) for source in ('osm','recreation')])
  self.assertEqual(set(mvt.decode(result)),{'osm__test','recreation__test'})
 def test_dem_mosaic_lossless(self):
  rows,cols=np.indices((1024,1024));values=(1000+rows/256+cols/128).astype('float32')
  np.testing.assert_array_equal(decode_png(encode_png(values)),values)
if __name__=='__main__':unittest.main()
