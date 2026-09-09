import unittest
from mapbox_vector_tile.Mapbox import vector_tile_pb2 as pb
import mapbox_vector_tile as mvt
from shapely.geometry import LineString
from benchmark_overviews import combine_native
class NativeCompositionTests(unittest.TestCase):
 def test_preserves_wire_geometry_properties_ids_and_buffers(self):
  blob=mvt.encode({'name':'roads','features':[{'id':73,'geometry':LineString([(-64,3),(4200,4097)]),'properties':{'name':'Test','min_zoom':10}}]},default_options={'extents':4096,'y_coord_down':True})
  combined=pb.tile();combined.ParseFromString(combine_native([('osm',blob),('trails',blob)]))
  reference=pb.tile();reference.ParseFromString(blob)
  self.assertEqual([l.name for l in combined.layers],['osm__roads','trails__roads'])
  for layer in combined.layers:
   layer.name='roads';self.assertEqual(layer.SerializeToString(),reference.layers[0].SerializeToString())
if __name__=='__main__':unittest.main()
