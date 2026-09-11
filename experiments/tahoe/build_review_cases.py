import argparse,json,sys,gzip,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/tiles'))
p=argparse.ArgumentParser(description='Freeze audit source geometry for the human review UI.')
p.add_argument('--report',type=Path,required=True);p.add_argument('--tiles',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
import mapbox_vector_tile
from trail_matching import normalized_name
r=json.loads(args.report.read_text())
for c in r['candidates']:
 z,x,y=c['tile'];b=(args.tiles/f'{x}-{y}.pbf').read_bytes();layer=mapbox_vector_tile.decode(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b,default_options={'y_coord_down':True})['trails__network'];extent=layer['extent']
 def coords(v):
  if isinstance(v[0],(int,float)):
   return [(x+v[0]/extent)/2**z*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+v[1]/extent)/2**z))))]
  return [coords(p) for p in v]
 features=[]
 for f in layer['features']:
  p=f['properties'];kind='trail' if p.get('class') in ('path','footway','cycleway','bridleway','steps','pedestrian','sidewalk','crossing') else 'road'
  if normalized_name(p.get('name'))!=normalized_name(c['name']) or kind!=c['kind'] or p.get('agency') not in c['agencies']:continue
  features.append({'type':'Feature','properties':p,'geometry':{'type':f['geometry']['type'],'coordinates':coords(f['geometry']['coordinates'])}})
 c['id']=hashlib.sha256(json.dumps([r['release'],c['tile'],c['name'],sorted(c['agencies'])]).encode()).hexdigest()[:20]
 c['geometry']={'type':'FeatureCollection','features':features}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(r,separators=(',',':')))
print(len(r['candidates']), 'review cases')
