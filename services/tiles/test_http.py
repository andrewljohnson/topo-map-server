"""Actual ephemeral HTTP integration tests; requires permission to bind localhost."""
import base64
import gzip
import http.client
import json
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import tile_service as tiles

class QuietHandler(tiles.Handler):
    def log_message(self, *_):
        pass

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = tiles.ThreadingHTTPServer(('127.0.0.1',0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        x,y = (int(v*4096) for v in tiles.project(*tiles.META['center']))
        cls.keys = [f'12/{x+offset}/{y}' for offset in range(2)]
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
    def setUp(self):
        self.conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port,timeout=10)
        self.meta = patch.object(tiles,'metadata',return_value={**tiles.META,'datasetId':'test-dataset'})
        self.meta.start()
        self.addCleanup(self.meta.stop)
        self.addCleanup(self.conn.close)
    def request(self,path,encoding='gzip',method='GET'):
        self.conn.request(method,path,headers={'Accept-Encoding':encoding})
        response = self.conn.getresponse()
        body = response.read()
        self.assertEqual(int(response.getheader('Content-Length')),len(body) if method!='HEAD' else int(response.getheader('Content-Length')))
        wire = body
        if response.getheader('Content-Encoding')=='gzip' and body:
            body = gzip.decompress(body)
        return response,body,wire
    def batch(self,keys=None,dataset='test-dataset'):
        return '/tile-batch?'+urlencode({'datasetId':dataset,'tiles':','.join(self.keys if keys is None else keys)})
    def test_partial_success_retry_and_gzip(self):
        first,second = self.keys
        payload = b'valid-protobuf-placeholder'*300
        def render(z,x,y,**kwargs):
            if f'{z}/{x}/{y}'==second:
                raise RuntimeError('injected temporary failure')
            return payload
        with patch.object(tiles,'tile_bytes',side_effect=render) as mocked:
            response,body,wire = self.request(self.batch())
            self.assertEqual(response.status,200)
            self.assertEqual(response.getheader('Content-Encoding'),'gzip')
            self.assertLess(len(wire),len(body))
            result=json.loads(body)
            self.assertEqual(result['datasetId'],'test-dataset')
            self.assertEqual(result['tiles'],[{'key':first,'data':base64.b64encode(payload).decode()}])
            self.assertEqual(result['errors'][0]['key'],second)
            self.assertEqual(mocked.call_count,2)
        with patch.object(tiles,'tile_bytes',return_value=payload) as mocked:
            response,body,_=self.request(self.batch([second]))
            self.assertEqual(json.loads(body)['errors'],[])
            self.assertEqual(mocked.call_count,1,'retry only failed key')
    def test_full_eight_key_batch(self):
        x,y = (int(v*16384) for v in tiles.project(*tiles.META['center']))
        keys = [f'14/{x+dx}/{y+dy}' for dx in range(4) for dy in range(2)]
        with patch.object(tiles,'tile_bytes',return_value=b'tile-vector') as mocked:
            response,body,_ = self.request(self.batch(keys))
            self.assertEqual(response.status,200)
            self.assertEqual(len(json.loads(body)['tiles']),8)
            self.assertEqual(mocked.call_count,8)
            response,_,_ = self.request(self.batch(keys+[f'14/{x+4}/{y}']))
            self.assertEqual(response.status,400)
            self.assertEqual(mocked.call_count,8)

    def test_limits_validation_before_render(self):
        malformed=[self.batch([]),self.batch([self.keys[0]]*2),self.batch([self.keys[0]]*9),self.batch(['14/0/0']),self.batch(['12/001/1']),self.batch(['../../etc']),'/tile-batch?tiles=12/1/1','/tile-batch?datasetId=test-dataset&tiles=&extra=yes']
        with patch.object(tiles,'tile_bytes') as mocked:
            for path in malformed:
                response,_,_=self.request(path)
                self.assertEqual(response.status,400,path)
            mocked.assert_not_called()
    def test_dataset_mismatch_before_render(self):
        with patch.object(tiles,'tile_bytes') as mocked:
            response,body,_=self.request(self.batch(dataset='old-dataset'))
            self.assertEqual(response.status,409)
            self.assertEqual(json.loads(body)['datasetId'],'test-dataset')
            mocked.assert_not_called()
    def test_keepalive_individual_gzip_and_disabled_encoding(self):
        payload=b'protobuf-test'*500
        with patch.object(tiles,'tile_bytes',return_value=payload):
            response,body,_=self.request('/tiles/'+self.keys[0]+'.pbf')
            socket=self.conn.sock
            self.assertEqual(response.version,11)
            self.assertEqual(response.getheader('Content-Encoding'),'gzip')
            self.assertEqual(body,payload)
            response,body,_=self.request('/tiles/'+self.keys[1]+'.pbf',encoding='gzip;q=0, br')
            self.assertIs(self.conn.sock,socket)
            self.assertIsNone(response.getheader('Content-Encoding'))
            self.assertEqual(body,payload)
            self.assertEqual(response.getheader('Vary'),'Accept-Encoding')
            self.assertEqual(response.getheader('Access-Control-Allow-Origin'),'*')
    def test_single_tile_dataset_query_invalidates_browser_cache(self):
        with patch.object(tiles,'tile_bytes',return_value=b'vector-pbf') as mocked:
            response,body,_=self.request('/tiles/'+self.keys[0]+'.pbf?datasetId=old-dataset')
            self.assertEqual(response.status,409)
            mocked.assert_not_called()
            response,body,_=self.request('/tiles/'+self.keys[0]+'.pbf?datasetId=test-dataset')
            self.assertEqual(response.status,200)
            self.assertEqual(body,b'vector-pbf')
            self.assertEqual(mocked.call_count,1)

    def test_independent_contour_endpoints_and_dataset_ids(self):
        meta={**tiles.META,'datasetId':'test-dataset','tilesets':{'osm':{'datasetId':'test-dataset'},'contours':{'datasetId':'contour-dataset'}}}
        def payload(z,x,y,**kwargs):
            return (b'contour-pbf' if kwargs['tileset']=='contours' else b'osm-pbf')*100
        with patch.object(tiles,'metadata',return_value=meta),patch.object(tiles,'tile_bytes',side_effect=payload) as mocked:
            response,body,_=self.request('/contours/'+self.keys[0]+'.pbf?datasetId=contour-dataset')
            self.assertEqual(response.status,200)
            self.assertEqual(body,b'contour-pbf'*100)
            response,body,_=self.request('/tiles/'+self.keys[0]+'.pbf?datasetId=test-dataset')
            self.assertEqual(body,b'osm-pbf'*100)
            contour_batch='/contour-batch?'+urlencode({'datasetId':'contour-dataset','tiles':','.join(self.keys)})
            response,body,_=self.request(contour_batch)
            self.assertEqual(response.status,200)
            result=json.loads(body)
            self.assertEqual(result['datasetId'],'contour-dataset')
            self.assertEqual(result['errors'],[])
            self.assertTrue(all(base64.b64decode(tile['data'])==b'contour-pbf'*100 for tile in result['tiles']))
            before=mocked.call_count
            for path in ['/contours/'+self.keys[0]+'.pbf?datasetId=test-dataset','/tiles/'+self.keys[0]+'.pbf?datasetId=contour-dataset',contour_batch.replace('contour-dataset','test-dataset'),self.batch(dataset='contour-dataset')]:
                response,_,_=self.request(path)
                self.assertEqual(response.status,409)
            self.assertEqual(mocked.call_count,before)
            x,y=(int(v*1024) for v in tiles.project(*tiles.META['center']))
            response,_,_=self.request('/contour-batch?'+urlencode({'datasetId':'contour-dataset','tiles':f'10/{x}/{y}'}))
            self.assertEqual(response.status,400,'Contour zoom minimum is 11')
            self.assertEqual(mocked.call_count,before)

    def test_contours_not_advertised_or_served_before_ready(self):
        with patch.object(tiles,'tile_bytes') as mocked:
            response,_,_=self.request('/contours/'+self.keys[0]+'.pbf')
            self.assertEqual(response.status,503)
            response,_,_=self.request('/contour-batch?'+urlencode({'datasetId':'unavailable','tiles':self.keys[0]}))
            self.assertEqual(response.status,503)
            mocked.assert_not_called()

    def test_head_options_and_metadata(self):
        response,body,_=self.request('/metadata')
        meta=json.loads(body)
        self.assertEqual(meta['batchSize'],8)
        self.assertEqual(meta['batchUrl'],'/tile-batch')
        response,body,_=self.request('/metadata',method='HEAD')
        self.assertEqual(response.status,200)
        self.assertEqual(body,b'')
        response,body,_=self.request('/tile-batch',method='OPTIONS')
        self.assertEqual(response.status,204)
        self.assertEqual(body,b'')

if __name__=='__main__':
    unittest.main()
