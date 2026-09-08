import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from publish_cloud import buffered_tiles

class PipelineTests(unittest.TestCase):
    def test_starts_next_tile_while_previous_window_still_has_slow_tile(self):
        release=threading.Event();third=threading.Event()
        def task(i):
            if i==1:
                if not release.wait(3):raise TimeoutError('slow tile not released')
            if i==2:third.set()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=buffered_tiles(pool,task,range(4),2)
            try:
                self.assertEqual(next(results),0)
                self.assertTrue(third.wait(1),'next tile should start without waiting for tile 1')
            finally:release.set()
            self.assertEqual(list(results),[1,2,3])

    def test_failure_never_yields_checkpoint_past_failed_tile(self):
        def task(i):
            if i==2:raise ValueError('source unavailable')
        results=[]
        with ThreadPoolExecutor(max_workers=3) as pool:
            with self.assertRaises(ValueError):
                for item in buffered_tiles(pool,task,range(20),4):results.append(item)
        self.assertEqual(results,[0,1])

    def test_lookahead_bounded_and_early_close_drains(self):
        submitted=[]
        def items():
            for i in range(100):submitted.append(i);yield i
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=buffered_tiles(pool,lambda i:None,items(),4)
            self.assertEqual(next(results),0)
            self.assertEqual(len(submitted),5)
            results.close()
        self.assertEqual(len(submitted),5)

if __name__=='__main__':unittest.main()
