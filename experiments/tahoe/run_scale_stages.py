#!/usr/bin/env python3
"""Run only the explicitly bounded representative/next-scale benchmarks locally."""
import argparse,json,subprocess,sys,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'services/tiles/data/experiments'
STAGES=('sf-10x','smokies-10x','desert-10x','western-1000x')
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)
def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,choices=range(1,9),default=8);p.add_argument('--regions',nargs='+',choices=STAGES,default=list(STAGES));a=p.parse_args()
    status={'startedAt':time.time(),'workers':a.workers,'stages':[],'state':'running'}
    state=OUT/'scale-stages-status.json'
    for region in a.regions:
        stage={'region':region,'startedAt':time.time(),'attempts':[]};status['stages'].append(stage);write(state,status)
        for attempt in range(1,4):
            if shutil.disk_usage(OUT).free<60*1024**3:
                status.update(state='blocked',error='60 GiB disk reserve reached');write(state,status);raise RuntimeError(status['error'])
            log=OUT/f'{region}-attempt-{attempt}.log'
            record={'attempt':attempt,'startedAt':time.time(),'log':str(log)};stage['attempts'].append(record);write(state,status)
            command=[sys.executable,str(ROOT/'experiments/tahoe/build.py'),'--region',region,'--workers',str(a.workers),'--task-chunksize','64','--spatial-order','morton']
            with log.open('w') as stream:
                result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            record.update(finishedAt=time.time(),returncode=result.returncode);write(state,status)
            if result.returncode==0: break
            if attempt==3:
                status.update(state='blocked',error=f'{region} failed after three resumable attempts; inspect {log}');write(state,status);raise RuntimeError(status['error'])
            time.sleep(10)
        report=json.loads((OUT/f'{region}-z12-v1/report.json').read_text())
        summary={k:v for k,v in report.items() if k!='parents'}
        summary['vectorBytes']=sum(row['gzipBytes'] for row in report['parents'])
        summary['attemptWallSeconds']=time.time()-stage['startedAt']
        summary['parentHashes']={row['key']:row['sha256'] for row in report['parents']}
        write(ROOT/f'experiments/tahoe/results/{region}-first-scale.json',summary)
        stage.update(finishedAt=time.time(),seconds=summary['attemptWallSeconds'],vectorParents=report['vectorParents'],demTiles=report['dem']['tiles'],vectorBytes=summary['vectorBytes'],demBytes=report['dem']['bytes']);write(state,status)
    status.update(state='complete',finishedAt=time.time());write(state,status)
    print(json.dumps(status),flush=True)
if __name__=='__main__':main()
