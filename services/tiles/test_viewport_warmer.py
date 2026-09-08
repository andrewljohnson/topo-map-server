import threading
import time
import unittest
from viewport_warmer import ViewportWarmer, neighborhood
from tile_service import RenderGate, tile_lock

class ViewportWarmingTests(unittest.TestCase):
    def warmer(self, **kwargs):
        return ViewportWarmer(lambda key:None,lambda key:False,lambda *args:True,**kwargs)
    def test_halo_children_and_all_sources(self):
        keys=set(neighborhood(12,655,1583))
        for source in ('osm','dem','amenities','boundaries','waterways','landcover','trails','recreation'):
            self.assertIn((source,12,654,1583),keys)
            self.assertIn((source,13,1310,3166),keys)
        self.assertEqual(len(keys),104)
        self.assertEqual({k[1] for k in neighborhood(14,100,100)},{14})
        self.assertEqual({k[0] for k in neighborhood(3,2,2)},{'osm'})
        self.assertTrue(all(0<=k[2]<2**k[1] and 0<=k[3]<2**k[1] for k in neighborhood(10,0,0)))
    def test_bound_dedup_expiry_and_cached_skip(self):
        now=[0];w=self.warmer(limit=140,ttl=10,clock=lambda:now[0])
        w.observe(12,655,1583);w.observe(12,655,1583);self.assertEqual(len(w.pending),104)
        w.observe(12,900,1300);self.assertEqual(len(w.pending),140);self.assertGreater(w.dropped,0)
        now[0]=11;self.assertIsNone(w.take('terrain'));self.assertEqual(len(w.pending),0)
        w.cached=lambda key:True;w.observe(12,655,1583);self.assertFalse(w.pending)
    def test_isolated_lanes_active_dedup_and_stop(self):
        w=self.warmer();w.observe(12,655,1583)
        key=w.take('amenities');self.assertEqual(key[0],'amenities')
        self.assertIn(w.take('terrain')[0],('osm','dem'))
        count=len(w.pending);w.observe(12,655,1583);self.assertNotIn(key,w.pending);self.assertEqual(len(w.pending),count)
        w.stop();self.assertIsNone(w.take('terrain'))
    def test_failure_cooldown(self):
        w=self.warmer()
        def fail(key):raise RuntimeError('upstream unavailable')
        w.render=fail;w.pending[('osm',12,1,1)]=time.monotonic()+10
        thread=threading.Thread(target=w.run,args=('terrain',));thread.start()
        deadline=time.monotonic()+2
        while not w.failed and time.monotonic()<deadline:time.sleep(.01)
        w.stop();thread.join(2)
        self.assertEqual(w.failed,1);self.assertTrue(w.cooldown)
        self.assertIn('upstream unavailable',w.status()['recentErrors'][0]['error'])
    def test_background_reserves_foreground_capacity(self):
        gate=RenderGate(2);entered=threading.Event()
        def background():
            with gate.slot(batch=True,background=True):entered.set()
        with gate.slot():
            thread=threading.Thread(target=background);thread.start();self.assertFalse(entered.wait(.05))
            with gate.slot():self.assertEqual(gate.active,2)
        self.assertTrue(entered.wait(1));thread.join()
    def test_exact_tile_locks(self):
        lock=tile_lock('a');self.assertIs(lock,tile_lock('a'));self.assertIsNot(lock,tile_lock('b'))

    def test_download_batch_also_reserves_foreground_capacity(self):
        gate=RenderGate(2);entered=threading.Event()
        def batch():
            with gate.slot(batch=True):entered.set()
        with gate.slot():
            thread=threading.Thread(target=batch);thread.start();self.assertFalse(entered.wait(.05))
            with gate.slot():self.assertEqual(gate.active,2)
        self.assertTrue(entered.wait(1));thread.join()
    def test_warming_waits_until_viewport_is_finished_and_quiet(self):
        now=[0];w=self.warmer(clock=lambda:now[0]);w.observe(12,655,1583)
        with w.foreground():
            now[0]=20;self.assertIsNone(w.take('terrain'));self.assertIsNone(w.take('boundaries'))
        self.assertIsNone(w.take('terrain'));now[0]=22.1;self.assertIsNotNone(w.take('terrain'))
    def test_newest_viewport_is_warmed_before_abandoned_area(self):
        w=self.warmer();w.observe(12,655,1583);w.observe(12,900,1300)
        key=w.take('terrain');self.assertIn(key[2],(899,900,901,1800,1801))

    def test_queued_batch_does_not_lock_out_visible_same_tile(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import tile_service as server
        gate=RenderGate(2);started=threading.Event();visible=threading.Event();errors=[]
        def request(batch):
            try:
                if batch:started.set()
                self.assertEqual(server.tile_bytes(12,100,100,batch=batch),b'tile')
                if not batch:visible.set()
            except Exception as exc:errors.append(exc)
        with tempfile.TemporaryDirectory() as directory,patch.object(server,'DATA',Path(directory)),patch.object(server,'valid_tile',return_value=True),patch.object(server,'metadata',return_value={'tilesets':{'osm':{'datasetId':'test'}}}),patch.object(server,'render_tile',return_value=b'tile'),patch.object(server,'_render_gate',gate),patch.object(server,'_render_pool',None):
            with gate.slot():
                background=threading.Thread(target=request,args=(True,));background.start();self.assertTrue(started.wait(1))
                time.sleep(.02)
                foreground=threading.Thread(target=request,args=(False,));foreground.start()
                completed=visible.wait(1)
            foreground.join(2);background.join(2)
            self.assertTrue(completed,'visible request must finish before the occupied slot is released')
            self.assertFalse(errors)
