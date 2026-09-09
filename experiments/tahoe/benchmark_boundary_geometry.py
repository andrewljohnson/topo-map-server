#!/usr/bin/env python3
"""Verify parsed-boundary reuse against the complete 400-parent child reference."""
import hashlib,json,multiprocessing,sys,time,resource
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
import national_boundaries as boundaries

def render(key):
 x,y=key;blob=boundaries.render_tile(14,x,y)
 return f'{x}/{y}.pbf',hashlib.sha256(blob).hexdigest()
if __name__=='__main__':
 folder=ROOT/'services/tiles/data/experiments/sierra-100x-z12-v1/derived/boundaries/14'
 reference={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*/*.pbf')}
 assert len(reference)==6400, 'Generate the 400-parent boundary reference first'
 start=time.monotonic()
 keys=[tuple(map(int,key.removesuffix('.pbf').split('/'))) for key in sorted(reference)]
 with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
  for key,digest in pool.map(render,keys):assert digest==reference[key],key
 result={'seconds':time.monotonic()-start,'workers':4,'identicalTiles':len(keys),'reference':'400-parent first run boundary children; retained inputs','maxChildPeakRssKiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
 print(json.dumps(result),flush=True)
 (ROOT/'experiments/tahoe/results/boundary-geometry-reuse-400-parent.json').write_text(json.dumps(result,indent=2)+'\n')
