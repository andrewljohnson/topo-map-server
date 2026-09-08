import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import base64
from shapely.geometry import box
import precache as job

class PrecacheTests(unittest.TestCase):
    def setUp(self):job.STOP.clear()
    def test_region_enumeration_clips_to_boundary(self):
        keys=list(job.region_keys(box(.1,.1,.2,.2),2,2))
        self.assertEqual(keys,[(2,'2/0/0')])
    def test_resume_and_source_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'job.sqlite';shape=box(.1,.1,.2,.2)
            meta={'tilesets':{'osm':{'datasetId':'a','minZoom':2,'maxZoom':2}}}
            job.initialize(path,meta,shape)
            with job.connect(path) as con:con.execute("UPDATE tasks SET status='done'")
            job.initialize(path,meta,shape)
            with job.connect(path) as con:self.assertEqual(con.execute('SELECT status FROM tasks').fetchone()[0],'done')
            meta['tilesets']['osm']['datasetId']='b';job.initialize(path,meta,shape)
            with job.connect(path) as con:self.assertEqual(con.execute('SELECT status FROM tasks').fetchone()[0],'pending')
    def test_basemap_revision_preserves_completed_contours(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'job.sqlite';geometry=box(.1,.1,.2,.2)
            meta={'tilesets':{s:{'datasetId':s,'minZoom':2,'maxZoom':2} for s in ['osm','contours']}}
            job.initialize(path,meta,geometry)
            with job.connect(path) as con:con.execute("UPDATE tasks SET status='done',bytes=123")
            meta['tilesets']['osm']['datasetId']='new-labels'
            job.initialize(path,meta,geometry)
            with job.connect(path) as con:
                self.assertEqual(con.execute('SELECT source,status,bytes FROM tasks ORDER BY source').fetchall(),[('contours','done',123),('osm','pending',0)])

    def test_worker_records_both_sets_and_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'job.sqlite';shape=box(.1,.1,.2,.2)
            meta={'tilesets':{s:{'datasetId':s,'minZoom':2,'maxZoom':2,'batchUrl':'/'+s,'batchSize':8} for s in ['osm','contours']}}
            job.initialize(path,meta,shape)
            def fetch(url):
                from urllib.parse import urlsplit,parse_qs
                q=parse_qs(urlsplit(url).query)
                return {'datasetId':q['datasetId'][0],'tiles':[{'key':key,'data':base64.b64encode(b'tile').decode()} for key in q['tiles'][0].split(',')],'errors':[]}
            with patch.object(job,'fetch',side_effect=fetch),patch.object(job,'DATA',Path(tmp)):
                self.assertIsNone(job.worker(path,'http://local',meta))
            status=job.status(path,0,'complete')
            self.assertEqual(status['completed'],2);self.assertEqual(status['tileBytes'],8)
            self.assertEqual(status['sources'],{'osm':{'done':1},'contours':{'done':1}})

if __name__=='__main__':unittest.main()
