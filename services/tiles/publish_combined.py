#!/usr/bin/env python3
"""Resumable combined-z12 generation and verified rolling R2 publication.

The default pilot contains Tahoe/SF detail and worldwide z0–3 overview. CONUS is
an explicit separate scope; no invocation silently expands the pilot nationwide.
"""
import argparse,fcntl,gzip,hashlib,importlib,io,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/tahoe'))
from publish_cloud import Publisher
from cloud_config import load
from build import REGIONS,atomic,morton_key,SOURCES
from benchmark_overviews import combine_native,SOURCES as OVERVIEW_SOURCES
DATA=ROOT/'services/tiles/data'


def compact(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def fingerprint():
 files=[*sorted((ROOT/'services/tiles').glob('*.py')),ROOT/'experiments/tahoe/build.py',ROOT/'experiments/tahoe/benchmark_overviews.py']
 return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in files)).hexdigest()
def rectangles(keys):
 # Row runs form exact coverage, never a rectangle covering ungenerated holes.
 rows={}
 for z,x,y in keys:rows.setdefault((z,y),set()).add(x)
 result={}
 for (z,y),xs in sorted(rows.items()):
  start=end=None
  for x in sorted(xs):
   if end is not None and x==end+1:end=x;continue
   if start is not None:result.setdefault(str(z),[]).append([start,y,end,y])
   start=end=x
  if start is not None:result.setdefault(str(z),[]).append([start,y,end,y])
 return result

