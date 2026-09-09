#!/usr/bin/env python3
"""Reproducible geometry audit of a generated shard, usable in any region.

Counts are tile fragments, not distinct physical roads. Nearness is a review
signal; campsites, parallel paths, bridges and real branches must be retained.
"""
import argparse,json,sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/tiles'))
import mapbox_vector_tile as mvt
from shapely.geometry import shape
from shapely.affinity import scale
from shapely.strtree import STRtree
parser=argparse.ArgumentParser(description='Flag nearby agency/OSM road fragments for review; never automatically delete a road.')
parser.add_argument('--derived',type=Path,required=True,help='Directory containing trails/14/x/y.pbf')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--parent-file',type=Path,help='Optional JSON list of z12 x/y parents')
args=parser.parse_args()
root=args.derived/'trails/14'
parents=set(map(tuple,json.loads(args.parent_file.read_text()))) if args.parent_file else None
rows=[];count=0;merged=0
for path in sorted(root.glob('*/*.pbf')):
 x,y=int(path.parent.name),int(path.stem)
 if parents is not None and (x//4,y//4) not in parents:continue
 layer=mvt.decode(path.read_bytes(),default_options={'y_coord_down':True})['network'];lat=math.atan(math.sinh(math.pi*(1-2*(y+.5)/16384)));factor=40075016.68557849*math.cos(lat)/16384/layer['extent']
 fs=[f for f in layer['features'] if f['properties'].get('class') not in ['path','footway','cycleway','bridleway','steps','pedestrian','sidewalk','crossing']]
 gs=[scale(shape(f['geometry']),xfact=factor,yfact=factor,origin=(0,0)) for f in fs];tree=STRtree(gs);count+=len(fs);merged+=sum(f['properties'].get('source_count',0)>1 for f in fs)
 for i,a in enumerate(fs):
  if a['properties'].get('agency')=='OpenStreetMap':continue
  ga=gs[i]
  if ga.length<30:continue
  for j in tree.query(ga.buffer(20)):
   j=int(j)
   if i==j:continue
   b=fs[j];gb=gs[j]
   if b['properties'].get('agency')!='OpenStreetMap' and j<i:continue
   if gb.length<30:continue
   overlap=ga.intersection(gb.buffer(15,cap_style=2)).length
   if overlap<30 or overlap/min(ga.length,gb.length)<.7:continue
   rows.append({'tile':[x,y],'a':a['properties'],'b':b['properties'],'overlapM':round(overlap,1),'aLengthM':round(ga.length,1),'bLengthM':round(gb.length,1),'hausdorffM':round(ga.hausdorff_distance(gb),1),'geometryA':a['geometry'],'geometryB':b['geometry']})
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'roadFragments':count,'mergedFragments':merged,'candidates':rows},indent=2))
print('roads',count,'merged',merged,'candidates',len(rows))
