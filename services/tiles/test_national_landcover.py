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
        z,x,y=14,2748,6334
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

if __name__=='__main__': unittest.main()
