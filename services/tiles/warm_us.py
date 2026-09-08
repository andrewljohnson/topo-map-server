#!/usr/bin/env python3
"""Resumable US cache warming through the serving process's low-priority batches.

One bounded batch at a time. SQLite contains cursors and failed keys, not millions
of pending rows. Coastline quadtree traversal skips completed subtrees on resume.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import os
import coverage_policy

from shapely.geometry import box, shape
from shapely.ops import transform
from shapely.prepared import prep

SOURCES = ('osm', 'dem', 'boundaries', 'landcover', 'trails', 'amenities', 'waterways', 'recreation')
MASK = Path(__file__).parent / 'regions/us-warming.geojson'

def project(x, y, z=None):
    return (x+180)/360, (1-math.asinh(math.tan(math.radians(max(-85.05112878,min(85.05112878,y)))))/math.pi)/2

def coverage(spec, mask=MASK):
    geometry = shape(json.loads(mask.read_text())['geometry'])
    geometry = geometry.intersection(box(*spec['bounds']))
    return prep(transform(project, geometry))

def coordinates(geometry, target, after=-1):
    """Morton ordered leaves; resume without visiting completed subtrees."""
    def visit(z, x, y, code):
        shift = 2*(target-z)
        if ((code+1)<<shift)-1 <= after:
            return
        n=2**z
        if not geometry.intersects(box(x/n,y/n,(x+1)/n,(y+1)/n)):
            return
        if z==target:
            yield code,x,y
        else:
            for digit in range(4):
                yield from visit(z+1,x*2+(digit&1),y*2+(digit>>1),code*4+digit)
    yield from visit(0,0,0,0)

def tile_count(geometry,target):
    def visit(z,x,y):
        n=2**z; tile=box(x/n,y/n,(x+1)/n,(y+1)/n)
        if not geometry.intersects(tile):return 0
        if z==target:return 1
        if geometry.covers(tile):return 4**(target-z)
        return sum(visit(z+1,x*2+(digit&1),y*2+(digit>>1)) for digit in range(4))
    return visit(0,0,0)

def read_json(url):
    token_file=os.environ.get('TOPO_WARM_TOKEN_FILE')
    headers={'Authorization':'Bearer '+Path(token_file).read_text().strip()} if token_file else {}
    with urlopen(Request(url,headers=headers),timeout=300) as response:
        return json.load(response)

class Journal:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row
        self.db.executescript("""
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, source TEXT, dataset TEXT, zoom INTEGER,
            cursor INTEGER DEFAULT -1, done INTEGER DEFAULT 0,
            exhausted INTEGER DEFAULT 0);
          CREATE TABLE IF NOT EXISTS failures (
            run TEXT, code INTEGER, x INTEGER, y INTEGER, attempts INTEGER,
            retry_at REAL, message TEXT, PRIMARY KEY(run,code));
        """)
    def ensure(self,source,spec,z,mask_hash):
        identity=json.dumps([1,source,spec,z,mask_hash],sort_keys=True)
        key=hashlib.sha256(identity.encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO runs(id,source,dataset,zoom) VALUES(?,?,?,?)',(key,source,spec['datasetId'],z))
        return key
    def row(self,key):return self.db.execute('SELECT * FROM runs WHERE id=?',(key,)).fetchone()
    def record(self,key,items,successes,errors,retry=False):
        with self.db:
            for code,x,y in items:
                tile=f"{self.row(key)['zoom']}/{x}/{y}"
                if tile in successes:
                    self.db.execute('DELETE FROM failures WHERE run=? AND code=?',(key,code))
                    self.db.execute('UPDATE runs SET done=done+1 WHERE id=?',(key,))
                else:
                    old=self.db.execute('SELECT attempts FROM failures WHERE run=? AND code=?',(key,code)).fetchone()
                    attempts=old[0]+1 if old else 1
                    delay=min(3600,30*2**min(attempts,7))
                    self.db.execute('INSERT OR REPLACE INTO failures VALUES(?,?,?,?,?,?,?)',(key,code,x,y,attempts,time.time()+delay,errors.get(tile,'Missing tile in batch response')))
            if items and not retry:
                self.db.execute('UPDATE runs SET cursor=? WHERE id=?',(items[-1][0],key))
    def failed(self,key):
        return self.db.execute('SELECT COUNT(*) FROM failures WHERE run=?',(key,)).fetchone()[0]

def request_batch(api,spec,z,items):
    keys=[f'{z}/{x}/{y}' for _,x,y in items]
    query=urlencode({'datasetId':spec['datasetId'],'tiles':','.join(keys)})
    data=read_json(api+spec['batchUrl']+'?'+query)
    if data.get('datasetId')!=spec['datasetId']:
        raise RuntimeError('Dataset changed while warming; restart to load the new manifest')
    success=set()
    for tile in data.get('tiles',[]):
        if tile.get('key') not in keys or tile['key'] in success:raise ValueError('Unexpected batch tile')
        blob=base64.b64decode(tile['data'],validate=True)
        if spec.get('format')=='png' and not blob.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid DEM PNG')
        success.add(tile['key'])
    return success,{t['key']:t.get('error','Tile failed') for t in data.get('errors',[])}

def can_warm(api,data,min_free_gb):
    if shutil.disk_usage(data).free < min_free_gb*10**9:
        return 'paused-low-disk'
    stats=read_json(api+'/jobs/viewport')
    if stats.get('foregroundActive',0) or stats.get('idleSeconds',999)<stats.get('quietSeconds',2):
        return 'waiting-for-viewport'
    return None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api',default='http://127.0.0.1:3001')
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--sources',nargs='+',choices=SOURCES,default=list(SOURCES))
    parser.add_argument('--max-zoom',type=int,default=14)
    parser.add_argument('--min-free-gb',type=float,default=50)
    parser.add_argument('--batch-size',type=int,choices=range(1,9),default=8)
    parser.add_argument('--once',action='store_true',help='One pass; exit nonzero if tiles remain failed')
    parser.add_argument('--plan',action='store_true',help='Count covered tiles; do not request or generate tiles')
    args=parser.parse_args()
    if not 0<=args.max_zoom<=14:parser.error('--max-zoom must be 0–14')
    if args.min_free_gb<0:parser.error('--min-free-gb must be nonnegative')
    api=args.api.rstrip('/')
    specs=read_json(api+'/metadata')['tilesets']
    geometries={s:prep(coverage_policy.conus()) for s in args.sources}
    # Contour stencils need neighbors just outside the land mask as well.
    terrain={z:prep(geometries['dem'].context.buffer(2**-z)) for z in range(3,min(13,args.max_zoom)+1)} if 'dem' in geometries else {}
    def geometry_for(s,z):return prep(box(0,0,1,1)) if s=='osm' and z<=7 else terrain[z] if s=='dem' else geometries[s]
    plans=[(s,z) for group in (('osm','dem'),tuple(s for s in SOURCES if s not in ('osm','dem'))) for z in range(args.max_zoom+1) for s in group if s in args.sources and specs[s]['minZoom']<=z<=specs[s]['maxZoom']]
    if args.plan:
        total=0
        for s,z in plans:
            count=tile_count(geometry_for(s,z),z);total+=count
            print(json.dumps({'source':s,'zoom':z,'tiles':count}),flush=True)
        print(json.dumps({'total':total}),flush=True);return
    jobs=args.data/'jobs';jobs.mkdir(parents=True,exist_ok=True)
    lock=(jobs/'us-warming.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    journal=Journal(jobs/'us-warming.sqlite')
    mask_hash='world7-conus14-v1-'+hashlib.sha256(MASK.read_bytes()).hexdigest()
    active=[(journal.ensure(s,specs[s],z,mask_hash),s,z) for s,z in plans]
    def status(state,current=None,error=None):
        rows=[dict(journal.row(k),failed=journal.failed(k)) for k,_,_ in active]
        result={'status':state,'updatedAt':time.time(),'current':current,'error':error,
                'done':sum(r['done'] for r in rows),'failed':sum(r['failed'] for r in rows),'runs':rows}
        target=jobs/'us-status.json';temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(result,separators=(',',':')));temp.replace(target)
    def batch(key,s,z,items,retry=False):
        while True:
            try:blocked=can_warm(api,args.data,args.min_free_gb)
            except HTTPError as exc:blocked='paused-allowance' if exc.code==429 else 'waiting-for-server'
            except Exception as exc:blocked='waiting-for-server'
            if not blocked:break
            status(blocked,{'source':s,'zoom':z});time.sleep(5)
        status('warming',{'source':s,'zoom':z,'tiles':len(items)})
        while True:
            try:ok,errors=request_batch(api,specs[s],z,items)
            except HTTPError as exc:
                if exc.code in (401,403,429):
                    status('paused-allowance-or-credentials',{'source':s,'zoom':z});time.sleep(60)
                    continue
                ok=set();errors={f'{z}/{x}/{y}':str(exc)[:300] for _,x,y in items}
            except Exception as exc:
                ok=set();errors={f'{z}/{x}/{y}':str(exc)[:300] for _,x,y in items}
            break
        journal.record(key,items,ok,errors,retry=retry)
        # One sequential request stream and a pause leave resources for browsing.
        time.sleep(.25 if not errors else 5)
    while True:
        for key,s,z in active:
            row=journal.row(key)
            if not row['exhausted']:
                items=[]
                for item in coordinates(geometry_for(s,z),z,row['cursor']):
                    items.append(item)
                    if len(items)==args.batch_size:
                        batch(key,s,z,items);items=[]
                if items:batch(key,s,z,items)
                with journal.db:journal.db.execute('UPDATE runs SET exhausted=1 WHERE id=?',(key,))
            retries=journal.db.execute('SELECT code,x,y FROM failures WHERE run=? AND retry_at<=? LIMIT ?',(key,time.time(),args.batch_size)).fetchall()
            if retries:batch(key,s,z,[tuple(r) for r in retries],retry=True)
        failed=sum(journal.failed(k) for k,_,_ in active)
        status('retrying' if failed else 'complete')
        if args.once:raise SystemExit(1 if failed else 0)
        # Stay alive after completion; container restarts do not create a tight loop.
        time.sleep(30 if failed else 300)

if __name__=='__main__':main()
