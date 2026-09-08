#!/usr/bin/env python3
"""Compare real tile downloads against an isolated local service; never clears live caches."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import http.client
import json
import multiprocessing
from pathlib import Path
import statistics
import tempfile
import threading
import time
from urllib.parse import urlencode
import tile_service as tiles

class QuietHandler(tiles.Handler):
    def log_message(self,*_):
        pass

def cell_keys():
    x,y=(int(v*4096) for v in tiles.project(*tiles.META['center']))
    keys=[(z,x//2**(12-z),y//2**(12-z)) for z in range(6,12)]
    for z in range(12,15):
        factor=2**(z-12)
        keys += [(z,x*factor+dx,y*factor+dy) for dx in range(factor) for dy in range(factor)]
    return [key for key in keys if tiles.valid_tile(*key)]

def render_one(coords):
    start=time.perf_counter()
    blob=tiles.render_tile(*coords)
    return len(blob),time.perf_counter()-start

def run(args):
    keys=cell_keys()
    report={'cell':'Baltimore z12','tileCount':len(keys),'notes':'Wire bytes count response bodies only. Loopback has no Wi-Fi latency; CPU, network RTT, and throughput differ on a phone.'}
    if args.compare_processes:
        start=time.perf_counter()
        serial=[render_one(k) for k in keys]
        serial_elapsed=time.perf_counter()-start
        start=time.perf_counter()
        with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
            parallel=list(pool.map(render_one,keys))
        parallel_elapsed=time.perf_counter()-start
        report['directCpuComparison']={'serialSeconds':round(serial_elapsed,3),'twoProcessesSeconds':round(parallel_elapsed,3),'speedup':round(serial_elapsed/parallel_elapsed,2),'sameTotalBytes':sum(x[0] for x in serial)==sum(x[0] for x in parallel)}
        print(json.dumps(report,indent=2),flush=True)
        return
    with tempfile.TemporaryDirectory(prefix='tile-benchmark-') as tmp:
        # DB is held separately; only cache output is redirected away from live data.
        tiles.DATA=Path(tmp)
        server=tiles.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        dataset=tiles.metadata()['datasetId']
        def transfer(batch=False,encoding='identity'):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=120)
            start=time.perf_counter(); size=0; times=[]; requests=0
            groups=[keys[i:i+8] for i in range(0,len(keys),8)] if batch else [[k] for k in keys]
            try:
                for group in groups:
                    path='/tile-batch?'+urlencode({'datasetId':dataset,'tiles':','.join('/'.join(map(str,k)) for k in group)}) if batch else '/tiles/'+('/'.join(map(str,group[0])))+'.pbf'
                    before=time.perf_counter()
                    conn.request('GET',path,headers={'Accept-Encoding':encoding})
                    response=conn.getresponse(); body=response.read(); size+=len(body);requests+=1
                    if response.status!=200: raise RuntimeError((response.status,body[:200]))
                    if batch:
                        result=json.loads(gzip.decompress(body) if response.getheader('Content-Encoding')=='gzip' else body)
                        if result['errors']: raise RuntimeError(result['errors'])
                    times.append({'key':'/'.join(map(str,group[0])),'seconds':round(time.perf_counter()-before,3)})
            finally:
                conn.close()
            return {'seconds':round(time.perf_counter()-start,3),'wireBytes':size,'requests':requests,'slowest':sorted(times,key=lambda x:-x['seconds'])[:5]}
        try:
            report['coldSerial']=transfer()
            for label,batch,encoding in [('cachedSerial',False,'identity'),('cachedSerialGzip',False,'gzip'),('cachedBatchGzip',True,'gzip')]:
                runs=[transfer(batch,encoding) for _ in range(args.rounds)]
                report[label]={'medianSeconds':statistics.median(r['seconds'] for r in runs),'wireBytes':runs[0]['wireBytes'],'requests':runs[0]['requests']}
            report['batchReductionPercent']=round(100*(1-report['cachedBatchGzip']['wireBytes']/report['cachedSerial']['wireBytes']),1)
        finally:
            server.shutdown();server.server_close();thread.join()
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rounds',type=int,default=3)
    p.add_argument('--compare-processes',action='store_true',help='Benchmark direct cold encoding serial vs two worker processes')
    run(p.parse_args())
