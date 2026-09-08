import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
from shapely.geometry import box,mapping,shape,LineString,GeometryCollection
import national_boundaries as b
import tile_service as server

class BoundaryTests(unittest.TestCase):
 def feature(self,geom):return {'type':'Feature','geometry':mapping(geom),'properties':{'UNIT_CODE':'test','UNIT_NAME':'Test Park'}}
 def test_interior_tile_has_fill_without_fake_outline(self):
  z,x,y=10,170,390;w,s,e,n=b.bounds(z,x,y)
  features=b.outline_features(self.feature(box(w-1,s-1,e+1,n+1)),'park',z,x,y)
  self.assertTrue(features)
  self.assertTrue(all(f['geometry'].geom_type=='Polygon' for f in features))
 def test_clipped_actual_boundary_and_identifiers(self):
  z,x,y=10,170,390;w,s,e,n=b.bounds(z,x,y)
  features=b.outline_features(self.feature(box((w+e)/2,s-1,e+1,n+1)),'park',z,x,y)
  self.assertEqual({f['geometry'].geom_type for f in features},{'LineString','Polygon'})
  for f in features:
   self.assertEqual(f['properties']['id'],'park-test')
   self.assertLessEqual(f['geometry'].bounds[2],(x+1+8/512)/2**z+1e-12)
 def test_missing_source_does_not_cache_empty(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'CACHE',Path(d)),patch.object(b,'query',return_value={'features':[]}):
   with self.assertRaises(RuntimeError):b.object_data('park',1)
   self.assertFalse((Path(d)/'objects/park/1.json').exists())
 def test_valid_empty_id_response_is_cached(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'CACHE',Path(d)),patch.object(b,'query',return_value={'objectIds':[]}) as q:
   self.assertEqual(b.cell_ids('park',40,90),[])
   self.assertEqual(b.cell_ids('park',40,90),[])
   self.assertEqual(q.call_count,1)
 def test_arcgis_explicit_null_ids_is_empty(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'CACHE',Path(d)),patch.object(b,'query',return_value={'objectIds':None}):
   self.assertEqual(b.cell_ids('forest',40,90),[])
 def test_missing_ids_is_failure(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'CACHE',Path(d)),patch.object(b,'query',return_value={}):
   with self.assertRaises(RuntimeError):b.cell_ids('park',40,90)
 def test_mvt_and_service_metadata(self):
  with patch.object(b,'cell_ids',return_value=[]):self.assertEqual(mapbox_vector_tile.decode(b.render_tile(8,40,90))['areas']['features'],[])
  with patch.object(server,'MODE','national'):
   self.assertTrue(server.valid_tile(8,40,90,'boundaries'))
   self.assertFalse(server.valid_tile(7,40,90,'boundaries'))
   self.assertEqual(server.metadata()['tilesets']['boundaries']['datasetId'],b.DATASET_ID)

 def test_duplicate_wilderness_stroke_keeps_distinct_branch(self):
  park=LineString([(0,0),(3000,0)])
  line=LineString([(0,2),(2000,2),(2000,1000)])
  result=b.dedupe_outline(line,park,park,1,'wilderness')
  self.assertAlmostEqual(result.length,995)
  self.assertTrue(result.intersects(LineString([(1900,500),(2100,500)])))
 def test_coarse_forest_shared_run_removed_but_crossing_retained(self):
  park=LineString([(0,0),(4000,0)])
  shared=LineString([(0,120),(3000,120),(3000,1500)])
  result=b.dedupe_outline(shared,park,park,1,'forest')
  self.assertAlmostEqual(result.length,1250)
  crossing=LineString([(2000,-1500),(2000,1500)])
  result=b.dedupe_outline(crossing,GeometryCollection(),park,1,'forest')
  self.assertEqual(result,crossing)
 def test_distinct_nearby_wilderness_and_distant_forest_retained(self):
  park=LineString([(0,0),(4000,0)])
  for kind,offset in [('wilderness',100),('forest',300)]:
   line=LineString([(0,offset),(4000,offset)])
   self.assertEqual(b.dedupe_outline(line,park,park,1,kind),line)
 def test_deduplication_does_not_remove_designation_fill(self):
  z,x,y=10,170,390;w,s,e,n=b.bounds(z,x,y)
  feature=self.feature(box((w+e)/2,s-1,e+1,n+1))
  result=b.outline_features(feature,'park',z,x,y,GeometryCollection())
  self.assertTrue(result)
  self.assertTrue(all(f['geometry'].geom_type=='Polygon' for f in result))

 def test_adjacent_tiles_reuse_matching_before_clipping(self):
  b.prepared_cell.cache_clear()
  with patch.object(b,'cell_ids',return_value=[]) as ids:
   b.render_tile(12,640,1440)
   b.render_tile(12,641,1440)
   self.assertEqual(ids.call_count,3)
  b.prepared_cell.cache_clear()
