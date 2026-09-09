#!/usr/bin/env python3
"""Compare bounded worker counts without modifying served tiles or publishing."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from build import ROOT,REGIONS

def main():
 p=argparse.ArgumentParser();p.add_argument('--fixture',choices=('pilot','sierra'),default='pilot');p.add_argument('--workers',type=int,nargs='+',default=[8,16]);p.add_argument('--repeats',type=int,choices=range(1,4),default=1);a=p.parse_args()
 if any(not 1<=w<=32 for w in a.workers):p.error('workers must be 1–32')
 parents=REGIONS['tahoe-10x']+REGIONS['sf-10x'] if a.fixture=='pilot' else REGIONS['sierra-100x']
 output=ROOT/'services/tiles/data/publication/combined'/('worker-proof-'+a.fixture)
 output.mkdir(parents=True,exist_ok=True);keys=output/'parents.json';keys.write_text(json.dumps(parents))
 runs=[];expected=None
 for repeat in range(a.repeats):
  for workers in (a.workers if repeat%2==0 else list(reversed(a.workers))):
   out=output/f'workers-{workers}';env={**os.environ,'TOPO_SCRATCH_ROOT':str(out/'raw')}
   cmd=[sys.executable,str(ROOT/'experiments/tahoe/build.py'),'--parent-file',str(keys),'--output',str(out),'--workers',str(workers),'--dem-workers',str(min(workers,16)),'--spatial-order','morton','--task-chunksize','64','--regenerate-vectors']
   with (output/f'run-{repeat}-{workers}.log').open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
   report=json.loads((out/'report.json').read_text())
   assert all(v['derivedCacheHits']==0 for v in report['sources'].values())
   hashes={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for kind in ('base','dem') for f in (out/kind).rglob('*') if f.is_file()}
   if expected is None:expected=hashes
   else:assert hashes==expected,'Worker count changed generated tile bytes'
   report['identicalOutputFiles']=len(hashes);report['repeat']=repeat;runs.append(report)
   (output/'comparison.json').write_text(json.dumps(runs,indent=2))
   print(json.dumps({'workers':workers,'repeat':repeat,'seconds':report['totalSeconds'],'files':len(hashes),'sources':{k:round(v['seconds'],2) for k,v in report['sources'].items()}}),flush=True)
if __name__=='__main__':main()
