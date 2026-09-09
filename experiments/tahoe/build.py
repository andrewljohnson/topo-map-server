#!/usr/bin/env python3
"""Tahoe-only correctness baseline: finest vector children -> combined z12; raw DEM mosaic."""
import argparse,gzip,hashlib,importlib,json,os,sys,time,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
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
EXTENT=16384

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

def main():
 p=argparse.ArgumentParser();p.add_argument('--clean-derived',action='store_true');p.add_argument('--workers',type=int,default=2);p.add_argument('--legacy-recreation',action='store_true');p.add_argument('--legacy-dem',action='store_true',help='Encode/decode intermediate child PNGs for comparison');p.add_argument('--regenerate-vectors',action='store_true',help='Ignore derived vector files while preserving raw inputs and current served outputs');a=p.parse_args()
 if a.clean_derived and OUT.exists():shutil.rmtree(OUT)
 OUT.mkdir(parents=True,exist_ok=True);start=time.monotonic();report={'workers':max(1,min(4,a.workers)),'sources':{},'parents':[],'mode':'legacy-fine-children correctness baseline' if a.legacy_recreation else 'direct full-detail recreation + fine-child vector baseline','sourceCache':'retained local inputs; cache misses fetched','startedAt':time.time()}
 def acquire(task):
  source,z,x,y=task;path=OUT/'derived'/source/str(z)/str(x)/f'{y}.pbf';t=time.monotonic()
  hit=path.exists() and not a.regenerate_vectors
  if hit:blob=path.read_bytes()
  else:
   blob=importlib.import_module(SOURCES[source]).render_tile(z,x,y);atomic(path,blob)
  return (x%4,y%4,blob,time.monotonic()-t,hit)
 parent_children={xy:[] for xy in PARENTS}
 with ThreadPoolExecutor(max_workers=max(1,min(4,a.workers))) as pool:
  for source in SOURCES:
   if source=='recreation' and not a.legacy_recreation:
    t=time.monotonic();module=importlib.import_module(SOURCES[source]);cells={};prepare_seconds=0
    for x,y in PARENTS:
     key=(x//4,y//4)
     if key not in cells:
      prepared_start=time.monotonic();cells[key]=module.prepare_cell(14,*key);prepare_seconds+=time.monotonic()-prepared_start
     blob=module.render_tile(12,x,y,detail_zoom=14,extent=EXTENT,prepared=cells[key])
     parent_children[(x,y)].append((source,None,None,blob))
    report['sources'][source]={'seconds':time.monotonic()-t,'preparedCells':len(cells),'prepareSeconds':prepare_seconds,'parentTiles':len(PARENTS),'childTiles':0,'derivedCacheHits':0}
    atomic(OUT/'progress.json',json.dumps(report).encode());print(source,report['sources'][source],flush=True);continue
   t=time.monotonic();hits=0;prepare_seconds=0
   tasks=[(source,14,x*4+dx,y*4+dy) for x,y in PARENTS for dy in range(4) for dx in range(4)]
   if source=='trails' and (a.regenerate_vectors or any(not (OUT/'derived'/source/str(z)/str(x)/f'{y}.pbf').exists() for _,z,x,y in tasks)):
    # Populate the immutable PCT cache before parallel workers can duplicate
    # its expensive first construction. Include preparation in source timing.
    importlib.import_module(SOURCES[source]).pct_features();prepare_seconds=time.monotonic()-t
   for task,result in zip(tasks,pool.map(acquire,tasks)):
    dx,dy,blob,seconds,hit=result;hits+=int(hit);parent_children[(task[2]//4,task[3]//4)].append((source,dx,dy,blob))
   report['sources'][source]={'seconds':time.monotonic()-t,'childTiles':len(tasks),'derivedCacheHits':hits,'prepareSeconds':prepare_seconds}
   atomic(OUT/'progress.json',json.dumps(report).encode());print(source,report['sources'][source],flush=True)
  for (x,y),children in parent_children.items():
   t=time.monotonic();blob,counts=merge_tiles(children);compressed=gzip.compress(blob,mtime=0)
   atomic(OUT/'base/12'/str(x)/f'{y}.pbf',compressed)
   report['parents'].append({'key':f'12/{x}/{y}','bytes':len(blob),'gzipBytes':len(compressed),'packSeconds':time.monotonic()-t,'sourceFeatureCounts':counts,'sha256':hashlib.sha256(blob).hexdigest()})
  dem_start=time.monotonic()
  def dem_parent(xy):
   x,y=xy;canvas=np.empty((1024,1024),dtype='float32');module=importlib.import_module('national_dem')
   for dy in range(2):
    for dx in range(2):canvas[dy*512:(dy+1)*512,dx*512:(dx+1)*512]=decode_png(module.render_tile(13,x*2+dx,y*2+dy)) if a.legacy_dem else module.render_samples(13,x*2+dx,y*2+dy)
   blob=encode_png(canvas);atomic(OUT/'dem/12'/str(x)/f'{y}.png',blob);return len(blob)
  # Halo supplies neighboring elevation samples for contour stitching.
  dem_keys=[(x,y) for x in range(680,684) for y in range(1565,1569)]
  report['dem']={'tiles':len(dem_keys),'bytes':sum(pool.map(dem_parent,dem_keys)),'seconds':time.monotonic()-dem_start,'tileSize':1024,'intermediateChildPngs':64 if a.legacy_dem else 0}
 w,s,_,_=bounds(12,681,1567);_,_,e,n=bounds(12,682,1566)
 metadata={'name':'Tahoe zoom-12 experiment','publicAccess':True,'bounds':[w,s,e,n],'center':[-120.035,38.905],'initialZoom':12.5,'minZoom':12,'maxZoom':12,'datasetId':'tahoe-combined-v1','tileUrl':'/base/{z}/{x}/{y}.pbf','combined':True,'tilesets':{'dem':{'datasetId':'tahoe-dem-v1','tileUrl':'/dem/{z}/{x}/{y}.png','bounds':[w,s,e,n],'minZoom':12,'maxZoom':12,'tileSize':1024,'attribution':'Elevation: USGS 3DEP · Mapzen terrain'}}}
 report['totalSeconds']=time.monotonic()-start;report['finishedAt']=time.time();atomic(OUT/'metadata.json',json.dumps(metadata).encode());atomic(OUT/'report.json',json.dumps(report,indent=2).encode());atomic(OUT/'reports'/f'{time.time_ns()}.json',json.dumps(report,indent=2).encode());print(json.dumps(report),flush=True)
if __name__=='__main__':main()
