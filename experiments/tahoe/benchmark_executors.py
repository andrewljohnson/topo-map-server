#!/usr/bin/env python3
"""Bounded Tahoe-only thread/process comparison; never publishes generated tiles."""
import hashlib,json,multiprocessing,os,resource,sys,time
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/tiles'))
import national_trails
DATA=ROOT/'services/tiles/data/experiments/tahoe-z12-v1'

def initialize():
 national_trails.pct_features()

def render(key):
 x,y=key
 base=(DATA/'derived/osm/14'/str(x)/f'{y}.pbf').read_bytes()
 blob=national_trails.render_tile(14,x,y,basemap_tile=base)
 usage=resource.getrusage(resource.RUSAGE_SELF)
 return {'key':f'{x}/{y}.pbf','sha256':hashlib.sha256(blob).hexdigest(),'pid':os.getpid(),'peakRssKiB':usage.ru_maxrss}

def main():
 expected=json.loads((ROOT/'experiments/tahoe/results/trail-corridor-equivalence.json').read_text())['sha256']
 keys=[tuple(map(int,key.removesuffix('.pbf').split('/'))) for key in expected]
 runs=[]
 for round in range(2):
  for mode in (('threads','processes') if round==0 else ('processes','threads')):
   # Clear the one-time PCT cache for every trial, including the second thread run.
   national_trails.pct_features.cache_clear()
   start=time.perf_counter();load_start=os.getloadavg()
   if mode=='threads':
    initialize();pool=ThreadPoolExecutor(max_workers=2)
   else:pool=ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn'),initializer=initialize)
   with pool:rows=list(pool.map(render,keys))
   seconds=time.perf_counter()-start
   for row in rows:assert row['sha256']==expected[row['key']],row['key']
   peaks={}
   for row in rows:peaks[str(row['pid'])]=max(peaks.get(str(row['pid']),0),row['peakRssKiB'])
   report={'round':round+1,'executor':mode,'seconds':seconds,'identicalTiles':len(rows),'workerPeakRssKiB':peaks,'loadAverageStart':load_start,'loadAverageEnd':os.getloadavg()}
   runs.append(report);print(json.dumps(report),flush=True)
 report={'workers':2,'includes':'PCT preparation, process spawn/shutdown, normalized input reads and all trail generation','coverage':'64 Tahoe z14 reference children only','runs':runs}
 (ROOT/'experiments/tahoe/results/executor-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
