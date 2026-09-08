import hashlib,io,json,tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from access_control import Access,Denied
from object_cache import ObjectCache
import coverage_policy as coverage
from scratch_cache import prune

class Missing(Exception):response={'Error':{'Code':'NoSuchKey'}}
class Forbidden(Exception):response={'Error':{'Code':'AccessDenied'}}
class Store:
    def __init__(self):self.items={};self.puts=0;self.fail=False
    def get_paginator(self,name):return self
    def paginate(self,**kw):return [{'Contents':[{'Key':k,'Size':len(v)} for k,v in self.items.items()]}]
    def get_object(self,Key,**kw):
        if self.fail:raise Forbidden()
        if Key not in self.items:raise Missing()
        return {'Body':io.BytesIO(self.items[Key])}
    def put_object(self,Key,Body,**kw):self.items[Key]=Body;self.puts+=1

class CloudTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def access(self,limits={}):
        self.config=self.root/'access.json'
        self.config.write_text(json.dumps({'credentials':[{'role':role,'sha256':hashlib.sha256(role.encode()).hexdigest()} for role in ('client','warm')],'limits':limits}))
        return Access(self.root,self.config)
    def test_auth_revoke_and_separate_allowances(self):
        a=self.access({'generations':1,'warm_generations':2})
        with self.assertRaises(Denied):
            with a.request('Bearer invalid'):pass
        with a.request('Bearer client'):
            a.charge('generations',1)
            with self.assertRaises(Denied):a.charge('generations',1)
        with a.request('Bearer warm'):a.charge('generations',2)
        self.config.write_text('{"credentials":[]}')
        with self.assertRaises(Denied):a.identify('Bearer client')
    def test_atomic_monthly_limit_survives_restart(self):
        a=self.access({'generations':20})
        def charge(_):
            try:a.charge('generations',1);return 1
            except Denied:return 0
        with ThreadPoolExecutor(max_workers=12) as pool:self.assertEqual(sum(pool.map(charge,range(100))),20)
        other=Access(self.root,self.config)
        with self.assertRaises(Denied):other.charge('generations',1)
        with patch.object(other,'month',return_value='2099-01'):other.charge('generations',1)
    def test_concurrency_rate_and_byte_limits(self):
        a=self.access({'concurrency':1,'requests_per_minute':1,'download_bytes':5})
        with a.request('Bearer client'):
            with self.assertRaises(Denied):
                with a.request('Bearer client'):pass
            a.charge('download_bytes',4)
            with self.assertRaises(Denied):a.charge('download_bytes',1)
        with self.assertRaises(Denied):
            with a.request('Bearer client'):pass
        self.assertEqual(a.active['client'],0)
    def test_s3_caps_eviction_rehydrate_and_error_not_miss(self):
        client=Store();cache=ObjectCache(self.root,'bucket',client=client,max_bytes=6,local_bytes=3)
        first=self.root/'cache/a';second=self.root/'cache/b'
        cache.put('tiles/v1/a',first,b'abc','osm');cache.put('tiles/v1/b',second,b'def','osm')
        cache.prune(force=True);self.assertFalse(first.exists())
        self.assertEqual(cache.get('tiles/v1/a',first),b'abc')
        with self.assertRaises(Denied):cache.put('tiles/v1/c',second,b'g','osm')
        self.assertEqual(client.puts,2)
        client.fail=True
        with self.assertRaises(Forbidden):cache.get('tiles/v1/missing',self.root/'missing')
    def test_unpublished_local_tile_does_not_fake_s3_success(self):
        client=Store();cache=ObjectCache(self.root,'bucket',client=client)
        path=self.root/'old';path.write_bytes(b'old')
        self.assertIsNone(cache.get('tiles/v1/old',path))
    def test_reconcile_existing_bucket_before_writes(self):
        client=Store();client.items['tiles/v1/a']=b'1234'
        cache=ObjectCache(self.root,'bucket',client=client,max_bytes=4)
        with self.assertRaises(Denied):cache.put('tiles/v1/b',self.root/'b',b'1','osm')
    def test_world_overview_conus_detail_only(self):
        for lon,lat,detail in [(-119,38,True),(-150,64,False),(-155,20,False),(2,48,False)]:
            x,y=coverage.project(lon,lat)
            self.assertTrue(coverage.allowed('osm',7,int(x*128),int(y*128)))
            self.assertEqual(coverage.allowed('osm',12,int(x*4096),int(y*4096)),detail)
        from warm_us import tile_count
        from shapely.geometry import box
        from shapely.prepared import prep
        self.assertEqual(sum(tile_count(prep(box(0,0,1,1)),z) for z in range(8)),21845)
    def test_overzoom_clips_and_preserves_coordinates_and_properties(self):
        import mapbox_vector_tile as mvt
        blob=mvt.encode([{'name':'water','features':[{'geometry':{'type':'Point','coordinates':[512,3584]},'properties':{'name':'lake'}}]}])
        result=mvt.decode(coverage.overzoom(blob,9,0,0))['water']['features']
        self.assertEqual(result[0]['geometry']['coordinates'],[2048,2048])
        self.assertEqual(result[0]['properties']['name'],'lake')
        self.assertFalse(mvt.decode(coverage.overzoom(blob,9,3,3))['water']['features'])
    def test_scratch_preserves_databases_and_provenance(self):
        folder=self.root/'national_dem/id/windows';folder.mkdir(parents=True)
        (folder/'one.npz').write_bytes(b'12345');(folder/'one.json').write_text('{}')
        (self.root/'usage.sqlite').write_bytes(b'ledger')
        self.assertEqual(prune(self.root,0),0)
        self.assertTrue((folder/'one.json').exists());self.assertTrue((self.root/'usage.sqlite').exists())

if __name__=='__main__':unittest.main()
