import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import mapbox_vector_tile
from shapely.geometry import box
import tile_service as tiles
import national_basemap as base
import national_contours as contours

class NationalServiceTests(unittest.TestCase):
    def test_national_metadata_and_coordinates(self):
        with patch.object(tiles,'MODE','national'):
            meta=tiles.metadata()
            self.assertEqual(meta['name'],'United States');self.assertEqual(meta['minZoom'],0)
            for lon,lat in [(-122,38),(-150,61),(-158,21)]:
                x,y=(int(v*4096) for v in tiles.project(lon,lat))
                self.assertTrue(tiles.valid_tile(12,x,y))
            self.assertFalse(tiles.valid_tile(10,0,0,'contours'))
            self.assertNotEqual(meta['tilesets']['osm']['datasetId'],meta['tilesets']['dem']['datasetId'])
    def test_on_demand_result_is_cached(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(tiles,'MODE','national'),patch.object(tiles,'DATA',Path(tmp)),patch.object(base,'render_tile',return_value=b'generated-vector') as render:
            self.assertEqual(tiles.tile_bytes(12,655,1583),b'generated-vector')
            self.assertEqual(tiles.tile_bytes(12,655,1583),b'generated-vector')
            render.assert_called_once()
    def test_only_confirmed_open_water_gets_empty_contours(self):
        empty=mapbox_vector_tile.encode([{'name':'land','features':[]}])
        land=mapbox_vector_tile.encode([{'name':'land','features':[{'geometry':box(0,0,4096,4096),'properties':{}}]}])
        with tempfile.TemporaryDirectory() as tmp,patch.object(tiles,'MODE','national'),patch.object(contours,'CACHE',Path(tmp)),patch.object(contours,'render_tile',side_effect=contours.CoverageUnavailable('No samples')):
            with patch.object(base,'render_tile',return_value=empty):
                result=mapbox_vector_tile.decode(tiles.render_contour_tile(14,2620,6330))
                self.assertEqual(result['contour']['features'],[])
            with patch.object(base,'render_tile',return_value=land):
                with self.assertRaises(contours.CoverageUnavailable):tiles.render_contour_tile(14,2620,6330)

if __name__=='__main__':unittest.main()
