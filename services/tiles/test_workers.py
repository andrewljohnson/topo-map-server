"""Real CLI + spawned renderer integration; requires localhost binding permission."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import http.client
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import mapbox_vector_tile
from shapely.geometry import box, LineString
import tile_service as tiles

class WorkerTests(unittest.TestCase):
    def test_cli_two_workers_encode_actual_vectors(self):
        self.assertIsNone(tiles._render_pool, 'Importing the service must not spawn workers')
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp); database=directory/'maryland.sqlite'
            elevation=directory/'contours.sqlite'
            z=12;x,y=(int(v*4096) for v in tiles.project(*tiles.META['center']))
            geom=box(x/4096,(y+.1)/4096,(x+2)/4096,(y+.9)/4096)
            with sqlite3.connect(database) as con:
                con.executescript('CREATE TABLE features(id INTEGER PRIMARY KEY,kind TEXT,subtype TEXT,name TEXT,minzoom INTEGER,area REAL,geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
                con.execute('INSERT INTO metadata VALUES (?,?)',('sourceSha256','test-source-hash'))
                con.execute('INSERT INTO features VALUES (?,?,?,?,?,?,?)',(1,'water','test','Spawned water',6,geom.area,geom.wkb))
                a,b,c,d=geom.bounds;con.execute('INSERT INTO spatial VALUES (?,?,?,?,?)',(1,a,c,b,d))
            with sqlite3.connect(elevation) as con:
                con.executescript('CREATE TABLE contours(id INTEGER PRIMARY KEY,ele_ft INTEGER,is_index INTEGER,geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
                con.execute('INSERT INTO metadata VALUES (?,?)',('info',json.dumps({'status':'ready','sourceHash':'worker-contour','intervalFt':20,'indexIntervalFt':100})))
                line=LineString([(x/4096,(y+.5)/4096),((x+2)/4096,(y+.5)/4096)])
                con.execute('INSERT INTO contours VALUES (?,?,?,?)',(1,100,1,line.wkb))
                a,b,c,d=line.bounds;con.execute('INSERT INTO spatial VALUES (?,?,?,?,?)',(1,a,c,b,d))
            environment={**os.environ,'TILE_DATA_DIR':tmp,'TILE_MODE':'regional','TILE_RENDER_WORKERS':'2','TILE_RENDER_CONCURRENCY':'2'}
            process=subprocess.Popen([sys.executable,str(Path(tiles.__file__)),'serve','--port','0'],env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            try:
                line=process.stdout.readline()
                match=re.search(r':(\d+) \(render workers: 2\)',line)
                self.assertIsNotNone(match,line)
                port=int(match.group(1))
                def fetch(key,tileset='osm'):
                    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=15)
                    try:
                        conn.request('GET',('/contours/' if tileset=='contours' else '/tiles/')+'/'.join(map(str,key))+'.pbf',headers={'Accept-Encoding':'gzip'})
                        response=conn.getresponse();blob=response.read()
                        self.assertEqual(response.status,200,blob[:100])
                        return gzip.decompress(blob) if response.getheader('Content-Encoding')=='gzip' else blob
                    finally:
                        conn.close()
                keys=[(z,x,y),(z,x+1,y)]
                with ThreadPoolExecutor(max_workers=2) as pool:
                    blobs=list(pool.map(fetch,keys))
                with patch.object(tiles,'DB',database), patch.object(tiles,'CONTOURS_DB',elevation):
                    self.assertEqual(blobs,[tiles.render_tile(*key) for key in keys],'Spawned workers must preserve exact MVT bytes')
                for blob in blobs:
                    self.assertEqual(mapbox_vector_tile.decode(blob)['water']['features'][0]['properties']['name'],'Spawned water')
                self.assertEqual(list(map(fetch,keys)),blobs,'Repeated requests use parent disk cache')
                self.assertTrue(all('contour' not in mapbox_vector_tile.decode(blob) for blob in blobs))
                contour_blobs=[fetch(key,'contours') for key in keys]
                with patch.object(tiles,'CONTOURS_DB',elevation):
                    self.assertEqual(contour_blobs,[tiles.render_contour_tile(*key) for key in keys])
                for blob in contour_blobs:
                    decoded=mapbox_vector_tile.decode(blob)
                    self.assertEqual(set(decoded),{'contour'})
                    self.assertEqual(decoded['contour']['features'][0]['properties']['ele_ft'],100)
                self.assertEqual([fetch(key,'contours') for key in keys],contour_blobs)
            finally:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait()
                process.stdout.close()
            self.assertEqual(process.returncode,0,'CLI should shut down its worker processes cleanly')

if __name__=='__main__':
    unittest.main()
