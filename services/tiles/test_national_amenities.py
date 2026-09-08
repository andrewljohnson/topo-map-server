import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
import national_amenities as a
class AmenitiesTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.cache=patch.object(a,'CACHE',Path(self.temp.name));self.cache.start()
 def tearDown(self):self.cache.stop();self.temp.cleanup()
 def test_successful_empty_cached_but_failure_not_cached(self):
  with patch.object(a,'fetch',side_effect=RuntimeError('timeout')):
   with self.assertRaises(RuntimeError):a.cell_data(190,397)
  self.assertFalse((a.CACHE/'cells/190/397.json').exists())
  with patch.object(a,'fetch',return_value={'elements':[]}) as fetch:
   self.assertEqual(a.cell_data(190,397)['features'],[])
   a.cell_data(190,397);self.assertEqual(fetch.call_count,1)
 def test_processing_upgrade_reuses_raw_and_keeps_site_badges_in_vector_tile(self):
  x,y=252,355;w,s,e,n=a.bounds(10,x,y)
  raw={'elements':[{'type':'node','id':123,'lon':(w+e)/2,'lat':(s+n)/2,'tags':{'tourism':'camp_site','name':'Camp','toilets':'yes'}}]}
  path=a.CACHE/'cells'/str(x)/(str(y)+'.json');a.atomic_json(path,{'features':[],'bounds':[w,s,e,n]});a.atomic_json(path.with_suffix('.raw.json'),raw)
  with patch.object(a,'fetch',side_effect=AssertionError('must reuse raw extract')):
   result=a.cell_data(x,y)
   self.assertEqual(result['build_version'],a.BUILD_VERSION)
   features=mapbox_vector_tile.decode(a.render_tile(10,x,y))['amenities']['features']
  member=next(f for f in features if f['properties']['kind']=='amenity')
  self.assertEqual(member['properties']['grid_image'],'amenity-grid:campsite,toilet')
  self.assertEqual(member['properties']['facility_location'],'site_only')

 def test_partial_response_retried_not_accepted(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{"elements":[],"remark":"runtime error: timeout"}'
  with patch.object(a,'urlopen',return_value=Response()) as call,patch.object(a.time,'sleep'):
   with self.assertRaises(RuntimeError):a.fetch('query')
   self.assertEqual(call.call_count,3)
 def test_half_open_boundary_and_stable_identifier(self):
  # Longitude 0 is the exact shared edge of two tiles; only eastern tile owns it.
  point={'type':'Feature','geometry':{'type':'Point','coordinates':[0,0]},'properties':{'kind':'group','osm_id':'node/1','icons':['campsite','toilet'],'name':'Camp'}}
  with patch.object(a,'cell_data',return_value={'features':[point]}):
   left=mapbox_vector_tile.decode(a.render_tile(10,511,512))['amenities']['features']
   right=mapbox_vector_tile.decode(a.render_tile(10,512,512))['amenities']['features']
   zoomed=mapbox_vector_tile.decode(a.render_tile(14,8192,8192))['amenities']['features']
  self.assertEqual(left,[]);self.assertEqual(len(right),1)
  self.assertEqual(right[0]['id'],zoomed[0]['id'])
  self.assertEqual(right[0]['properties']['grid_image'],'amenity-grid:campsite,toilet')
  self.assertEqual(right[0]['properties']['grid_rows'],1)
 def test_full_site_extent_refetched(self):
  w,s,e,n=a.bounds(10,190,397)
  polygon={'type':'way','id':1,'tags':{'tourism':'camp_site','name':'Camp'},'geometry':[{'lon':x,'lat':y} for x,y in [(w,s),(e+.05,s),(e+.05,n),(w,n),(w,s)]]}
  raw={'elements':[polygon]}
  with patch.object(a,'fetch',return_value=raw) as fetch:
   a.cell_data(190,397)
  self.assertEqual(fetch.call_count,2)
  self.assertIn(str(e+.051),fetch.call_args.args[0])

 def test_connection_failure_uses_fallback_and_records_provenance(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{"elements":[]}'
  with patch.object(a,'urlopen',side_effect=[ConnectionRefusedError(),Response()]) as call,patch.object(a.time,'sleep'):
   result=a.fetch('query')
  self.assertEqual(call.call_args_list[0].args[0].full_url,a.URL)
  self.assertTrue(call.call_args_list[1].args[0].full_url.startswith(a.FALLBACK_URL+'?data='))
  self.assertEqual(call.call_args_list[1].args[0].get_method(),'GET')
  self.assertEqual(result['_endpoint'],a.FALLBACK_URL)

if __name__=='__main__':unittest.main()
