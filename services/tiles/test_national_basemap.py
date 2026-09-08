import gzip
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import mapbox_vector_tile
from pmtiles.tile import Compression,TileType,zxy_to_tileid
from pmtiles.writer import Writer
from shapely.geometry import Point,LineString,Polygon,box
import national_basemap as national


def fixture_tile():
    hole=Polygon([(0,0),(8000,0),(8000,8000),(0,8000),(0,0)],[[(2000,2000),(4000,2000),(4000,4000),(2000,4000),(2000,2000)]])
    inputs=[('earth',box(0,0,8192,8192),{'kind':'earth'}),('water',hole,{'kind':'lake'}),('water',LineString([(0,100),(8000,100)]),{'kind_detail':'stream'}),('roads',LineString([(0,200),(8000,200)]),{'kind':'major_road','kind_detail':'primary','name':'Main Street'}),('roads',LineString([(0,300),(8000,300)]),{'kind':'rail','kind_detail':'rail'}),('buildings',box(400,400,800,800),{'kind':'building'}),('buildings',Point(500,500),{'kind':'address'}),('places',Point(4096,2048),{'kind':'locality','kind_detail':'city','name':'Original','name:en':'English'}),('landcover',box(0,500,1000,900),{'kind':'forest'}),('landuse',box(0,500,1000,900),{'kind':'park'}),('landcover',box(0,500,1000,900),{'kind':'barren'})]
    layers={}
    for layer,geometry,properties in inputs:
        layers.setdefault(layer,[]).append({'geometry':geometry,'properties':properties})
    return mapbox_vector_tile.encode([{'name':name,'features':features} for name,features in layers.items()],default_options={'extents':8192,'y_coord_down':True})


class FakeResponse:
    def __init__(self,status,body,headers):
        self.status=status;self.body=body;self.headers=headers;self.reads=0
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def read(self,_): self.reads+=1;return self.body


