#!/usr/bin/env python3
"""Measure genuinely empty native DEM caches without deleting reusable inputs."""
import argparse,json,math,multiprocessing,os,shutil,sys,time,resource,re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2]
POINTS={'tahoe':(-120.03,38.90),'kansas':(-97.33,37.69),'cascades':(-121.75,46.85)}
EPOCH='usgs-national-dem-feet20-v2-20260905'

def initialize(cache):
 os.environ['NATIONAL_CONTOURS_DATA']=cache
 sys.path.insert(0,str(ROOT/'experiments/tahoe'))

def render(task):
 from build import dem_parent
 size=dem_parent(task)
 usage=resource.getrusage(resource.RUSAGE_SELF)
 return {'bytes':size,'pid':os.getpid(),'cpu':usage.ru_utime+usage.ru_stime,'rssKiB':usage.ru_maxrss}

def main():
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,choices=range(1,33),default=8);p.add_argument('--executor',choices=('processes','threads','prefetch'),default='processes');p.add_argument('--tag',default='v1');p.add_argument('--regions',nargs='+',choices=tuple(POINTS),default=list(POINTS));a=p.parse_args()
 if not re.fullmatch('[a-z0-9-]+',a.tag):raise ValueError('Invalid probe tag')
 if a.executor!='processes' and len(a.regions)!=1:raise ValueError('Thread comparisons require one region per fresh interpreter')
 results=[]
 for name in a.regions:
  lon,lat=POINTS[name];cx=int((lon+180)/360*4096);cy=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*4096)
  parents=[(x,y) for y in range(cy-4,cy+6) for x in range(cx-4,cx+6)]
  keys=sorted({(x+dx,y+dy) for x,y in parents for dx in (-1,0,1) for dy in (-1,0,1)})
  out=ROOT/f'services/tiles/data/experiments/cold-dem-{name}-{a.tag}';cache=out/'raw';namespace=cache/EPOCH
  if (namespace/'windows').exists():raise RuntimeError(f'{name} already has a native cache; do not label a rerun cold')
  if shutil.disk_usage(out.parent).free<60*1024**3:raise RuntimeError('60 GiB disk reserve reached')
  catalog=ROOT/'services/tiles/data/national_dem'/EPOCH/'catalog';seed=namespace/'catalog';seed.mkdir(parents=True,exist_ok=True);seeded=0
  # Preserve already-pinned editions; catalog reuse is recorded separately from
  # the deliberately empty native raster cache. New cells still query TNM.
  for path in catalog.glob('*.json'):
   shutil.copy2(path,seed/path.name);seeded+=1
  started=time.time();begin=time.monotonic()
  prefetch={}
  if a.executor=='prefetch':
   initialize(str(cache))
   from build import prefetch_dem
   prefetch=prefetch_dem(keys,16)
  executor=ProcessPoolExecutor if a.executor in ('processes','prefetch') else ThreadPoolExecutor
  options={'mp_context':multiprocessing.get_context('spawn')} if a.executor in ('processes','prefetch') else {}
  with executor(max_workers=a.workers,initializer=initialize,initargs=(str(cache),),**options) as pool:
   rows=list(pool.map(render,[(x,y,False,str(out),3) for x,y in keys]))
  workers={}
  for row in rows:
   old=workers.get(row['pid'],{'cpu':0,'rssKiB':0});workers[row['pid']]={'cpu':max(old['cpu'],row['cpu']),'rssKiB':max(old['rssKiB'],row['rssKiB'])}
  chunks=list((namespace/'windows').glob('*.npz'))
  if not chunks:raise RuntimeError('Probe did not populate its isolated native cache')
  result={**prefetch,'executor':a.executor,'tag':a.tag,'region':name,'startedAt':started,'seconds':time.monotonic()-begin,'vectorAreaParents':100,'demParents':len(keys),'workers':a.workers,'nativeCacheBefore':0,'nativeChunksFetched':len(chunks),'nativeCacheBytes':sum(p.stat().st_size for p in chunks),'seededCatalogFiles':seeded,'demBytes':sum(r['bytes'] for r in rows),'workerCpuSeconds':sum(r['cpu'] for r in workers.values()),'maxWorkerRssKiB':max(r['rssKiB'] for r in workers.values()),'scope':'Cold native raster acquisition + reprojection + level-3 PNG; source catalogs retained where already pinned; shared global fallback cache retained'}
  results.append(result);print(json.dumps(result),flush=True)
  (ROOT/('experiments/tahoe/results/cold-dem-probes'+('' if a.tag=='v1' else '-'+a.tag)+'.json')).write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
