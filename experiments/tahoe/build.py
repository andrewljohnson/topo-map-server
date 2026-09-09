#!/usr/bin/env python3
"""Bounded staged correctness/performance experiments: finest vector children -> combined z12; raw DEM mosaic."""
import argparse,gzip,hashlib,importlib,json,os,sys,time,shutil,resource,multiprocessing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
os.environ.update(TILE_MODE='national',OSM_REQUIRE_BULK='1',TILE_DATA_DIR=str(ROOT/'services/tiles/data'))
import mapbox_vector_tile as mvt
import numpy as np
from shapely.geometry import shape,box,GeometryCollection
from shapely.affinity import affine_transform
from shapely.ops import unary_union,linemerge
from shapely import make_valid
from national_boundaries import bounds
from national_dem import decode_png,encode_png
SOURCES={'osm':'national_basemap','boundaries':'national_boundaries','landcover':'national_landcover','trails':'national_trails','amenities':'national_amenities','waterways':'national_waterways','recreation':'national_recreation'}
OUT=ROOT/'services/tiles/data/experiments/tahoe-z12-v1'
PARENTS=[(681,1566),(682,1566),(681,1567),(682,1567)]
REGIONS={
 'tahoe':PARENTS,
 'tahoe-10x':[(x,y) for y in range(1560,1568) for x in range(680,685)],
 'sierra-100x':[(x,y) for y in range(1552,1572) for x in range(672,692)],
 'nyc-stress':[(x,y) for y in range(1539,1541) for x in range(1205,1207)],
 'sf-10x':[(x,y) for y in range(1580,1588) for x in range(653,658)],
 'smokies-10x':[(x,y) for y in range(1610,1618) for x in range(1095,1100)],
 'desert-10x':[(x,y) for y in range(1601,1609) for x in range(733,738)],
 'western-1000x':[(x,y) for y in range(1536,1586) for x in range(675,755)],
}
EXTENT=16384

def morton_key(xy):
 return sum(((xy[0]>>bit)&1)<<(bit*2) | ((xy[1]>>bit)&1)<<(bit*2+1) for bit in range(14))

def atomic(path,blob):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');temp.write_bytes(blob);temp.replace(path)
def merge_tiles(children):
 groups={};counts={}
 for source,dx,dy,blob in children:
  for name,layer in mvt.decode(blob,default_options={'y_coord_down':True}).items():
   target=source+'__'+name;counts[target]=counts.get(target,0)+len(layer['features'])
   extent=layer['extent'];direct=dx is None;scale=(EXTENT if direct else 4096)/extent
   clip=box(0,0,EXTENT,EXTENT) if direct else box(-64 if dx==0 else 0,-64 if dy==0 else 0,4160 if dx==3 else 4096,4160 if dy==3 else 4096)
   for f in layer['features']:
    g=affine_transform(make_valid(shape(f['geometry'])),[scale,0,0,scale,0,0]).intersection(clip)
    if g.is_empty:continue
    if not direct:g=affine_transform(g,[1,0,0,1,dx*4096,dy*4096])
    props=f['properties'];key=(target,f.get('id',0),json.dumps(props,sort_keys=True,separators=(',',':')))
    groups.setdefault(key,[]).append(g)
 layers={}
 for (name,ident,props),parts in groups.items():
  g=unary_union(parts)
  if g.geom_type=='MultiLineString':g=linemerge(g)
  pieces=list(g.geoms) if g.geom_type in ('GeometryCollection','MultiPoint') else [g]
  for piece in pieces:
   if piece.is_empty:continue
   layers.setdefault(name,[]).append({'geometry':piece,'properties':json.loads(props),'id':ident})
 return mvt.encode([{'name':name,'features':features} for name,features in sorted(layers.items())],default_options={'extents':EXTENT,'y_coord_down':True}),counts

