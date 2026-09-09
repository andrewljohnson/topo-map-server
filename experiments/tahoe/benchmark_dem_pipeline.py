#!/usr/bin/env python3
"""Measure the final I/O-prefetch plus process-render DEM phase on the 4,000-parent fixture."""
import json,time,multiprocessing,resource,hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from build import ROOT,REGIONS,dem_parent,prefetch_dem,morton_key

def main():
 out=ROOT/'services/tiles/data/experiments/western-1000x-z12-v1'
 keys=sorted({(x+dx,y+dy) for x,y in REGIONS['western-1000x'] for dx in (-1,0,1) for dy in (-1,0,1)},key=morton_key)
 reference={str(p.relative_to(out/'dem')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'dem').glob('12/*/*.png')}
 start=time.monotonic();prefetch=prefetch_dem(keys,16);generation=time.monotonic()
 with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
  size=sum(pool.map(dem_parent,[(x,y,False,str(out),3) for x,y in keys]))
 elapsed=time.monotonic()-start;generation=time.monotonic()-generation
 for key,digest in reference.items():assert hashlib.sha256((out/'dem'/key).read_bytes()).hexdigest()==digest,key
 result={'seconds':elapsed,'generationSeconds':generation,**prefetch,'renderWorkers':8,'executor':'processes','demParents':len(keys),'demBytes':size,'identicalTiles':len(reference),'childCpuSeconds':resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,'maxChildRssKiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'scope':'Retained native inputs; only DEM phase including process startup/shutdown, no vector work'}
 (ROOT/'experiments/tahoe/results/western-dem-prefetch-processes.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
