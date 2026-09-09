import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mapbox_vector_tile
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
import national_landcover as lc

class LandcoverTests(unittest.TestCase):
    def test_categories_and_water_mask(self):
        pixels=np.array([[42]*6+[11]*2]*4+[[95]*6+[0]*2]*4,dtype='uint8')
        features=lc.vector_features(pixels,(0,0,8,8))
        self.assertEqual({f['properties']['class'] for f in features},{'forest','wetland'})
        self.assertEqual(sum(f['geometry'].area for f in features),48)
        self.assertTrue(all(f['properties']['year']==2024 for f in features))

    def test_outside_coverage_never_requests_network(self):
        with patch.object(lc,'fetch_raster',side_effect=AssertionError('network')):
            # Anchorage and Honolulu.
            for xyz in [(10,85,288),(10,65,449)]:
                self.assertEqual(mapbox_vector_tile.decode(lc.render_tile(*xyz))['landcover']['features'],[])

    def test_bad_coordinate(self):
        for xyz in [(5,0,0),(15,0,0),(6,64,0),(6,0,-1)]:
            with self.assertRaises(ValueError): lc.render_tile(*xyz)

    def test_raw_cache_and_tile_round_trip(self):
        z,x,y=13,1374,3167
        bbox=lc.tile_bounds(z,x,y)
        size=max(16,min(256,__import__('math').ceil((bbox[2]-bbox[0])/30)))
        values=np.full((size,size),42,dtype='uint8')
        with MemoryFile() as mem:
            with mem.open(driver='GTiff',width=size,height=size,count=1,dtype='uint8',crs='EPSG:3857',transform=from_bounds(*bbox,size,size)) as ds:
                ds.write(values,1)
            data=mem.read()
        with tempfile.TemporaryDirectory() as d, patch.object(lc,'CACHE',Path(d)), patch.object(lc,'fetch_raster',return_value=data) as fetch:
            first=lc.render_tile(z,x,y); second=lc.render_tile(z,x,y)
            self.assertEqual(first,second); self.assertEqual(fetch.call_count,1)
            layer=mapbox_vector_tile.decode(first)['landcover']
            self.assertEqual(layer['features'][0]['properties']['subclass'],'evergreen')
            coordinates=layer['features'][0]['geometry']['coordinates'][0]
            self.assertEqual({tuple(v) for v in coordinates},{(0,0),(4096,0),(4096,4096),(0,4096)})

    def test_batch_slices_adjacent_children_and_fetches_once(self):
        size=82
        pixels=np.full((size*16,size*16),42,dtype='uint8')
        pixels[:size,size:2*size]=95
        with MemoryFile() as mem:
            with mem.open(driver='GTiff',width=size*16,height=size*16,count=1,dtype='uint8',
                          transform=from_bounds(*lc.tile_bounds(10,170,391),size*16,size*16)) as ds:
                ds.write(pixels,1)
            data=mem.read()
        lc.batch_values.cache_clear()
        try:
            with tempfile.TemporaryDirectory() as d, patch.object(lc,'CACHE',Path(d)), patch.object(lc,'fetch_raster',return_value=data) as fetch:
                for x,expected in [(2720,42),(2721,95),(2720,42)]:
                    blob=lc.raster(14,x,6256,lc.tile_bounds(14,x,6256),size)
                    with MemoryFile(blob) as mem,mem.open() as ds:
                        self.assertTrue(np.all(ds.read(1)==expected))
                self.assertEqual(fetch.call_count,1)
                self.assertEqual(fetch.call_args.args,(lc.tile_bounds(10,170,391),1312))
        finally: lc.batch_values.cache_clear()

    def test_transient_timeout_retries_but_does_not_cache_failure(self):
        from urllib.error import URLError
        with patch.object(lc,'urlopen',side_effect=URLError('timeout')) as fetch,patch.object(lc.time,'sleep'):
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'failed.tif'
                with self.assertRaises(URLError): lc.cached_raster(path,(0,0,1,1),16)
                self.assertFalse(path.exists())
                self.assertEqual(fetch.call_count,4)

if __name__=='__main__': unittest.main()
