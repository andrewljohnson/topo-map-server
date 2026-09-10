import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
from shapely.geometry import LineString, MultiLineString, box
import national_trails as t

class OfficialTrailsTest(unittest.TestCase):
 def setUp(self):t.prepared_agency_features.cache_clear()
 def tearDown(self):t.prepared_agency_features.cache_clear()
 def test_route_names_not_generic_designation(self):
  self.assertEqual(t.route_ref('PACIFIC CREST TRAIL'), 'PCT')
  self.assertEqual(t.route_ref('PCT SAN FRANCISQUITO CYN'), 'PCT')
  self.assertEqual(t.route_ref('PCT CONNECTOR'), '')
  self.assertEqual(t.route_ref('PCT SPUR'), '')
  self.assertEqual(t.route_ref('PCTOWN ROAD'), '')
  self.assertEqual(t.route_ref('Appalachian Trail'), 'AT')
  self.assertEqual(t.route_ref('Trail to Lake'), '')
 def test_vehicle_restrictions_preserved(self):
  f={'properties':{'objectid':9,'name':'Forest Road','seasonal':'Y','motorcycle':'Y','motorcycle_datesopen':'06/01-10/31','passengervehicle':'N'}}
  p=t.properties('mvum_roads',f)
  self.assertEqual(p['kind'],'forest_road');self.assertEqual(p['passengervehicle'],'N')
  self.assertEqual(p['motorcycle_datesopen'],'06/01-10/31');self.assertEqual(p['seasonal'],'Y')
 def test_private_and_snow_paths_excluded(self):
  self.assertIsNone(t.properties('nps',{'properties':{'OPENTOPUBLIC':'No'}}))
  self.assertIsNone(t.properties('usfs',{'properties':{'trail_type':'SNOW'}}))
 def test_clipping_preserves_line_only(self):
  f=t.clipped_feature(LineString([(-2,.5),(2,.5)]),{'id':'a'},box(0,0,1,1),16)
  self.assertEqual(f['geometry'].bounds,(0,.5,1,.5))
 def test_pcta_full_centerline_asset(self):
  features=t.pct_features();self.assertEqual(len(features),94)
  self.assertTrue(all(p['route_ref']=='PCT' for _,p in features))
  self.assertTrue(any(g.bounds[1]<t.project(-120,49)[1] for g,_ in features))
 def test_detail_overview_and_pct_preference(self):
  raw={'id':1,'properties':{'trail_name':'PACIFIC CREST TRAIL','objectid':1},'geometry':{'type':'LineString','coordinates':[[-120,38],[-120,39]]}}
  with patch.object(t,'cell_features',return_value=[raw]) as fetch:
   decoded=mapbox_vector_tile.decode(t.render_tile(5,5,12))
   self.assertFalse(decoded['trails']['features']);self.assertTrue(decoded['routes']['features'])
   self.assertEqual(fetch.call_count,2)
 def test_partial_batches_not_cached(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(t,'CACHE',Path(directory)),patch.object(t,'query',side_effect=[{'objectIds':[1,2]},{'features':[]} ]):
   with self.assertRaises(RuntimeError):t.cell_features('nps',11,340,790)
   self.assertFalse(list(Path(directory).rglob('*.json')))
 def test_persistent_cells_reused(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(t,'CACHE',Path(directory)),patch.object(t,'query',return_value={'objectIds':[]}) as query:
   self.assertEqual(t.cell_features('nps',11,340,790),[])
   self.assertEqual(t.cell_features('nps',11,340,790),[])
   self.assertEqual(query.call_count,1)
 def test_local_namesake_does_not_get_sierra_route_badge(self):
  raw={'id':1,'properties':{'trail_name':'John Muir Trail'},'geometry':{'type':'LineString','coordinates':[[-83.5,35.5],[-83.4,35.5]]}}
  with patch.object(t,'cell_features',return_value=[raw]):
   d=mapbox_vector_tile.decode(t.render_tile(7,34,50))
   self.assertFalse(d['routes']['features'])
 def test_prepared_basemap_preserves_network_without_archive_read(self):
  blob=mapbox_vector_tile.encode({'name':'road','features':[{'id':73,'geometry':LineString([(100,200),(3000,3500)]),'properties':{'name':'Test Trail','class':'path'}}]},default_options={'y_coord_down':True})
  with patch('national_basemap.archive') as archive,patch('national_basemap.normalize_tile',return_value=blob) as normalize:
   archive.return_value.get.return_value=b'' # No surrounding streets in this isolated fixture.
   reference=t.osm_network(14,2724,6264)
   archive.reset_mock();normalize.reset_mock()
   actual=t.osm_network(14,2724,6264,blob)
   archive.assert_not_called();normalize.assert_not_called()
  self.assertEqual(len(actual),1)
  self.assertEqual(actual[0]['properties'],reference[0]['properties']);self.assertEqual(actual[0]['id'],reference[0]['id'])
  self.assertTrue(actual[0]['geometry'].equals_exact(reference[0]['geometry'],0))
 def test_source_geometry_prepared_once_for_adjacent_children(self):
  raw={'id':1,'properties':{'trail_name':'Test Trail','objectid':1},'geometry':{'type':'LineString','coordinates':[[-120.5,38.5],[-119.5,39.5]]}}
  empty=mapbox_vector_tile.encode({'name':'road','features':[]})
  with patch.object(t,'cell_features',return_value=[raw]) as fetch,patch.object(t,'pct_features',return_value=[]),patch.object(t,'properties',wraps=t.properties) as props:
   for x in (2724,2725):t.render_tile(14,x,6264,basemap_tile=empty)
   self.assertEqual(fetch.call_count,4)
   self.assertEqual(props.call_count,4)
 def test_mvum_surface_controls_road_style_not_vehicle_access(self):
  self.assertEqual(t.agency_road_class({'surface':'AC - ASPHALT'}),'unclassified')
  self.assertEqual(t.agency_road_class({'surface':'NAT - NATIVE MATERIAL','passengervehicle':'open'}),'track')
  self.assertEqual(t.agency_road_class({'surface':''}),'track')
 def test_density_context_is_applied_after_full_reference_matching(self):
  geometry=MultiLineString([[(100,200),(150,200)],[(100,400),(150,400)]])
  blob=mapbox_vector_tile.encode({'name':'road','features':[{'id':73,'geometry':geometry,'properties':{'name':'Test Trail','class':'path'}}]},default_options={'y_coord_down':True})
  with patch.object(t,'cell_features',return_value=[]),patch.object(t,'pct_features',return_value=[]),patch.object(t,'conflate',wraps=t.conflate) as matching,patch('path_context.urban_at',side_effect=[True,True,True,False]):
   tile=mapbox_vector_tile.decode(t.render_tile(14,2724,6264,basemap_tile=blob))
  reference=matching.call_args.args[0]
  self.assertEqual(len(reference),1);self.assertEqual(reference[0]['geometry'].geom_type,'MultiLineString')
  network=tile['network']['features'];self.assertEqual(len(network),2)
  self.assertEqual(sum(f['properties'].get('path_context')=='urban' for f in network),1)
 def test_canonical_route_availability_survives_tile_clipping(self):
  empty=mapbox_vector_tile.encode({'name':'road','features':[]})
  remote=LineString([(.1,.1),(.11,.11)])
  for catalog,expected in [([(remote,{'id':'pcta-remote'})],{'PCT'}),([],set())]:
   with patch.object(t,'prepared_agency_features',return_value=()),patch.object(t,'pct_features',return_value=catalog),patch.object(t,'conflate',return_value=[]) as matching:
    t.render_tile(14,2719,6255,basemap_tile=empty)
   self.assertEqual(matching.call_args.kwargs['canonical_routes'],expected)
 def test_bad_tile_rejected(self):
  for args in [(4,0,0),(15,0,0),(8,-1,2),(8,0,256)]:
   with self.assertRaises(ValueError):t.render_tile(*args)
if __name__=='__main__':unittest.main()
