#!/usr/bin/env python3
"""Compare current parents with retained fine-child inputs, without fetching data."""
import gzip,json
from collections import Counter
from build import OUT,PARENTS,SOURCES,merge_tiles,mvt

def canonical(layer):
 return Counter(json.dumps(f,sort_keys=True,separators=(',',':')) for f in layer.get('features',[]))

def main():
 results=[]
 for x,y in PARENTS:
  children=[]
  for source in SOURCES:
   for dy in range(4):
    for dx in range(4):
     path=OUT/'derived'/source/'14'/str(x*4+dx)/f'{y*4+dy}.pbf'
     if not path.exists():raise RuntimeError(f'Missing reference {path}. Run a legacy reference build first; this check never fetches inputs.')
     children.append((source,dx,dy,path.read_bytes()))
  old,_=merge_tiles(children);old=mvt.decode(old)
  current=mvt.decode(gzip.decompress((OUT/'base/12'/str(x)/f'{y}.pbf').read_bytes()))
  if set(old)!=set(current):raise AssertionError(f'Layer set changed at {x}/{y}')
  for name in old:
   if old[name]['extent']!=current[name]['extent'] or canonical(old[name])!=canonical(current[name]):
    raise AssertionError(f'Geometry, identity, or properties changed in {x}/{y}/{name}')
  results.append({'tile':f'12/{x}/{y}','identicalFeatures':{name:len(layer['features']) for name,layer in current.items()}})
 print(json.dumps(results,indent=2))
if __name__=='__main__':main()
