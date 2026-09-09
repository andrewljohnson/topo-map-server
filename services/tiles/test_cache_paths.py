import json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cache_paths import working_path
import national_basemap as basemap
import national_boundaries as boundaries
import national_amenities as amenities
import national_waterways as waterways

class WorkingSourceCacheTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'data';self.root.mkdir();self.scratch=self.root/'publication/combined/test/spool/detail-0/raw'
  self.env=patch.dict(os.environ,TILE_DATA_DIR=str(self.root),TOPO_SCRATCH_ROOT=str(self.scratch));self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def test_existing_sources_win_and_disposable_cleanup_preserves_them(self):
  old=self.root/'ranges/old.bin';old.parent.mkdir();old.write_bytes(b'original')
  new=self.root/'ranges/new.bin';redirect=working_path(new);redirect.parent.mkdir(parents=True);redirect.write_bytes(b'new')
  self.assertEqual(working_path(old),old);self.assertEqual(working_path(new),redirect);self.assertEqual(working_path(redirect),redirect)
  self.assertFalse(new.exists());shutil.rmtree(self.scratch);self.assertEqual(old.read_bytes(),b'original')
 def test_normal_server_and_external_cache_paths_are_unchanged(self):
  external=Path(self.temp.name)/'explicit-cache/file';self.assertEqual(working_path(external),external)
  path=self.root/'ranges/new.bin'
  with patch.dict(os.environ,TOPO_SCRATCH_ROOT=''):self.assertEqual(working_path(path),path)
 def test_range_reader_reuses_retained_blocks_and_spools_new_blocks(self):
  cache=self.root/'national-basemap/ranges/source';cache.mkdir(parents=True);(cache/'000000000000.bin').write_bytes(b'abcd')
  source=basemap.RangeSource(url='https://example.invalid/archive',cache_dir=cache,block_size=4)
  with patch.object(source,'_fetch',return_value=b'efgh') as fetch:self.assertEqual(source.get_bytes(0,8),b'abcdefgh');self.assertEqual(fetch.call_count,1)
  self.assertFalse((cache/'000000000001.bin').exists());self.assertEqual(working_path(cache/'000000000001.bin').read_bytes(),b'efgh')
  second=basemap.RangeSource(url='https://example.invalid/archive',cache_dir=cache,block_size=4)
  with patch.object(second,'_fetch',side_effect=AssertionError('must reuse complete spool')):self.assertEqual(second.get_bytes(0,8),b'abcdefgh')
 def test_archive_decode_is_identical_with_disposable_or_persistent_ranges(self):
  import gzip,io
  from pmtiles.writer import Writer
  from pmtiles.tile import zxy_to_tileid,TileType,Compression
  from test_national_basemap import fixture_tile
  memory=io.BytesIO();writer=Writer(memory);raw=fixture_tile();writer.write_tile(zxy_to_tileid(2,1,1),gzip.compress(raw));writer.finalize({'tile_type':TileType.MVT,'tile_compression':Compression.GZIP},{'name':'fixture'})
  archive=self.root/'fixture.pmtiles';archive.write_bytes(memory.getvalue());old_cache=self.root/'ranges/retained';new_cache=self.root/'ranges/new'
  with patch.dict(os.environ,TOPO_SCRATCH_ROOT=''):
   original=basemap.Archive(basemap.RangeSource(str(archive),cache_dir=old_cache,block_size=128)).get(2,1,1)
  retained={p:p.read_bytes() for p in old_cache.glob('*.bin')}
  candidate=basemap.Archive(basemap.RangeSource(str(archive),cache_dir=new_cache,block_size=128)).get(2,1,1)
  self.assertEqual(basemap.normalize_tile(original,2),basemap.normalize_tile(candidate,2));self.assertFalse(new_cache.exists())
  self.assertTrue(list((self.scratch/'source-cache/ranges/new').glob('*.bin')))
  self.assertEqual(retained,{p:p.read_bytes() for p in old_cache.glob('*.bin')})
 def test_agency_json_spools_only_new_records(self):
  existing=self.root/'national-boundaries/old.json';existing.parent.mkdir();existing.write_text('{"id":1}')
  self.assertEqual(boundaries.cached(existing,lambda: self.fail('reused input fetched')),{'id':1})
  new=self.root/'national-boundaries/new.json';self.assertEqual(boundaries.cached(new,lambda:{'id':2}),{'id':2});self.assertFalse(new.exists())
  self.assertEqual(boundaries.cached(new,lambda:self.fail('spool fetched twice')),{'id':2})
 def test_amenity_cell_keeps_raw_and_derived_records_together_in_spool(self):
  cache=self.root/'national-amenities/v1'
  with patch.object(amenities,'CACHE',cache),patch.object(amenities,'fetch',return_value={'elements':[]}) as fetch:
   first=amenities.cell_data(190,397);second=amenities.cell_data(190,397);self.assertEqual(first,second);self.assertEqual(fetch.call_count,1)
  canonical=cache/'cells/190/397.json';self.assertFalse(canonical.exists());self.assertTrue(working_path(canonical).with_suffix('.raw.json').exists())
 def test_stream_tags_reuse_retained_records_and_spool_misses(self):
  cache=self.root/'national-waterways/v2';old=cache/'ways/0/1.json';old.parent.mkdir(parents=True);old.write_text('{"tags":{"seasonal":"yes"}}')
  with patch.object(waterways,'CACHE',cache),patch.object(amenities,'fetch',return_value={'elements':[{'type':'way','id':2,'tags':{'intermittent':'yes'}}]}) as fetch:
   self.assertEqual(waterways.stream_tags([1,2]),{1:{'seasonal':'yes'},2:{'intermittent':'yes'}})
   self.assertEqual(waterways.stream_tags([2,1]),{1:{'seasonal':'yes'},2:{'intermittent':'yes'}});self.assertEqual(fetch.call_count,1)
  self.assertEqual(json.loads(old.read_text())['tags'],{'seasonal':'yes'});self.assertFalse((cache/'ways/0/2.json').exists())

# Independent spawned readers model the vector process pool's shared cold ranges.
_range_gate=None
def range_reader_initialize(gate):
 global _range_gate
 _range_gate=gate
def simultaneous_range_reader(cache):
 import time
 source=basemap.RangeSource(url='https://example.invalid/archive',cache_dir=cache,block_size=8);fetched=[]
 def fetch(start):fetched.append(start);time.sleep(.15);return b'abcdefgh'
 source._fetch=fetch;_range_gate.wait(timeout=20)
 return source.get_bytes(0,8),bool(fetched)

class ConcurrentRangeCacheTests(unittest.TestCase):
 def test_independent_processes_fetch_a_shared_cold_range_once(self):
  import multiprocessing
  from concurrent.futures import ProcessPoolExecutor
  context=multiprocessing.get_context('spawn')
  with tempfile.TemporaryDirectory() as folder:
   with ProcessPoolExecutor(max_workers=8,mp_context=context,initializer=range_reader_initialize,initargs=(context.Barrier(8),)) as pool:
    results=list(pool.map(simultaneous_range_reader,[str(Path(folder)/'ranges')]*8))
   self.assertTrue(all(value==b'abcdefgh' for value,fetched in results))
   self.assertEqual(sum(fetched for value,fetched in results),1)
