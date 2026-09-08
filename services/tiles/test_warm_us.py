import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shapely.geometry import box
from shapely.prepared import prep
from warm_us import Journal, coordinates, tile_count, request_batch, can_warm, coverage

class WarmingTests(unittest.TestCase):
    def test_quadtree_resume_has_no_gaps_or_duplicates(self):
        geometry=prep(box(.1,.2,.72,.81))
        expected=list(coordinates(geometry,5))
        self.assertEqual(len(expected),tile_count(geometry,5))
        for index in (0,7,len(expected)//2,len(expected)-1):
            self.assertEqual(list(coordinates(geometry,5,expected[index][0])),expected[index+1:])
        self.assertEqual(len({(x,y) for _,x,y in expected}),len(expected))

    def test_country_mask_includes_all_three_regions_not_open_ocean(self):
        from warm_us import project
        geom=coverage({'bounds':[-180,-85,180,85]})
        for lon,lat in [(-119.5,37.7),(-150,64),(-155.5,19.6)]:
            x,y=project(lon,lat)
            self.assertTrue(geom.intersects(box(x-1e-5,y-1e-5,x+1e-5,y+1e-5)))
        x,y=project(-135,25)
        self.assertFalse(geom.intersects(box(x-.001,y-.001,x+.001,y+.001)))

    def test_failures_survive_reopen_and_retry_clears_only_that_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'jobs.sqlite'
            journal=Journal(path)
            spec={'datasetId':'one'}
            key=journal.ensure('osm',spec,2,'mask')
            journal.record(key,[(0,0,0),(1,1,0)],{'2/0/0'},{'2/1/0':'offline'})
            journal.db.close()
            journal=Journal(path)
            self.assertEqual(journal.row(key)['cursor'],1)
            self.assertEqual(journal.row(key)['done'],1)
            self.assertEqual(journal.failed(key),1)
            journal.record(key,[(1,1,0)],{'2/1/0'},{},retry=True)
            self.assertEqual(journal.failed(key),0)
            self.assertEqual(journal.row(key)['done'],2)
            self.assertNotEqual(key,journal.ensure('osm',{'datasetId':'two'},2,'mask'))
            journal.db.close()

    def test_partial_batch_not_marked_success(self):
        spec={'datasetId':'one','batchUrl':'/tile-batch'}
        response={'datasetId':'one','tiles':[{'key':'2/0/0','data':''}],
                  'errors':[{'key':'2/1/0','error':'upstream unavailable'}]}
        with patch('warm_us.read_json',return_value=response):
            ok,errors=request_batch('http://local',spec,2,[(0,0,0),(1,1,0)])
        self.assertEqual(ok,{'2/0/0'})
        self.assertEqual(errors,{'2/1/0':'upstream unavailable'})

    def test_invalid_dem_and_changed_manifest_fail(self):
        spec={'datasetId':'one','batchUrl':'/dem-batch','format':'png'}
        response={'datasetId':'one','tiles':[{'key':'3/0/0','data':base64.b64encode(b'html error').decode()}]}
        with patch('warm_us.read_json',return_value=response), self.assertRaises(ValueError):
            request_batch('http://local',spec,3,[(0,0,0)])
        response['datasetId']='two'
        with patch('warm_us.read_json',return_value=response), self.assertRaises(RuntimeError):
            request_batch('http://local',spec,3,[(0,0,0)])

    def test_viewport_and_disk_take_priority(self):
        from collections import namedtuple
        usage=namedtuple('usage','total used free')(100,20,80)
        with patch('warm_us.shutil.disk_usage',return_value=usage):
            self.assertEqual(can_warm('http://local','/',1),'paused-low-disk')
            with patch('warm_us.read_json',return_value={'foregroundActive':1}):
                self.assertEqual(can_warm('http://local','/',0),'waiting-for-viewport')
            with patch('warm_us.read_json',return_value={'idleSeconds':1,'quietSeconds':2}):
                self.assertEqual(can_warm('http://local','/',0),'waiting-for-viewport')
            with patch('warm_us.read_json',return_value={'idleSeconds':3,'quietSeconds':2}):
                self.assertIsNone(can_warm('http://local','/',0))

if __name__=='__main__':unittest.main()
