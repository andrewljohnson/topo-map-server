"""Audit junction continuity before MVT quantization across a bounded pilot.

Reports agency endpoints connected in source data but disconnected after
conflation, and newly cut ends that do not meet the retained network. Original
source dead ends remain informational. Excludes the tile halo and route-only
badge geometry. Findings are review candidates, never automatic repair orders.
"""
import sys,json,math,multiprocessing,argparse,importlib.util
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict,Counter
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'services/tiles'))
import national_trails as nt
from trail_matching import lines
base=None;matcher=None
def initialize(path,matching_source=None):
 global base,matcher
 base=Path(path);matcher=__import__('trail_matching').conflate
 if matching_source:
  spec=importlib.util.spec_from_file_location('connectivity_baseline',matching_source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);matcher=module.conflate
def run(key):
 x,y=key;findings=[];counts=Counter();original=matcher
 def audited(reference,additions):
  if not reference:return original(reference,additions)
  incoming=reference+additions
  before=[(f,line) for f in incoming for line in lines(f['geometry'])]
  result=original(reference,additions)
  after=[(f,line) for f in result for line in lines(f['geometry'])]
  beforetree=STRtree([g for f,g in before]);aftertree=STRtree([g for f,g in after])
  originals=defaultdict(list);original_lines=defaultdict(list);corridors={}
  for f,g in before:
   original_lines[(f['properties'].get('agency'),f['properties']['id'])].append(g)
   originals[(f['properties'].get('agency'),f['properties']['id'])].extend(Point(c) for c in [g.coords[0],g.coords[-1]])
  for index,(f,line) in enumerate(after):
   props=f['properties'];identity=(props.get('agency'),props['id'])
   if props.get('agency')=='OpenStreetMap':continue
   for xy in [line.coords[0],line.coords[-1]]:
    latitude=math.atan(math.sinh(math.pi*(1-2*(y+.5)/16384)));span=40075016.68557849*math.cos(latitude)/16384
    if not (0<xy[0]<span and 0<xy[1]<span):continue
    p=Point(xy);counts['agencyEnds']+=1
    if any(j!=index and p.distance(after[int(j)][1])<1 for j in aftertree.query(p.buffer(1))):continue
    oldend=any(p.distance(q)<.01 for q in originals[identity])
    if oldend:
     partners=[before[int(j)][0]['properties'] for j in beforetree.query(p.buffer(.05)) if (before[int(j)][0]['properties'].get('agency'),before[int(j)][0]['properties']['id'])!=identity and p.distance(before[int(j)][1])<.05]
     if not partners:counts['sourceDeadEnds']+=1;continue
     if identity not in corridors:corridors[identity]=unary_union(original_lines[identity]).buffer(1)
     focus=p.buffer(20)
     distinct=[partner for partner in partners if any(ff['properties']['id']==partner['id'] and ff['properties'].get('agency')==partner.get('agency') and g.intersection(focus).difference(corridors[identity]).length>=5 for ff,g in before)]
     if not distinct:counts['duplicateTermini']+=1;continue
     partners=distinct
     kind='lostSourceJunction'
    else:partners=[];kind='disconnectedNewCut'
    near=[(p.distance(g),ff['properties']) for j in aftertree.query(p.buffer(60)) if int(j)!=index for ff,g in [after[int(j)]]]
    distance,closest=min(near,key=lambda v:v[0]) if near else (None,{})
    counts[kind]+=1
    findings.append({'kind':kind,'tile':[14,x,y],'pointMetres':list(xy),'id':props['id'],'agency':props.get('agency'),'name':props.get('name'),'nearestMetres':distance,'nearestId':closest.get('id'),'nearestName':closest.get('name'),'formerPartners':[{'id':p['id'],'agency':p.get('agency'),'name':p.get('name')} for p in partners]})
  return result
 nt.conflate=audited
 try:nt.render_tile(14,x,y,basemap_tile=(base/str(x)/f'{y}.pbf').read_bytes())
 finally:nt.conflate=original
 return dict(counts),findings
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parents',required=True,type=Path);parser.add_argument('--basemap',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--workers',type=int,default=16);parser.add_argument('--matching-source',type=Path,help='Optional earlier trail_matching.py for comparable baseline auditing');args=parser.parse_args()
 if not 1<=args.workers<=32:parser.error('workers must be1–32')
 keys=[(x*4+dx,y*4+dy) for x,y in json.loads(args.parents.read_text()) for dy in range(4) for dx in range(4)]
 counts=Counter();findings=[]
 with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(args.basemap,args.matching_source)) as pool:
  for c,f in pool.map(run,keys,chunksize=16):counts.update(c);findings.extend(f)
 for f in findings:
  z,x,y=f['tile'];n=2**z;scale=40075016.68557849*math.cos(math.atan(math.sinh(math.pi*(1-2*(y+.5)/n))));a,b=f['pointMetres'];f['lonlat']=[(a/scale+x/n)*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*(b/scale+y/n)))))]
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps({'tiles':len(keys),'counts':dict(counts),'findings':findings},indent=2));print(dict(counts))
