import unittest, tempfile
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
from shapely.geometry import LineString, Polygon, box, shape
import national_waterways as waterways
import tile_service

class WaterwayTests(unittest.TestCase):
    def test_flags(self):
        for value in (False, 'no', 'false', 0):
            self.assertEqual(waterways.flow_properties({'intermittent':value, 'seasonal':value})['flow'], 'perennial')
        for value in (True, 'yes', 1):
            self.assertEqual(waterways.flow_properties({'intermittent':value})['flow'], 'intermittent')
        result=waterways.flow_properties({'seasonal':'summer','intermittent':True})
        self.assertEqual(result['flow'],'seasonal')
        self.assertEqual(result['seasonal_value'],'summer')
    def test_missing_tags_unknown(self):
        self.assertEqual(waterways.flow_properties({})['flow'],'unknown')
        self.assertEqual(waterways.osm_id((2<<44)|12345),12345)
        self.assertIsNone(waterways.osm_id((3<<44)|12345))
    def test_lake_clip_and_island_preserved(self):
        lake=Polygon([(100,100),(300,100),(300,300),(100,300)], [[(180,180),(220,180),(220,220),(180,220)]])
        raw=mapbox_vector_tile.encode([{'name':'water','features':[
          {'geometry':lake,'properties':{'kind':'lake'}},
          {'geometry':LineString([(0,200),(400,200)]),'properties':{'name':'Creek','intermittent':True,'kind_detail':'stream'}}]}], default_options={'extents':4096,'y_coord_down':True})
        features=mapbox_vector_tile.decode(waterways.normalize_tile(raw,14),default_options={'y_coord_down':True})['waterline']['features']
        self.assertEqual(len(features),1)
        self.assertEqual(features[0]['properties']['flow'],'intermittent')
        geometry=shape(features[0]['geometry'])
        self.assertEqual(geometry.intersection(lake).length,0)
        self.assertEqual(geometry.length,240)
    def test_fully_submerged_line_removed(self):
        raw=mapbox_vector_tile.encode([{'name':'water','features':[
          {'geometry':box(0,0,400,400),'properties':{'kind':'lake'}},
          {'geometry':LineString([(100,100),(200,200)]),'properties':{'kind':'river'}}]}])
        self.assertEqual(mapbox_vector_tile.decode(waterways.normalize_tile(raw,14))['waterline']['features'],[])
    def test_metadata_and_zoom(self):
        with patch.object(tile_service,'MODE','national'):
            spec=tile_service.metadata()['tilesets']['waterways']
            self.assertEqual(spec['datasetId'],waterways.DATASET_ID)
            self.assertTrue(tile_service.valid_tile(6,10,20,'waterways'))
            self.assertFalse(tile_service.valid_tile(5,10,20,'waterways'))
            self.assertFalse(tile_service.valid_tile(15,10,20,'waterways'))

    def test_tag_batches_deduplicate_and_cache(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(waterways,'CACHE',Path(temp)), patch('national_amenities.fetch') as fetch:
            fetch.return_value={'elements':[{'type':'way','id':123,'tags':{'intermittent':'yes'}}]}
            first=waterways.stream_tags([123,123,124])
            second=waterways.stream_tags([123,124])
            self.assertEqual(first,second)
            self.assertEqual(first[123]['intermittent'],'yes')
            self.assertEqual(first[124],{})
            fetch.assert_called_once()
            self.assertIn('way(id:123,124)',fetch.call_args[0][0])
    def test_failed_fetch_does_not_cache(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(waterways,'CACHE',Path(temp)), patch('national_amenities.fetch',side_effect=RuntimeError('upstream unavailable')):
            with self.assertRaises(RuntimeError): waterways.stream_tags([123])
            self.assertFalse(list(Path(temp).rglob('123.json')))
    def test_original_way_tag_join(self):
        raw=mapbox_vector_tile.encode([{'name':'water','features':[{'id':(2<<44)|123,'geometry':LineString([(0,0),(100,100)]),'properties':{'name':'Example','kind':'stream'}}]}])
        result=mapbox_vector_tile.decode(waterways.normalize_tile(raw,14,{123:{'seasonal':'spring','waterway':'stream','name':'Renamed'}}))['waterline']['features'][0]['properties']
        self.assertEqual(result['flow'],'seasonal')
        self.assertEqual(result['seasonal_value'],'spring')
        self.assertEqual(result['name'],'Example')

class CachedEnrichmentConcurrencyTests(unittest.TestCase):
    def test_cached_tags_do_not_wait_for_unrelated_enrichment_writer(self):
        import json
        with tempfile.TemporaryDirectory() as tmp,patch.object(waterways,'CACHE',Path(tmp)),patch.object(waterways.fcntl,'flock',side_effect=AssertionError('cached read acquired writer lock')):
            path=Path(tmp)/'ways'/'0'/'123.json';path.parent.mkdir(parents=True);path.write_text(json.dumps({'tags':{'waterway':'stream','intermittent':'yes'}}))
            self.assertEqual(waterways.stream_tags([123,123])[123]['intermittent'],'yes')