def acquire(task):
 source,z,x,y,regenerate,legacy_base,output=task
 output=Path(output);path=output/'derived'/source/str(z)/str(x)/f'{y}.pbf';start=time.monotonic()
 hit=path.exists() and not regenerate
 if hit:blob=path.read_bytes()
 else:
  module=importlib.import_module(SOURCES[source])
  options={'basemap_tile':(output/'derived/osm'/str(z)/str(x)/f'{y}.pbf').read_bytes()} if source=='trails' and not legacy_base else {}
  blob=module.render_tile(z,x,y,**options);atomic(path,blob)
 return x%4,y%4,blob,time.monotonic()-start,hit


def prefetch_dem(keys,workers=16):
 import national_contours as usgs
 chunks=set()
 for x,y in keys:
  for dx in (0,1):
   for dy in (0,1):chunks.update(usgs.chunks_for_tile(13,x*2+dx,y*2+dy))
 missing=[key for key in sorted(chunks) if not all((usgs.CACHE/'windows'/f'{key[0]}_{key[1]}{suffix}').exists() for suffix in ('.npz','.json'))]
 start=time.monotonic()
 def fetch(key):usgs.load_chunk(*key);return 1
 if missing and workers:
  with ThreadPoolExecutor(max_workers=workers) as pool:
   for _ in pool.map(fetch,missing):pass
 return {'requiredNativeChunks':len(chunks),'missingNativeChunks':len(missing),'prefetchWorkers':workers,'prefetchSeconds':time.monotonic()-start}

def dem_parent(task):
 x,y,legacy,output,compression=task;canvas=np.empty((1024,1024),dtype='float32');module=importlib.import_module('national_dem')
 for dy in range(2):
  for dx in range(2):
   canvas[dy*512:(dy+1)*512,dx*512:(dx+1)*512]=decode_png(module.render_tile(13,x*2+dx,y*2+dy)) if legacy else module.render_samples(13,x*2+dx,y*2+dy)
 blob=encode_png(canvas,compression=compression);atomic(Path(output)/'dem/12'/str(x)/f'{y}.png',blob);return len(blob)

def pack_parent(task):
 x,y,children,output=task;start=time.monotonic();blob,counts=merge_tiles(children);compressed=gzip.compress(blob,mtime=0)
 atomic(Path(output)/'base/12'/str(x)/f'{y}.pbf',compressed)
 return {'key':f'12/{x}/{y}','bytes':len(blob),'gzipBytes':len(compressed),'packSeconds':time.monotonic()-start,'sourceFeatureCounts':counts,'sha256':hashlib.sha256(blob).hexdigest()}

