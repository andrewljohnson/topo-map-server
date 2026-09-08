import unittest,tempfile
from unittest.mock import patch
from pathlib import Path
import numpy as np
import national_dem as dem
import tile_service as tiles

class RawDemTests(unittest.TestCase):
 def test_lossless_samples_include_negative_and_high_elevations(self):
  values=np.array([[-430.125,0,1/256],[8848.75,-10.5,127.99609375]],dtype='float32')
  np.testing.assert_array_equal(dem.decode_png(dem.encode_png(values)),values)
  with self.assertRaises(ValueError):dem.encode_png(np.array([[np.nan]],dtype='float32'))
 def test_global_fallback_reconstructs_heights_not_rgb(self):
  values=np.tile(np.linspace(250,260,256,dtype='float32'),(256,1))
  with tempfile.TemporaryDirectory() as tmp,patch.object(dem,'CACHE',Path(tmp)),patch.object(dem,'global_dem',return_value=values),patch.object(dem.usgs,'read_tile_dem',side_effect=dem.usgs.CoverageUnavailable('no coverage')):
   result=dem.decode_png(dem.render_tile(12,687,1583))
   self.assertEqual(result.shape,(512,512));self.assertTrue(np.isfinite(result).all())
   self.assertLess(float(np.max(np.abs(np.diff(result[256])))),.025)
   self.assertAlmostEqual(float(result.min()),250,places=2);self.assertAlmostEqual(float(result.max()),260,places=2)
 def test_native_errors_are_retryable_not_permanent_coarse_tiles(self):
  with patch.object(dem.usgs,'read_tile_dem',side_effect=TimeoutError('upstream unavailable')),patch.object(dem,'global_dem') as fallback:
   with self.assertRaises(TimeoutError):dem.render_tile(12,687,1583)
   fallback.assert_not_called()
 def test_cache_stores_raw_png_and_stops_national_contour_requests(self):
  payload=dem.encode_png(np.ones((8,8),dtype='float32')*1234)
  with tempfile.TemporaryDirectory() as tmp,patch.object(tiles,'MODE','national'),patch.object(tiles,'DATA',Path(tmp)),patch.object(dem,'render_tile',return_value=payload) as render:
   self.assertEqual(tiles.tile_bytes(12,687,1583,tileset='dem'),payload)
   self.assertEqual(tiles.tile_bytes(12,687,1583,tileset='dem'),payload);render.assert_called_once()
   self.assertNotIn('contours',tiles.metadata()['tilesets']);self.assertFalse(tiles.valid_tile(12,687,1583,'contours'))
   self.assertFalse(tiles.valid_tile(14,2748,6332,'dem'))

 def test_overview_preserves_native_samples_without_download_inflation(self):
  values=np.ones((256,256),dtype='float32')*321.125
  with tempfile.TemporaryDirectory() as tmp,patch.object(dem,'CACHE',Path(tmp)),patch.object(dem,'global_dem',return_value=values):
   np.testing.assert_array_equal(dem.decode_png(dem.render_tile(8,48,99)),values)
