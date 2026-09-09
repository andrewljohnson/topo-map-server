#!/usr/bin/env python3
"""Add native z10–11 base overviews to an already completed local sample."""
import argparse,gzip,importlib,json,time
from build import ROOT,REGIONS,atomic
from benchmark_overviews import SOURCES,combine_native

def main():
 p=argparse.ArgumentParser();p.add_argument('region',choices=('tahoe-10x','sf-10x'));a=p.parse_args()
 out=ROOT/'services/tiles/data/experiments'/(a.region+'-z12-v1');meta=json.loads((out/'metadata.json').read_text());start=time.monotonic();rows=[]
 for z in (10,11):
  keys=sorted({(x//2**(12-z),y//2**(12-z)) for x,y in REGIONS[a.region]})
  for x,y in keys:
   children=[(source,importlib.import_module(module).render_tile(z,x,y)) for source,(module,minzoom) in SOURCES.items() if z>=minzoom]
   blob=gzip.compress(combine_native(children),mtime=0);atomic(out/'base'/str(z)/str(x)/f'{y}.pbf',blob);rows.append({'key':f'{z}/{x}/{y}','bytes':len(blob)})
 meta['minZoom']=10
 if a.region=='tahoe-10x':meta.update(initialZoom=10,center=[-120.04,39.08])
 atomic(out/'metadata.json',json.dumps(meta).encode())
 report={'region':a.region,'seconds':time.monotonic()-start,'tiles':rows,'dem':'Detailed z12 samples retained; base overviews add no DEM requests below z12'}
 atomic(out/'overview-report.json',json.dumps(report).encode());print(json.dumps(report))
if __name__=='__main__':main()
