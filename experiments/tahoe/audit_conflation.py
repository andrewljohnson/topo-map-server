"""Compare retained OSM geometry and designation areas across a pilot rebuild.

Use --before/--after for derived/trails/14 directories and --parents for a
JSON array of z12 [x,y] pairs. Export the earlier national_boundaries.py with
git show and pass its path as --before-boundaries. Inputs are local source caches.
"""
import argparse,math
import os,sys,json,importlib.util
from pathlib import Path
from collections import defaultdict
from shapely.geometry import shape
from shapely.ops import unary_union
parser=argparse.ArgumentParser(description=__doc__)
for name in ('before','after','parents','before-boundaries'):parser.add_argument('--'+name,required=True,type=Path)
parser.add_argument('--allow-split-rounding',action='store_true',help='Permit only the half-pixel diagonal introduced when metadata partitions add MVT vertices; verify full line coverage in both directions.')
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
count=0;fail=[];rounded=0;maximum_deviation=0.0
tolerance=math.sqrt(.5)+1e-8
for x,y in parents:
 for dx in range(4):
  for dy in range(4):
   path=Path(str(x*4+dx))/f'{y*4+dy}.pbf';a=groups((oldroot/path).read_bytes());b=groups((newroot/path).read_bytes());count+=len(a)
   for k,g in a.items():
    if k not in b:fail.append([str(path),k,'missing']);continue
    if g.equals(b[k]):continue
    deviation=g.hausdorff_distance(b[k]);maximum_deviation=max(maximum_deviation,deviation)
    # A discrete vertex Hausdorff check alone can miss a gap in a long segment.
    # Require the entire original/candidate line to be covered in both directions.
    if args.allow_split_rounding and g.difference(b[k].buffer(tolerance)).is_empty and b[k].difference(g.buffer(tolerance)).is_empty:rounded+=1
    else:fail.append([str(path),k,deviation])
assert not fail,fail[:20]
cells=set((x//16,y//16) for x,y in parents);areas=0;preserved=0
for cx,cy in sorted(cells):
 a=old.prepared_cell(cx,cy);b=new.prepared_cell(cx,cy)
 assert len(a)==len(b)
 for (af,ak,al,ag),(bf,bk,bl,bg) in zip(a,b):
  assert af==bf and ak==bk and ag.equals(bg)
  areas+=1
  if ak!='forest':assert al.equals(bl);preserved+=1
print(json.dumps({'fineTiles':len(parents)*16,'osmFeatureOccurrencesUnchanged':count-rounded,'osmFeatureOccurrencesWithinSplitRounding':rounded,'maximumDeviationTileUnits':maximum_deviation,'splitRoundingToleranceTileUnits':tolerance if args.allow_split_rounding else 0,'sourceCells':len(cells),'designationPolygonsUnchanged':areas,'nonForestOutlinesUnchanged':preserved},indent=2))