def recreation_cell(parents):
 """Prepare each shared source cell once, independently of other cells."""
 module=importlib.import_module(SOURCES['recreation']);x,y=parents[0]
 start=time.monotonic();prepared=module.prepare_cell(14,x//4,y//4)
 seconds=time.monotonic()-start
 return [(x,y,module.render_tile(12,x,y,detail_zoom=14,extent=EXTENT,prepared=prepared)) for x,y in parents],seconds

def main():
 p=argparse.ArgumentParser();p.add_argument('--clean-derived',action='store_true');p.add_argument('--workers',type=int,choices=range(1,33),default=4);p.add_argument('--legacy-recreation',action='store_true');p.add_argument('--legacy-trail-basemap',action='store_true',help='Normalize the OSM input again inside the trail stage');p.add_argument('--legacy-dem',action='store_true',help='Encode/decode intermediate child PNGs for comparison');p.add_argument('--regenerate-vectors',action='store_true',help='Ignore derived vector files while preserving raw inputs and current served outputs');p.add_argument('--executor',choices=('threads','processes'),default='processes');p.add_argument('--region',choices=tuple(REGIONS),default='tahoe');p.add_argument('--serial-pack',action='store_true');p.add_argument('--serial-recreation',action='store_true',help='Benchmark serial source-cell preparation');p.add_argument('--spatial-order',choices=('row','morton'),default='row');p.add_argument('--task-chunksize',type=int,choices=(1,4,16,64),default=1);p.add_argument('--dem-executor',choices=('threads','processes'),default='processes');p.add_argument('--dem-prefetch-workers',type=int,choices=range(0,33),default=16);p.add_argument('--dem-workers',type=int,choices=range(1,33));p.add_argument('--dem-compression',type=int,choices=range(1,10),default=3);p.add_argument('--parent-file',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 out=OUT if a.region=='tahoe' else OUT.parent/(a.region+'-z12-v1')
 parents=sorted(REGIONS[a.region],key=morton_key) if a.spatial_order=='morton' else REGIONS[a.region]
 if a.parent_file:
  parents=[tuple(key) for key in json.loads(a.parent_file.read_text())]
  if not 1<=len(parents)<=512 or len(set(parents))!=len(parents) or any(len(k)!=2 or any(type(v)!=int or not 0<=v<4096 for v in k) for k in parents):raise ValueError('Use 1–512 unique z12 parents')
  if not a.output:raise ValueError('A shard requires its own output directory')
  out=a.output.resolve();allowed=ROOT/'services/tiles/data/publication/combined'
  if not out.is_relative_to(allowed) or a.clean_derived:raise ValueError('Shard output must be disposable combined publication scratch')
  out.parent.mkdir(parents=True,exist_ok=True)
 if shutil.disk_usage(out.parent).free<50*10**9:raise RuntimeError('Experiment requires 60 GiB free disk reserve; release only expendable experiment outputs before continuing')
 if a.clean_derived and out.exists():shutil.rmtree(out)
 out.mkdir(parents=True,exist_ok=True);start=time.monotonic();report={'workers':a.workers,'executor':a.executor,'region':a.region,'taskChunksize':a.task_chunksize,'spatialOrder':a.spatial_order,'vectorParents':len(parents),'sources':{},'parents':[],'mode':'legacy-fine-children correctness baseline' if a.legacy_recreation else 'direct full-detail recreation + fine-child vector baseline','sourceCache':'retained local inputs; cache misses fetched','startedAt':time.time(),'loadAverageStart':os.getloadavg(),'pipeline':{'directRecreation':not a.legacy_recreation,'rawDemMosaic':not a.legacy_dem,'reuseTrailBasemap':not a.legacy_trail_basemap,'parallelPacking':a.executor=='processes' and not a.serial_pack}}
 parent_children={xy:[] for xy in parents}
 executor=ThreadPoolExecutor if a.executor=='threads' else ProcessPoolExecutor
 options={} if a.executor=='threads' else {'mp_context':multiprocessing.get_context('spawn')}
 with executor(max_workers=a.workers,**options) as pool:
  for source in SOURCES:
   if source=='recreation' and not a.legacy_recreation:
    t=time.monotonic();cells={};prepare_seconds=0
    for x,y in parents:cells.setdefault((x//4,y//4),[]).append((x,y))
    prepared=map(recreation_cell,cells.values()) if a.serial_recreation else pool.map(recreation_cell,cells.values())
    for encoded,seconds in prepared:
     prepare_seconds+=seconds
     for x,y,blob in encoded:parent_children[(x,y)].append((source,None,None,blob))
    report['sources'][source]={'seconds':time.monotonic()-t,'preparedCells':len(cells),'prepareSeconds':prepare_seconds,'parentTiles':len(parents),'childTiles':0,'derivedCacheHits':0,'parallelCells':not a.serial_recreation}
    atomic(out/'progress.json',json.dumps(report).encode());print(source,report['sources'][source],flush=True);continue
   t=time.monotonic();hits=0;prepare_seconds=0
   tasks=[(source,14,x*4+dx,y*4+dy) for x,y in parents for dy in range(4) for dx in range(4)]
   if source=='trails' and a.executor=='threads' and (a.regenerate_vectors or any(not (out/'derived'/source/str(z)/str(x)/f'{y}.pbf').exists() for _,z,x,y in tasks)):
    # Populate the immutable PCT cache before parallel workers can duplicate
    # its expensive first construction. Include preparation in source timing.
    importlib.import_module(SOURCES[source]).pct_features();prepare_seconds=time.monotonic()-t
   for task,result in zip(tasks,pool.map(acquire,[(source,z,x,y,a.regenerate_vectors,a.legacy_trail_basemap,str(out)) for source,z,x,y in tasks],chunksize=a.task_chunksize)):
    dx,dy,blob,seconds,hit=result;hits+=int(hit);parent_children[(task[2]//4,task[3]//4)].append((source,dx,dy,blob))
   report['sources'][source]={'seconds':time.monotonic()-t,'childTiles':len(tasks),'derivedCacheHits':hits,'prepareSeconds':prepare_seconds,'reusedBasemapTiles':len(tasks)-hits if source=='trails' and not a.legacy_trail_basemap else 0}
   atomic(out/'progress.json',json.dumps(report).encode());print(source,report['sources'][source],flush=True)
  packing_start=time.monotonic();packing_tasks=[(x,y,children,str(out)) for (x,y),children in parent_children.items()]
  packed=pool.map(pack_parent,packing_tasks) if a.executor=='processes' and not a.serial_pack else map(pack_parent,packing_tasks)
  report['parents']=list(packed);report['packingWallSeconds']=time.monotonic()-packing_start
 parent_children.clear();del packing_tasks
 dem_workers=a.dem_workers or min(16,a.workers)
 dem_executor=ThreadPoolExecutor if a.dem_executor=='threads' else ProcessPoolExecutor
 dem_options={} if a.dem_executor=='threads' else {'mp_context':multiprocessing.get_context('spawn')}
 dem_start=time.monotonic()
 # Halo supplies neighboring elevation samples for contour stitching.
 dem_keys=sorted({(x+dx,y+dy) for x,y in parents for dx in (-1,0,1) for dy in (-1,0,1)})
 if a.spatial_order=='morton':dem_keys.sort(key=morton_key)
 prefetch=prefetch_dem(dem_keys,a.dem_prefetch_workers)
 generation_start=time.monotonic()
 with dem_executor(max_workers=dem_workers,**dem_options) as dem_pool:
  report['dem']={'tiles':len(dem_keys),'bytes':sum(dem_pool.map(dem_parent,[(x,y,a.legacy_dem,str(out),a.dem_compression) for x,y in dem_keys])),'seconds':time.monotonic()-dem_start,'tileSize':1024,'compressionLevel':a.dem_compression,'executor':a.dem_executor,'workers':dem_workers,**prefetch,'generationSeconds':time.monotonic()-generation_start,'intermediateChildPngs':len(dem_keys)*4 if a.legacy_dem else 0}
 w,s,_,_=bounds(12,min(x for x,y in parents),max(y for x,y in parents));_,_,e,n=bounds(12,max(x for x,y in parents),min(y for x,y in parents))
 metadata={'name':a.region+' zoom-12 experiment','publicAccess':True,'bounds':[w,s,e,n],'center':[-120.035,38.905] if a.region=='tahoe' else [(w+e)/2,(s+n)/2],'initialZoom':12.5,'minZoom':12,'maxZoom':12,'datasetId':a.region+'-combined-v1','tileUrl':'/base/{z}/{x}/{y}.pbf','combined':True,'tilesets':{'dem':{'datasetId':a.region+'-dem-v1','tileUrl':'/dem/{z}/{x}/{y}.png','bounds':[w,s,e,n],'minZoom':12,'maxZoom':12,'tileSize':1024,'attribution':'Elevation: USGS 3DEP · Mapzen terrain'}}}
 usage=resource.getrusage(resource.RUSAGE_SELF);report['resources']={'userCpuSeconds':usage.ru_utime,'systemCpuSeconds':usage.ru_stime,'peakRssKiB':usage.ru_maxrss,'childUserCpuSeconds':resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,'childSystemCpuSeconds':resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,'maxChildPeakRssKiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'loadAverageEnd':os.getloadavg()};report['totalSeconds']=time.monotonic()-start;report['finishedAt']=time.time();atomic(out/'metadata.json',json.dumps(metadata).encode());atomic(out/'report.json',json.dumps(report,indent=2).encode());atomic(out/'reports'/f'{time.time_ns()}.json',json.dumps(report,indent=2).encode());print(json.dumps(report),flush=True)
if __name__=='__main__':main()