class NationalBasemapTests(unittest.TestCase):
    def test_pois_keep_names_zoom_and_square_circle_categories(self):
        features=[{'geometry':Point(100+i*100,200),'properties':props} for i,props in enumerate([
            {'kind':'toilets','min_zoom':14},
            {'kind':'camp_site','name':'Fallen Leaf Campground','min_zoom':12},
            {'kind':'peak','name':'Tallac','min_zoom':13},
            {'kind':'administrative','name':'Duplicate city label'},
            {'kind':'restaurant','name':'Hidden until later','min_zoom':16},
        ])]
        raw=mapbox_vector_tile.encode({'name':'pois','features':features},default_options={'extents':4096,'y_coord_down':True})
        pois=mapbox_vector_tile.decode(national.normalize_tile(raw,14))['poi']['features']
        self.assertEqual(len(pois),3)
        self.assertEqual([(p['properties']['poi_frame'],p['properties']['poi_icon']) for p in pois],[('square','toilet'),('circle','campsite'),('circle','mountain')])
        self.assertEqual(pois[0]['properties']['name'],'')
        self.assertEqual(pois[1]['properties']['name'],'Fallen Leaf Campground')
        self.assertEqual(pois[1]['properties']['min_zoom'],12)

    def test_route_shields_preserve_network_and_road_details(self):
        for network,number,kind in [('US:I','80','interstate'),('US:US','50','us'),('US:CA','89','state'),('US:CA:ElDorado','16','county')]:
            props={'network':network,'shield_text':number,'ref':number,'surface':'gravel','is_bridge':True}
            result=national.road_properties(props)
            self.assertEqual(result['shield_kind'],kind)
            self.assertEqual(result['shield_text'],number)
            self.assertEqual(result['surface'],'gravel')
            self.assertTrue(result['is_bridge'])
        self.assertEqual(national.road_properties({'ref':'NFR 12;NFR 13'})['shield_text'],'NFR 12')
        self.assertEqual(national.road_properties({'ref':'NFR 12'})['shield_kind'],'generic')
        self.assertNotIn('shield_text',national.road_properties({}))

    def test_long_axis_and_round_lake_fallback(self):
        from shapely.affinity import rotate
        world=.5005;center=world*4096*2**10
        lake=rotate(box(center-100,center-400,center+100,center+400),20,origin=(center,center))
        national.lake_axis.cache_clear()
        with patch.object(national,'water_shapes',return_value=[lake]):
            angle,elongated,horizontal_zoom=national.lake_axis(world,world)
            self.assertGreater(horizontal_zoom,5)
            long_zoom=national.lake_axis(world,world,"A Very Long Lake Name")[2]
            self.assertGreater(long_zoom,horizontal_zoom)
            self.assertAlmostEqual(angle,-70,places=1)
            self.assertTrue(elongated)
        national.lake_axis.cache_clear()
        with patch.object(national,'water_shapes',return_value=[Point(center,center).buffer(100)]):
            self.assertEqual(national.lake_axis(world,world),(0.0,False,0.0))
        national.lake_axis.cache_clear()

    def test_lake_label_anchor_name_and_zoom_survive_conversion(self):
        features=[{'geometry':Point(2048,1024),'properties':{'kind':'water','kind_detail':'lake','name':'Original','name:en':'Lake Example','min_zoom':11,'sort_rank':200}}, {'geometry':Point(100,100),'properties':{'kind':'ocean','name':'Ocean'}}, {'geometry':Point(300,300),'properties':{'kind':'water','kind_detail':'lake'}}]
        raw=mapbox_vector_tile.encode({'name':'water','features':features},default_options={'extents':4096,'y_coord_down':True})
        decoded=mapbox_vector_tile.decode(national.normalize_tile(raw,10),default_options={'y_coord_down':True})
        labels=decoded['water_label']['features']
        self.assertEqual(len(labels),1)
        self.assertEqual(labels[0]['geometry']['coordinates'],[2048,1024])
        self.assertEqual(labels[0]['properties'],{'name':'Lake Example','class':'lake','min_zoom':11,'sort_rank':200})
        self.assertEqual(mapbox_vector_tile.decode(national.normalize_tile(raw,9))['water_label']['features'],[])

    def test_real_schema_mapping_preserves_holes_and_tile_orientation(self):
        blob=national.normalize_tile(fixture_tile(),14)
        decoded=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True})
        self.assertEqual(set(decoded),set(national.LAYERS))
        self.assertNotIn('contour',decoded)
        water=decoded['water']['features'][0]['geometry']
        self.assertEqual(water['type'],'Polygon')
        self.assertEqual(len(water['coordinates']),2)
        label=decoded['label']['features'][0]
        self.assertEqual(label['geometry']['coordinates'],[2048,1024])
        self.assertEqual(label['properties'],{'class':'city','name':'English'})
        self.assertEqual(decoded['road']['features'][0]['properties']['class'],'primary')
        for layer in ['land','waterline','building','rail','forest','grass','rock']:
            self.assertEqual(len(decoded[layer]['features']),1,layer)
    def test_missing_tile_encodes_valid_empty_layers(self):
        decoded=mapbox_vector_tile.decode(national.normalize_tile(None,4))
        self.assertTrue(all(not layer['features'] for layer in decoded.values()))
    def test_global_coordinates_include_alaska_hawaii_and_reject_invalid(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(national,'DATA',Path(tmp)), patch.object(national,'archive') as mocked:
            mocked.return_value.get.return_value=None
            for key in [(0,0,0),(10,85,290),(10,62,449),(14,0,0),(14,16383,16383)]:
                national.render_tile(*key)
            self.assertEqual(mocked.return_value.get.call_count,5)
            for key in [(-1,0,0),(15,0,0),(0,1,0),(1,-1,0),(1,0,2)]:
                with self.assertRaises(ValueError): national.render_tile(*key)
            self.assertEqual(mocked.return_value.get.call_count,5)
    def test_actual_pmtiles_directory_lookup_and_persistent_range_cache(self):
        raw=fixture_tile();memory=io.BytesIO();writer=Writer(memory)
        writer.write_tile(zxy_to_tileid(2,1,1),gzip.compress(raw))
        writer.finalize({'tile_type':TileType.MVT,'tile_compression':Compression.GZIP},{'name':'test'})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.pmtiles';path.write_bytes(memory.getvalue());cache=Path(tmp)/'cache'
            source=national.RangeSource(str(path),cache_dir=cache,block_size=128)
            archive=national.Archive(source)
            self.assertEqual(archive.get(2,1,1),raw)
            self.assertIsNone(archive.get(2,3,3))
            reused=national.RangeSource(str(path),cache_dir=cache,block_size=128)
            with patch.object(reused,'_fetch',side_effect=AssertionError('must reuse durable ranges')):
                self.assertEqual(national.Archive(reused).get(2,1,1),raw)
            self.assertGreater(len(list(cache.glob('*.bin'))),1)
    def test_http_range_validation_and_no_full_archive_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=national.RangeSource('https://example.test/archive.pmtiles',cache_dir=tmp,block_size=16,etag='"known"')
            full=FakeResponse(200,b'x'*16,{})
            with patch.object(national,'urlopen',return_value=full):
                with self.assertRaises(ValueError):source.get_bytes(0,8)
            self.assertEqual(full.reads,0,'Reject ignored Range before reading a massive archive')
            wrong=FakeResponse(206,b'x'*16,{'Content-Range':'bytes 16-31/100','ETag':'"known"'})
            with patch.object(national,'urlopen',return_value=wrong):
                with self.assertRaises(ValueError):source.get_bytes(0,8)
            changed=FakeResponse(206,b'x'*16,{'Content-Range':'bytes 0-15/100','ETag':'"changed"'})
            with patch.object(national,'urlopen',return_value=changed):
                with self.assertRaises(ValueError):source.get_bytes(0,8)
            good=FakeResponse(206,b'abcdefghijklmnop',{'Content-Range':'bytes 0-15/100','ETag':'"known"'})
            with patch.object(national,'urlopen',return_value=good) as request:
                self.assertEqual(source.get_bytes(3,5),b'defgh')
                self.assertEqual(request.call_args.args[0].get_header('Range'),'bytes=0-15')
                self.assertEqual(request.call_args.kwargs['timeout'],30)
    def test_transient_http_error_retries_then_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=national.RangeSource('https://example.test/archive.pmtiles',cache_dir=tmp,block_size=16)
            error=HTTPError(source.url,503,'busy',{},None)
            response=FakeResponse(206,b'abcdefghijklmnop',{'Content-Range':'bytes 0-15/100'})
            with patch.object(national,'urlopen',side_effect=[error,response]) as request,patch.object(national.time,'sleep'):
                self.assertEqual(source.get_bytes(0,4),b'abcd')
                self.assertEqual(source.get_bytes(4,4),b'efgh')
                self.assertEqual(request.call_count,2)

if __name__=='__main__':
    unittest.main()
