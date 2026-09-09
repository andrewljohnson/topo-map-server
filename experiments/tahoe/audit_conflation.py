"""Compare retained OSM geometry and designation areas across a pilot rebuild.

Use --before/--after for derived/trails/14 directories and --parents for a
JSON array of z12 [x,y] pairs. Export the earlier national_boundaries.py with
git show and pass its path as --before-boundaries. Inputs are local source caches.
"""
import argparse
import os,sys,json,importlib.util
from pathlib import Path
from collections import defaultdict
from shapely.geometry import shape
from shapely.ops import unary_union
parser=argparse.ArgumentParser(description=__doc__)
for name in ('before','after','parents','before-boundaries'):parser.add_argument('--'+name,required=True,type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'services/tiles'))
os.environ['TILE_DATA_DIR']=str(root/'services/tiles/data')
import mapbox_vector_tile as m
import national_boundaries as new
spec=importlib.util.spec_from_file_location('old_boundary',str(args.before_boundaries));old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
parents=json.loads(args.parents.read_text())
oldroot=args.before
newroot=args.after
def groups(blob):
 out=defaultdict(list)
 for f in m.decode(blob,default_options={'y_coord_down':True})['network']['features']:
  p=f['properties']
  if p.get('agency')=='OpenStreetMap':out[p['id']].append(shape(f['geometry']))
 return {k:unary_union(v) for k,v in out.items()}
count=0;fail=[]
for x,y in parents:
 for dx in range(4):
  for dy in range(4):
   path=Path(str(x*4+dx))/f'{y*4+dy}.pbf';a=groups((oldroot/path).read_bytes());b=groups((newroot/path).read_bytes());count+=len(a)
   for k,g in a.items():
    if k not in b or not g.equals(b[k]):fail.append([str(path),k])
assert not fail,fail[:20]
cells=set((x//16,y//16) for x,y in parents);areas=0;preserved=0
for cx,cy in sorted(cells):
 a=old.prepared_cell(cx,cy);b=new.prepared_cell(cx,cy)
 assert len(a)==len(b)
 for (af,ak,al,ag),(bf,bk,bl,bg) in zip(a,b):
  assert af==bf and ak==bk and ag.equals(bg)
  areas+=1
  if ak!='forest':assert al.equals(bl);preserved+=1
print(json.dumps({'fineTiles':len(parents)*16,'osmFeatureOccurrencesUnchanged':count,'sourceCells':len(cells),'designationPolygonsUnchanged':areas,'nonForestOutlinesUnchanged':preserved},indent=2))
