#!/usr/bin/env python3
"""Resumable California cache job; uses the serving API's low-priority batch lane."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import fcntl
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import threading
import time
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from shapely.geometry import Polygon,box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('TILE_DATA_DIR',ROOT/'data'))
STOP=threading.Event()

def boundary(path):
    rings=[];holes=[];points=[];hole=False
    for line in Path(path).read_text().splitlines()[1:]:
        parts=line.split()
        if not parts:continue
        if parts[0]=='END':
            if points:(holes if hole else rings).append(Polygon(points));points=[]
        elif len(parts)==2:
            lon,lat=map(float,parts)
            points.append(((lon+180)/360,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2))
        else:hole=parts[0].startswith('!')
    return unary_union(rings).difference(unary_union(holes))

def region_keys(geometry,minzoom,maxzoom):
    west,north,east,south=geometry.bounds
    for z in range(minzoom,maxzoom+1):
        n=2**z
        for x in range(max(0,int(west*n)),min(n-1,int(east*n))+1):
            for y in range(max(0,int(north*n)),min(n-1,int(south*n))+1):
                if geometry.intersects(box(x/n,y/n,(x+1)/n,(y+1)/n)):
                    yield z,f'{z}/{x}/{y}'

def fetch(url):
    with urlopen(Request(url,headers={'Accept-Encoding':'gzip','User-Agent':'topo-map-server-precache/1'}),timeout=240) as response:
        data=response.read()
        return json.loads(gzip.decompress(data) if response.headers.get('Content-Encoding')=='gzip' else data)

def connect(path):
    con=sqlite3.connect(path,timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    return con

def initialize(path,meta,geometry,retry=False):
    composition=json.dumps({k:v['datasetId'] for k,v in meta['tilesets'].items()},sort_keys=True)
    with connect(path) as con:
        con.executescript('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS tasks(source TEXT,key TEXT,zoom INTEGER,status TEXT DEFAULT "pending",attempts INTEGER DEFAULT 0,retry_at REAL DEFAULT 0,bytes INTEGER DEFAULT 0,error TEXT,PRIMARY KEY(source,key)); CREATE INDEX IF NOT EXISTS task_status ON tasks(status,retry_at,zoom);')
        old=con.execute("SELECT value FROM metadata WHERE key='composition'").fetchone()
        if old and old[0]!=composition:
            # Preserve completed work for unchanged sources (especially DEM contours).
            previous=json.loads(old[0]);current=json.loads(composition)
            for name in previous.keys() | current.keys():
                if previous.get(name)!=current.get(name):
                    con.execute('DELETE FROM tasks WHERE source=?',(name,))
        if not old or old[0]!=composition:
            for name,source in meta['tilesets'].items():
                con.executemany('INSERT OR IGNORE INTO tasks(source,key,zoom) VALUES (?,?,?)',((name,key,z) for z,key in region_keys(geometry,source['minZoom'],source['maxZoom'])))
            con.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('composition',composition))
        con.execute("UPDATE tasks SET status='pending' WHERE status='working'")
        if retry:con.execute("UPDATE tasks SET status='pending',attempts=0,retry_at=0 WHERE status='error'")

def worker(path,api,meta):
    while not STOP.is_set():
        if shutil.disk_usage(DATA).free<10*1024**3:
            STOP.set();return 'Less than 10 GiB free; resume after freeing space'
        with connect(path) as con:
            con.execute('BEGIN IMMEDIATE')
            first=con.execute("SELECT source FROM tasks WHERE status='pending' AND retry_at<=? ORDER BY zoom,source DESC LIMIT 1",(time.time(),)).fetchone()
            if not first:
                pending=con.execute("SELECT count(*) FROM tasks WHERE status IN ('pending','working')").fetchone()[0]
                if not pending:return None
                con.commit();STOP.wait(2);continue
            source=first[0];spec=meta['tilesets'][source]
            keys=[r[0] for r in con.execute("SELECT key FROM tasks WHERE source=? AND status='pending' AND retry_at<=? ORDER BY zoom,key LIMIT ?",(source,time.time(),min(8,spec.get('batchSize',8))))]
            con.executemany("UPDATE tasks SET status='working' WHERE source=? AND key=?",((source,key) for key in keys))
        successes={};message='Tile missing from batch response'
        try:
            url=api+spec['batchUrl']+'?'+urlencode({'datasetId':spec['datasetId'],'tiles':','.join(keys)})
            result=fetch(url)
            if result['datasetId']!=spec['datasetId']:raise ValueError('Dataset changed; restart this job')
            successes={t['key']:len(base64.b64decode(t['data'])) for t in result['tiles'] if t['key'] in keys}
            if result.get('errors'):message=result['errors'][0]['error']
        except Exception as exc:message=str(exc)
        with connect(path) as con:
            for key in keys:
                if key in successes:con.execute("UPDATE tasks SET status='done',bytes=?,error=NULL WHERE source=? AND key=?",(successes[key],source,key))
                else:
                    attempt=con.execute('SELECT attempts FROM tasks WHERE source=? AND key=?',(source,key)).fetchone()[0]+1
                    con.execute('UPDATE tasks SET status=?,attempts=?,retry_at=?,error=? WHERE source=? AND key=?',('error' if attempt>=5 else 'pending',attempt,time.time()+min(300,5*2**attempt),message,source,key))
    return None

def status(path,started,state='running',error=None):
    with connect(path) as con:
        counts=dict(con.execute('SELECT status,count(*) FROM tasks GROUP BY status'))
        size=con.execute('SELECT coalesce(sum(bytes),0) FROM tasks').fetchone()[0]
        sources={name:dict(con.execute('SELECT status,count(*) FROM tasks WHERE source=? GROUP BY status',(name,))) for (name,) in con.execute('SELECT DISTINCT source FROM tasks').fetchall()}
        recent=con.execute('SELECT error FROM tasks WHERE error IS NOT NULL ORDER BY retry_at DESC LIMIT 1').fetchone()
    result={'region':'California','status':state,'pid':os.getpid(),'startedAt':started,'updatedAt':time.time(),'total':sum(counts.values()),'completed':counts.get('done',0),'failed':counts.get('error',0),'counts':counts,'sources':sources,'tileBytes':size,'maxZoom':14,'error':error or (recent[0] if recent else None)}
    tmp=path.with_name('california-status.tmp');tmp.write_text(json.dumps(result,indent=2));tmp.replace(path.with_name('california-status.json'))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--api',default='http://127.0.0.1:3001');parser.add_argument('--workers',type=int,default=2);parser.add_argument('--retry-errors',action='store_true');args=parser.parse_args()
    directory=DATA/'jobs';directory.mkdir(parents=True,exist_ok=True)
    lock=open(directory/'california.lock','w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('California job is already running')
    path=directory/'california.sqlite';started=time.time()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:STOP.set())
    meta=fetch(args.api+'/metadata');geometry=boundary(ROOT/'regions'/'california.poly');initialize(path,meta,geometry,args.retry_errors)
    initial=status(path,started);print(f"California job: {initial['total']:,} tiles; {initial['completed']:,} already complete",flush=True)
    with ThreadPoolExecutor(max_workers=max(1,min(2,args.workers))) as pool:
        futures=[pool.submit(worker,path,args.api,meta) for _ in range(max(1,min(2,args.workers)))]
        while not all(f.done() for f in futures):
            current=status(path,started);print(f"{current['completed']}/{current['total']} cached; {current['failed']} failed",flush=True);time.sleep(5)
        errors=[]
        for future in futures:
            try:
                error=future.result()
                if error:errors.append(error)
            except Exception as exc:errors.append(str(exc))
    final=status(path,started);state='paused' if STOP.is_set() else 'failed' if errors or final['failed'] else 'complete'
    print(json.dumps(status(path,started,state,'; '.join(errors) or None)),flush=True)

if __name__=='__main__':main()
