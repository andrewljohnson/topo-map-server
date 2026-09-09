#!/usr/bin/env python3
"""Verify prepared agency geometries against every retained 400-parent trail child."""
import hashlib,json,multiprocessing,sys,time,resource
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
import national_trails as trails
DATA=ROOT/'services/tiles/data/experiments/sierra-100x-z12-v1/derived'
def render(key):
 x,y=key
 base=(DATA/'osm/14'/str(x)/f'{y}.pbf').read_bytes()
 actual=trails.render_tile(14,x,y,basemap_tile=base)
 expected=(DATA/'trails/14'/str(x)/f'{y}.pbf').read_bytes()
 assert actual==expected,(x,y,hashlib.sha256(actual).hexdigest(),hashlib.sha256(expected).hexdigest())
 return len(actual)
if __name__=='__main__':
 keys=[(x*4+dx,y*4+dy) for y in range(1552,1572) for x in range(672,692) for dy in range(4) for dx in range(4)]
 start=time.monotonic()
 with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
  total=sum(pool.map(render,keys))
 result={'seconds':time.monotonic()-start,'workers':4,'identicalTiles':len(keys),'bytes':total,'maxChildPeakRssKiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'reference':'Retained 400-parent trail children from unprepared agency geometry path'}
 print(json.dumps(result),flush=True)
 (ROOT/'experiments/tahoe/results/trail-preparation-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
