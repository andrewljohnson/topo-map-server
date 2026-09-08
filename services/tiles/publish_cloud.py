#!/usr/bin/env python3
"""Generate locally and publish verified immutable tiles to private R2; resumable."""
import argparse,base64,fcntl,hashlib,importlib,json,os,shutil,sqlite3,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from cloud_config import load,client

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
SOURCES=('osm','dem','boundaries','landcover','trails','amenities','waterways','recreation')
MODULES={'osm':'national_basemap','dem':'national_dem','boundaries':'national_boundaries','landcover':'national_landcover','trails':'national_trails','amenities':'national_amenities','waterways':'national_waterways','recreation':'national_recreation'}

def validate(blob,source,z=None):
    if len(blob)>4000000:raise ValueError('Tile exceeds cloud delivery limit')
    if source=='dem':
        from PIL import Image
        import io
        with Image.open(io.BytesIO(blob)) as image:
            image.load()
            if image.size not in ((256,256),(512,512)) or z is not None and z>=12 and image.size!=(512,512):raise ValueError('DEM must be 256px overview or 512px detail')
    else:
        import mapbox_vector_tile
        mapbox_vector_tile.decode(blob)

class Publisher:
    def __init__(self,config,data,limit=1000000000000):
        self.config=config;self.client=client(config);self.data=data;self.limit=limit
        self.folder=data/'publication';self.folder.mkdir(exist_ok=True,parents=True)
        self.dbpath=self.folder/'uploads.sqlite'
        with self.db() as db:db.executescript('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS uploads(key TEXT PRIMARY KEY,size INTEGER,sha TEXT,done INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS cursors(plan TEXT PRIMARY KEY,code INTEGER);')
    def db(self):return sqlite3.connect(self.dbpath,timeout=60)
    def put(self,key,blob,content_type):
        checksum=hashlib.sha256(blob).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT size,sha,done FROM uploads WHERE key=?',(key,)).fetchone()
            if row and row[:2]!=(len(blob),checksum):raise ValueError('Immutable dataset changed; bump its version')
            if row and row[2]:return
            total=db.execute('SELECT COALESCE(SUM(size),0) FROM uploads').fetchone()[0]
            if not row and total+len(blob)>self.limit:raise RuntimeError('Publication storage ceiling reached')
            db.execute('INSERT OR IGNORE INTO uploads(key,size,sha) VALUES(?,?,?)',(key,len(blob),checksum))
        # Verify a prior upload after a crash before writing it again.
        try:head=self.client.head_object(Bucket=self.config['R2_BUCKET'],Key=key)
        except Exception as exc:
            if getattr(exc,'response',{}).get('Error',{}).get('Code') not in ('404','NoSuchKey','NotFound'):raise
            head=None
        if head and (head['ContentLength']!=len(blob) or head.get('Metadata',{}).get('sha256')!=checksum):raise ValueError('Cloud object differs from this dataset')
        if not head:
            self.client.put_object(Bucket=self.config['R2_BUCKET'],Key=key,Body=blob,ContentType=content_type,Metadata={'sha256':checksum})
            head=self.client.head_object(Bucket=self.config['R2_BUCKET'],Key=key)
        if head['ContentLength']!=len(blob) or head.get('Metadata',{}).get('sha256')!=checksum:raise ValueError('Upload verification failed')
        with self.db() as db:db.execute('UPDATE uploads SET done=1 WHERE key=?',(key,))
    def tile(self,source,z,x,y,spec):
        key='tiles/v1/'+spec['datasetId']+f'/{z}/{x}/{y}'+('.png' if source=='dem' else '.pbf')
        with self.db() as db:row=db.execute('SELECT done FROM uploads WHERE key=?',(key,)).fetchone()
        if row and row[0]:return
        if shutil.disk_usage(self.data).free<50*10**9:raise RuntimeError('Local 50 GB disk reserve reached')
        path=self.data/'cache'/spec['datasetId']/str(z)/str(x)/f'{y}.pbf'
        if path.exists():
            blob=path.read_bytes()
            try:validate(blob,source,z)
            except ValueError:blob=importlib.import_module(MODULES[source]).render_tile(z,x,y)
        else:blob=importlib.import_module(MODULES[source]).render_tile(z,x,y)
        validate(blob,source,z)
        self.put(key,blob,'image/png' if source=='dem' else 'application/vnd.mapbox-vector-tile')
    def document(self,name,value):
        blob=json.dumps(value,separators=(',',':')).encode()
        self.client.put_object(Bucket=self.config['R2_BUCKET'],Key='publication/'+name,Body=blob,ContentType='application/json',CacheControl='no-cache')
        path=self.folder/name;tmp=path.with_suffix('.tmp');tmp.write_bytes(blob);tmp.replace(path)
    def status(self,state,current=None,error=None):
        with self.db() as db:count,size=db.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM uploads WHERE done=1').fetchone()
        self.document('status.json',{'status':state,'updatedAt':time.time(),'uploadedTiles':count,'uploadedBytes':size,'storageLimitBytes':self.limit,'current':current,'error':error})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',action='store_true');p.add_argument('--plan',action='store_true');p.add_argument('--data',type=Path,default=DATA);p.add_argument('--max-bytes',type=int,default=1000000000000);a=p.parse_args()
    os.environ.update(TILE_MODE='national',TILE_COVERAGE='world-conus',TILE_DATA_DIR=str(a.data),OSM_REQUIRE_BULK='1')
    import tile_service,coverage_policy
    from warm_us import coordinates,tile_count
    from shapely.geometry import box
    from shapely.prepared import prep
    info=tile_service.metadata();specs=info['tilesets']
    info['publication']={'status':'warming','worldMaxZoom':7,'detailRegion':'CONUS'}
    plans=[('osm',z,prep(box(0,0,1,1))) for z in range(8)]
    # Spatially prioritize California before the complete CONUS detail pass.
    west,north=coverage_policy.project(-124.5,42.1);east,south=coverage_policy.project(-114,32.4)
    ca=box(west,north,east,south)
    for group in (('osm','dem'),tuple(s for s in SOURCES if s not in ('osm','dem'))):
        for region in (ca,None):
            for z in range(15):
                for source in group:
                    if not specs[source]['minZoom']<=z<=specs[source]['maxZoom'] or source=='osm' and z<=7:continue
                    geom=coverage_policy.geometry(z,source=='dem').context
                    plans.append((source,z,prep(geom.intersection(region) if region is not None else geom)))
    if a.plan:
        print(json.dumps({'worldOverviewTiles':21845,'plans':[{'source':s,'zoom':z,'tiles':tile_count(g,z)} for s,z,g in plans]}));return
    config=load();publisher=Publisher(config,a.data,a.max_bytes)
    lock=(publisher.folder/'publisher.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Refuse an unrelated populated bucket when there is no local upload ledger.
    with publisher.db() as db:known=db.execute('SELECT COUNT(*) FROM uploads').fetchone()[0]
    if not known:
        existing=publisher.client.list_objects_v2(Bucket=config['R2_BUCKET'],Prefix='tiles/v1/',MaxKeys=1)
        if existing.get('Contents'):raise RuntimeError('Restore the publication ledger before using a populated bucket')
    publisher.document('metadata.json',info)
    last_status=0;last_prune=0;last_priority=0
    pool=ThreadPoolExecutor(max_workers=2)
    def priorities():
        nonlocal last_priority
        if time.monotonic()-last_priority<60:return
        last_priority=time.monotonic();private=Path.home()/'.config/topo-map'
        if not (private/'deployment.json').exists():return
        try:
            url=json.loads((private/'deployment.json').read_text())['url']+'/operator/jobs'
            headers={'Authorization':'Bearer '+(private/'warm.token').read_text().strip()}
            with urlopen(Request(url,headers=headers),timeout=20) as response:jobs=json.load(response)['jobs']
            ack=[]
            for job in jobs[:16]:
                source=job['source'];z,x,y=map(int,job['key'].split('/'))
                if source not in specs or job['datasetId']!=specs[source]['datasetId'] or not coverage_policy.allowed(source,z,x,y):ack.append(job['id']);continue
                if source not in ('osm','dem') and not (a.data/'osm-source/us-enrichment.sqlite').exists():continue
                try:publisher.tile(source,z,x,y,specs[source]);ack.append(job['id'])
                except Exception:pass
            if ack:
                with urlopen(Request(url,headers=headers,data=json.dumps({'ack':ack}).encode()),timeout=20) as response:response.read()
        except Exception:pass
    def run(source,z,items):
        nonlocal last_status
        if not a.sample:priorities()
        list(pool.map(lambda item:publisher.tile(source,z,item[1],item[2],specs[source]),items))
        if time.monotonic()-last_status>30:
            publisher.status('warming',{'source':source,'zoom':z});last_status=time.monotonic()
    if a.sample:
        for z in range(4):run('osm',z,list(coordinates(prep(box(0,0,1,1)),z)))
        for source in SOURCES:
            # Existing detail around Fallen Leaf Lake validates every composited layer.
            for z in range(specs[source]['minZoom'],specs[source]['maxZoom']+1):
                if source=='osm' and z<4:continue
                x,y=coverage_policy.project(-120.055,38.93);n=2**z
                keys=[(0,int(x*n)+dx,int(y*n)+dy) for dx in (-1,0,1) for dy in (-1,0,1) if 0<=int(x*n)+dx<n and 0<=int(y*n)+dy<n]
                for item in keys:
                    try:run(source,z,[item])
                    except Exception as exc:print('Sample tile pending:',source,z,type(exc).__name__,flush=True)
        publisher.status('sample-published');return
    imported=False
    for index,(source,z,geom) in enumerate(plans):
        if source not in ('osm','dem') and not imported:
            from prepare_us import prepare
            while True:
                try:
                    publisher.status('preparing-local-osm');prepare(a.data);imported=True;break
                except Exception as exc:
                    publisher.status('paused-source-import',error=type(exc).__name__);time.sleep(60)
        plan=hashlib.sha256((str(index)+specs[source]['datasetId']+geom.context.wkb_hex).encode()).hexdigest()
        with publisher.db() as db:row=db.execute('SELECT code FROM cursors WHERE plan=?',(plan,)).fetchone()
        pending=[]
        for item in coordinates(geom,z,row[0] if row else -1):
            pending.append(item)
            if len(pending)<4:continue
            while True:
                try:run(source,z,pending);break
                except Exception as exc:
                    publisher.status('paused-retrying',{'source':source,'zoom':z},type(exc).__name__);time.sleep(60)
            with publisher.db() as db:db.execute('INSERT OR REPLACE INTO cursors VALUES(?,?)',(plan,pending[-1][0]))
            pending=[]
            # Keep replaceable source caches bounded, without touching dev tiles.
            if time.monotonic()-last_prune>300:
                import scratch_cache
                scratch_cache.prune(a.data,30000000000);last_prune=time.monotonic()
        if pending:
            while True:
                try:run(source,z,pending);break
                except Exception as exc:publisher.status('paused-retrying',error=type(exc).__name__);time.sleep(60)
            with publisher.db() as db:db.execute('INSERT OR REPLACE INTO cursors VALUES(?,?)',(plan,pending[-1][0]))
    info['publication']['status']='complete';publisher.document('metadata.json',info);publisher.status('complete')
if __name__=='__main__':main()
