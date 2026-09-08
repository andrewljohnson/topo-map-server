import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
import numpy as np
from rasterio.transform import Affine
import national_contours as nc

class NationalContoursTests(unittest.TestCase):
 def test_memory_cache_reuses_immutable_blocks_and_separates_namespaces(self):
  nc._memory_chunk.cache_clear()
  with patch.object(nc,'_load_chunk',side_effect=lambda x,y:(np.ones((4,4),dtype='float32'),{'chunk':[x,y]})) as read:
   with patch.object(nc,'CACHE',Path('/tmp/dem-cache-test-a')):
    first,_=nc.load_chunk(3,4);second,_=nc.load_chunk(3,4)
    self.assertIs(first,second);self.assertEqual(read.call_count,1)
    with self.assertRaises(ValueError):first[0,0]=2
   with patch.object(nc,'CACHE',Path('/tmp/dem-cache-test-b')):nc.load_chunk(3,4)
   self.assertEqual(read.call_count,2)
   for x in range(80):nc.load_chunk(x,4)
   self.assertLessEqual(nc._memory_chunk.cache_info().currsize,64)
  nc._memory_chunk.cache_clear()
 def test_latest_dated_sources(self):
  items=[{'title':f'USGS 1/3 Arc Second n38w123 {date}','downloadURL':f'https://example.gov/n38w123/{date}.tif','sourceId':date} for date in ['20210301','20260324']]
  selected=nc.select_sources(items,10)
  self.assertEqual(len(selected),1);self.assertEqual(selected[0]['id'],'20260324')
 def test_catalog_errors_not_cached(self):
  with tempfile.TemporaryDirectory() as d,patch.object(nc,'CACHE',Path(d)),patch.object(nc,'request_json',side_effect=OSError('network down')):
   with self.assertRaises(OSError):nc.catalog_cell(-123,37,10)
   self.assertFalse(list(Path(d).rglob('*.json')))
 def test_fallback_provenance_and_persistent_reuse(self):
  calls=[]
  def sources(bounds,res):return [{'url':str(res),'resolution_m':res}]
  def read(sources,transform,width,height):
   calls.append(sources[0]['resolution_m']);data=np.full((height,width),100,dtype='float32')
   if sources[0]['resolution_m']==10:data[:height//2]=np.nan
   return data
  with tempfile.TemporaryDirectory() as d,patch.object(nc,'CACHE',Path(d)),patch.object(nc,'CHUNK',16),patch.object(nc,'sources_for_bounds',side_effect=sources),patch.object(nc,'read_sources',side_effect=read):
   data,info=nc.load_chunk(10,10);self.assertTrue(np.isfinite(data).all());self.assertEqual(info['fallback30mPixels'],128);self.assertEqual(info['source10mPixels'],128)
   again,same=nc.load_chunk(10,10);np.testing.assert_equal(data,again);self.assertEqual(info['sha256'],same['sha256']);self.assertEqual(calls,[10,30])
 def test_partial_network_failure_propagates(self):
  def sources(bounds,res):
   if res==30:raise OSError('fallback unavailable')
   return [{'url':'fine'}]
  with tempfile.TemporaryDirectory() as d,patch.object(nc,'CACHE',Path(d)),patch.object(nc,'CHUNK',8),patch.object(nc,'sources_for_bounds',side_effect=sources),patch.object(nc,'read_sources',return_value=np.full((8,8),np.nan,dtype='float32')):
   with self.assertRaises(OSError):nc.load_chunk(0,0)
   self.assertFalse(list(Path(d).rglob('*.npz')))
 def test_missing_coverage_and_aligned_bounded_halos(self):
  def missing(cx,cy):return np.full((nc.CHUNK,nc.CHUNK),np.nan,dtype='float32'),{}
  with patch.object(nc,'load_chunk',side_effect=missing):
   with self.assertRaises(nc.CoverageUnavailable):nc.read_tile_dem(11,330,790)
  def gradient(cx,cy):return np.broadcast_to((np.arange(nc.CHUNK)+cx*nc.CHUNK).astype('float32'),(nc.CHUNK,nc.CHUNK)),{}
  with patch.object(nc,'load_chunk',side_effect=gradient):
   first,t1,_=nc.read_tile_dem(14,2600,6200);second,t2,_=nc.read_tile_dem(14,2601,6200)
   offset=round((t2.c-t1.c)/nc.RESOLUTION);overlap=first.shape[1]-offset
   self.assertGreater(overlap,4);np.testing.assert_array_equal(first[:,offset:],second[:,:overlap])
   coarse,_,_=nc.read_tile_dem(11,330,790);self.assertLess(max(coarse.shape),2200)
 def test_alaska_60m_fallback_is_explicit(self):
  calls=[]
  def sources(bounds,res):
   calls.append(res);return [{'url':str(res),'resolution_m':res}] if res==60 else []
  def read(sources,transform,width,height):return np.full((height,width),42 if sources else np.nan,dtype='float32')
  with tempfile.TemporaryDirectory() as d,patch.object(nc,'CACHE',Path(d)),patch.object(nc,'CHUNK',16),patch.object(nc,'chunk_spec',return_value=(Affine(nc.RESOLUTION,0,-150,0,-nc.RESOLUTION,65),16,16)),patch.object(nc,'sources_for_bounds',side_effect=sources),patch.object(nc,'read_sources',side_effect=read):
   dem,info=nc.load_chunk(0,0);self.assertEqual(calls,[10,30,60]);self.assertEqual(info['fallback60mPixels'],256);self.assertTrue(np.isfinite(dem).all())
 def test_mvt_orientation_feet_and_indices(self):
  z,x,y=14,4705,6245;b=nc.tile_bounds(z,x,y)
  west,north=nc.inverse_mercator(b[0],b[1]);east,south=nc.inverse_mercator(b[2],b[3]);t=Affine((east-west)/32,0,west,0,-(north-south)/32,north)
  dem=np.broadcast_to((np.arange(32)*20*nc.METERS_PER_FOOT)[:,None],(32,32)).copy()
  with tempfile.TemporaryDirectory() as d,patch.object(nc,'CACHE',Path(d)),patch.object(nc,'read_tile_dem',return_value=(dem,t,[])):pbf=nc.render_tile(z,x,y)
  features=mapbox_vector_tile.decode(pbf,default_options={'y_coord_down':True})['contour']['features'];self.assertGreater(len(features),10)
  by={f['properties']['ele_ft']:f for f in features};self.assertEqual(by[100]['properties']['name'],'100 ft');self.assertTrue(by[100]['properties']['index']);self.assertFalse(by[120]['properties']['index'])
  self.assertLess(by[100]['geometry']['coordinates'][0][1],by[300]['geometry']['coordinates'][0][1])
 def test_negative_contours_for_death_valley(self):
  from shapely.geometry import box
  dem=np.broadcast_to((np.arange(16)*20-200)[:,None]*nc.METERS_PER_FOOT,(16,16)).copy()
  lines=list(nc.contour_lines(dem,Affine(1,0,0,0,-1,16),box(0,0,16,16)))
  self.assertTrue(any(feet<0 for feet,line in lines));self.assertFalse(any(feet==0 for feet,line in lines))

if __name__=='__main__':unittest.main()
