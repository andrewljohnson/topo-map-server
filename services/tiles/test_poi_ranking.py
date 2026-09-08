import copy, json, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
import poi_ranking as r
import national_recreation as recreation

def point(ident,lon,lat=39,kind='summit',height=None):
 p={'id':ident,'name':ident,'kind':kind,'min_zoom':15 if kind=='restroom' else 13}
 if height is not None:p['elevation_m']=height
 return {'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':p}

class RankingTests(unittest.TestCase):
 def test_higher_peak_isolation_ignores_lower_neighbor(self):
  distances=r.isolation([[-120,39],[-120.001,39],[-121,39]],[3000,1000,4000])
  self.assertGreater(distances[0],80);self.assertLess(distances[1],1);self.assertEqual(distances[2],20015)
 def test_equal_heights_do_not_count_as_higher(self):
  self.assertEqual(list(r.isolation([[-120,39],[-120.01,39]],[3000,3000])),[20015,20015])
 def test_hierarchy_is_nested_and_input_order_independent(self):
  entries=[('high',-120,39,100,6),('low',-120.01,39,10,6),('detail',-120.01,39,1,15)]
  ranks=r.hierarchy(entries)
  self.assertEqual(ranks,r.hierarchy(entries[::-1]));self.assertEqual(ranks['high'],6);self.assertGreater(ranks['low'],6);self.assertEqual(ranks['detail'],15)
  for zoom in range(6,14):
   self.assertTrue({k for k,v in ranks.items() if v<=zoom}<={k for k,v in ranks.items() if v<=zoom+1})
 def test_medium_zoom_spacing_admits_neighboring_ridge_without_crowding_overview(self):
  # Dicks and Tallac are about 4.5km apart: distinct useful summits within
  # the same wilderness, held apart too aggressively by 120px at z10.
  entries=[('dicks',-120.1509004,38.9004581,500,9),('tallac',-120.098848,38.9058967,300,10)]
  before=r.hierarchy(entries,120);after=r.hierarchy(entries,120,72)
  self.assertEqual(after['dicks'],9);self.assertEqual(after['tallac'],10)
  self.assertGreater(before['tallac'],after['tallac'])
  self.assertEqual(after,r.hierarchy(entries[::-1],120,72))
 def test_neighbor_buckets_and_date_line_do_not_admit_close_competitors(self):
  for lon_a,lon_b in [(-.001,.001),(179.999,-179.999)]:
   ranks=r.hierarchy([('a',lon_a,39,100,6),('b',lon_b,39,90,6)])
   self.assertEqual(ranks['a'],6);self.assertGreater(ranks['b'],6)
 def test_highest_peak_and_remote_destination_precede_minor_neighbors(self):
  items=[point('high',-120,height=4000),point('low',-120.01,height=2000),point('unknown',-120.02),point('remote shelter',-119,kind='shelter'),point('camp A',-122,kind='campground'),point('camp B',-122.001,kind='campground'),point('toilet',-119,kind='restroom')]
  result={f['properties']['id']:f['properties'] for f in r.rank_features(items)}
  self.assertLess(result['high']['label_minzoom'],result['low']['label_minzoom'])
  self.assertGreaterEqual(result['unknown']['label_minzoom'],11)
  self.assertLess(result['remote shelter']['label_minzoom'],result['camp A']['label_minzoom'])
  self.assertEqual(result['toilet']['label_minzoom'],15)
 def test_atomic_index_keeps_close_zoom_details_in_source_maxzoom(self):
  with tempfile.TemporaryDirectory() as directory:
   target=Path(directory)/'rank.sqlite';items=[point('high',-120,height=4000),point('toilet',-120,kind='restroom')]
   with patch.object(r,'collect_features',return_value=(items,{})):r.build(target)
   self.assertEqual([f['properties']['id'] for f in r.features((-121,38,-119,40),6,target)],['high'])
   result=r.features((-121,38,-119,40),14,target)
   self.assertEqual(len(result),2);self.assertEqual(result[1]['properties']['label_minzoom'],15)
 def test_overview_uses_local_index_without_agency_network(self):
  f=point('high',-120,height=4000);r.rank_features([f]);z=6;x=10;y=24
  with patch.object(recreation,'ranked_features',return_value=[f]),patch.object(recreation,'cell_data',side_effect=AssertionError('overview contacted agency')):
   data=mapbox_vector_tile.decode(recreation.render_tile(z,x,y))['recreation']['features']
   self.assertEqual(len(data),1);self.assertEqual(data[0]['properties']['label_minzoom'],6)
 def test_same_id_generic_detail_merges_rank_instead_of_duplicate(self):
  a=point('nps:1',-120,kind='restroom');a['properties']['name']='Restroom';b=copy.deepcopy(a);b['properties'].update(label_minzoom=15,label_rank=0)
  merged=recreation.dedupe([a,b]);self.assertEqual(len(merged),1);self.assertEqual(merged[0]['properties']['label_rank'],0)