def plan(scope):
 if scope=='pilot':parents=sorted(set(REGIONS['tahoe-10x']+REGIONS['sf-10x']),key=morton_key);world=3
 else:
  from coverage_policy import geometry
  from warm_us import coordinates
  parents=sorted({(x,y) for _,x,y in coordinates(geometry(12),12)},key=morton_key);world=7
 dem=sorted({(x+dx,y+dy) for x,y in parents for dx in (-1,0,1) for dy in (-1,0,1) if 0<=x+dx<4096 and 0<=y+dy<4096},key=morton_key)
 overview=[(z,x,y) for z in range(world+1) for x in range(2**z) for y in range(2**z)]
 for z in range(world+1,12):overview.extend((z,x,y) for x,y in sorted({(x//2**(12-z),y//2**(12-z)) for x,y in parents},key=morton_key))
 return {'scope':scope,'parents':parents,'dem':dem,'overview':overview,'worldMaxZoom':world}

def metadata(release,work):
 from build import bounds
 base_id=release+'-base';dem_id=release+'-dem';prefix='/releases/'+release
 coverage=rectangles([*work['overview'],*((12,x,y) for x,y in work['parents'])]);dem_coverage=rectangles((12,x,y) for x,y in work['dem'])
 render=[]
 for points in ([REGIONS['tahoe-10x'],REGIONS['sf-10x']] if work['scope']=='pilot' else [work['parents']]):
  west,south,_,_=bounds(12,min(x for x,y in points),max(y for x,y in points));_,_,east,north=bounds(12,max(x for x,y in points),min(y for x,y in points));render.append([west,south,east,north])
 world=[-180,-85.0511,180,85.0511]
 base={'datasetId':base_id,'tileUrl':prefix+'/tiles/{z}/{x}/{y}.pbf?datasetId='+base_id,'batchUrl':prefix+'/tile-batch','batchSize':4,'minZoom':0,'maxZoom':12,'bounds':world,'coverage':coverage,'format':'mvt','encoding':'gzip','extent':16384}
 dem={'datasetId':dem_id,'tileUrl':prefix+'/dem/{z}/{x}/{y}.png?datasetId='+dem_id,'batchUrl':prefix+'/dem-batch','batchSize':4,'minZoom':12,'maxZoom':12,'bounds':[min(b[0] for b in render),min(b[1] for b in render),max(b[2] for b in render),max(b[3] for b in render)],'renderBounds':render,'coverage':dem_coverage,'format':'png','encoding':'terrarium','tileSize':1024,'halo':1,'attribution':'Elevation: USGS 3DEP · Mapzen terrain'}
 return {'name':'Topo · '+('Tahoe and San Francisco pilot' if work['scope']=='pilot' else 'United States'),'releaseId':release,'combined':True,'logicalSources':list(SOURCES),'overviewMaxZoom':work['worldMaxZoom'],'datasetId':base_id,'tileUrl':base['tileUrl'],'batchUrl':base['batchUrl'],'batchSize':4,'bounds':world,'center':[-120.05,38.92626],'initialZoom':12.5,'minZoom':0,'maxZoom':12,'gridZoom':12,'tilesets':{'osm':base,'dem':dem},'publication':{'status':'pilot-complete' if work['scope']=='pilot' else 'complete','detailRegion':'Tahoe and San Francisco' if work['scope']=='pilot' else 'CONUS','worldMaxZoom':work['worldMaxZoom']}}

def validate_combined(blob,source):
 if len(blob)>4000000:raise ValueError('Tile exceeds four MB delivery ceiling')
 if source=='dem':
  from PIL import Image
  with Image.open(io.BytesIO(blob)) as im:
   im.load()
   if im.size!=(1024,1024) or im.mode not in ('RGB','RGBA'):raise ValueError('Detailed DEM must be 1024px Terrarium')
 else:
  import mapbox_vector_tile
  with gzip.GzipFile(fileobj=io.BytesIO(blob)) as f:raw=f.read(4000001)
  if len(raw)>4000000:raise ValueError('Decoded base exceeds four MB ceiling')
  tile=mapbox_vector_tile.decode(raw)
  if any('__' not in name or name.split('__')[0] not in SOURCES for name in tile):raise ValueError('Unnamespaced vector layer')

def generate_overview(task):
 z,x,y,path=task
 from coverage_policy import allowed
 children=[]
 for source,(module,minzoom) in OVERVIEW_SOURCES.items():
  # Worldwide broad base is OSM; detailed ancillary sources start on regional overviews.
  if z<4 and source!='osm':continue
  if z>=minzoom and allowed(source,z,x,y):children.append((source,importlib.import_module(module).render_tile(z,x,y)))
 atomic(Path(path),gzip.compress(combine_native(children),mtime=0))
 return path

def ensure_limits(folder):
 if shutil.disk_usage(DATA).free<50*10**9:raise RuntimeError('Paused: 50 GB free disk reserve reached')
 size=0
 for p in folder.rglob('*'):
  try:
   if p.is_file():size+=p.stat().st_size
  except FileNotFoundError:pass
 if size>25*10**9:raise RuntimeError('Paused: 25 GB scratch/spool ceiling reached')

def immutable_document(publisher,key,value):publisher.put(key,compact(value),'application/json',verify_body=True)

def run(args):
 if not re.fullmatch('[a-z0-9-]{1,65}',args.release):raise ValueError('Use a lowercase release identifier')
 work=plan(args.scope);info=metadata(args.release,work)
 counts={'base':len(work['parents'])+len(work['overview']),'dem':len(work['dem'])}
 folder=DATA/'publication/combined'/args.release;folder.mkdir(parents=True,exist_ok=True)
 contract={'version':1,'release':args.release,'scope':args.scope,'codeFingerprint':fingerprint(),'sourceDatasets':{s:getattr(importlib.import_module(m),'DATASET_ID',None) for s,m in {**SOURCES,'dem':'national_dem'}.items()},'planSha256':hashlib.sha256(compact(work)).hexdigest(),'counts':counts,'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
 if args.action=='plan':print(json.dumps({'contract':contract,'metadata':info},indent=2));return
 config=load();publisher=Publisher(config,DATA,args.max_bytes)
 lock=(publisher.folder/'publisher.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 path=folder/'contract.json'
 if path.exists():
  previous=json.loads(path.read_text())
  if any(previous[k]!=contract[k] for k in ('codeFingerprint','planSha256','release','scope')):raise ValueError('Release inputs changed: use a new release identifier')
  contract=previous
 else:atomic(path,compact(contract));atomic(folder/'plan.json',compact(work))
 if args.action in ('promote','rollback'):
  if args.action=='promote':
   stored=publisher.client.get_object(Bucket=config['R2_BUCKET'],Key='publication/releases/'+args.release+'/metadata.json')['Body'].read();candidate=json.loads(stored)
   if candidate!=info:raise ValueError('Candidate manifest differs')
   # Publication pointer is the only mutable release switch. Backup first.
   old=publisher.client.get_object(Bucket=config['R2_BUCKET'],Key='publication/metadata.json')['Body'].read()
   backup=folder/'previous-metadata.json'
   if not backup.exists():atomic(backup,old)
   publisher.document('metadata.json',info)
  else:publisher.document('metadata.json',json.loads((folder/'previous-metadata.json').read_text()))
  print(args.action,args.release);return
 start=time.monotonic();status={'release':args.release,'status':'running','counts':counts,'startedAt':time.time()}
 def report(**extra):
  status.update(extra,elapsedSeconds=time.monotonic()-start,performance=publisher.performance());atomic(folder/'status.json',compact(status));print(json.dumps({k:v for k,v in status.items() if k!='performance'}),flush=True)
 def upload_tree(out):
  files=[*(out/'base').glob('*/*/*.pbf'),*(out/'dem').glob('*/*/*.png')]
  def put(path):
   source='dem' if path.suffix=='.png' else 'osm';spec=info['tilesets'][source];key='tiles/v1/'+spec['datasetId']+'/'+str(path.relative_to(out/('dem' if source=='dem' else 'base')))
   blob=path.read_bytes();validate_combined(blob,source);publisher.put(key,blob,'image/png' if source=='dem' else 'application/vnd.mapbox-vector-tile',content_encoding=None if source=='dem' else 'gzip',verify_body=True)
  with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(put,files))
  # Keep provenance/report and a completed marker before pruning only our own scratch.
  reports=folder/'reports';reports.mkdir(exist_ok=True)
  if (out/'report.json').exists():shutil.copy2(out/'report.json',reports/(out.name+'.json'))
  atomic(folder/(out.name+'.done'),compact({'files':len(files),'verifiedAt':time.time()}))
  if not out.resolve().is_relative_to(folder/'spool'):raise ValueError('Refusing unsafe scratch eviction')
  shutil.rmtree(out)
 try:
  immutable_document(publisher,'publication/releases/'+args.release+'/contract.json',contract)
  # One upload shard may overlap generation of the next: bounded to two shards.
  with ThreadPoolExecutor(max_workers=1) as upload_pool:
   pending=None
   batches=[('overview-'+str(i//256),'overview',work['overview'][i:i+256]) for i in range(0,len(work['overview']),256)]
   batches += [('detail-'+str(i//args.shard_size),'detail',work['parents'][i:i+args.shard_size]) for i in range(0,len(work['parents']),args.shard_size)]
   for name,kind,keys in batches:
    if (folder/(name+'.done')).exists():continue
    ensure_limits(folder/'spool');out=folder/'spool'/name;out.mkdir(parents=True,exist_ok=True);report(shard=name,phase='generating')
    if not (out/'generated.json').exists():
     if kind=='overview':
      # Process pool keeps native source geometry preparation parallel and bounded.
      import multiprocessing
      from concurrent.futures import ProcessPoolExecutor
      with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:list(pool.map(generate_overview,[(z,x,y,str(out/'base'/str(z)/str(x)/(str(y)+'.pbf'))) for z,x,y in keys],chunksize=8))
     else:
      atomic(out/'parents.json',compact(keys))
      command=[sys.executable,str(ROOT/'experiments/tahoe/build.py'),'--parent-file',str(out/'parents.json'),'--output',str(out),'--workers',str(args.workers),'--spatial-order','morton','--task-chunksize','64']
      with (out/'build.log').open('a') as log:subprocess.run(command,cwd=ROOT,env={**os.environ,'TOPO_SCRATCH_ROOT':str(out/'raw')},stdout=log,stderr=subprocess.STDOUT,check=True)
     atomic(out/'generated.json',compact({'keys':len(keys)}))
    ensure_limits(folder/'spool')
    if pending:pending.result()
    report(shard=name,phase='uploading');pending=upload_pool.submit(upload_tree,out)
   if pending:pending.result()
  # Every manifest coordinate must be in the verified object ledger.
  expected=[]
  for source,keys in [('osm',[*work['overview'],*((12,x,y) for x,y in work['parents'])]),('dem',[(12,x,y) for x,y in work['dem']])]:
   dataset=info['tilesets'][source]['datasetId'];ext='.png' if source=='dem' else '.pbf'
   expected.extend('tiles/v1/'+dataset+f'/{z}/{x}/{y}'+ext for z,x,y in keys)
  with publisher.db() as db:
   for key in expected:
    if db.execute('SELECT done FROM uploads WHERE key=?',(key,)).fetchone()!=(1,):raise ValueError('Coverage verification failed: '+key)
  immutable_document(publisher,'publication/releases/'+args.release+'/metadata.json',info)
  report(status='complete',phase='verified',verifiedObjects=len(expected))
 except Exception as exc:report(status='paused-error',error=str(exc));raise
 print('Candidate API: /releases/'+args.release+'/metadata',flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('plan','publish','promote','rollback'));p.add_argument('--release',required=True);p.add_argument('--scope',choices=('pilot','conus'),default='pilot');p.add_argument('--workers',type=int,choices=range(1,9),default=8);p.add_argument('--shard-size',type=int,choices=range(1,513),default=256);p.add_argument('--max-bytes',type=int,default=500000000000);run(p.parse_args())
if __name__=='__main__':main()
