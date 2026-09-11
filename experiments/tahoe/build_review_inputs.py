"""Build pre-conflation evidence plus neighboring context for the published review queue.
OSM is the pinned Protomaps z14 input, not original OSM ways. Agency records retain
full cached geometries. Never fetch agency cells silently or call missing data empty.
"""
import json,sys,math,hashlib,functools
from pathlib import Path
from shapely.geometry import shape,box,mapping
from shapely.ops import transform
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
from national_trails import osm_network,CACHE,properties,pct_features
from trail_matching import normalized_name
p=ROOT/'apps/web/public/review/candidates.json';report=json.loads(p.with_name('candidates-v1.json').read_text())
if report.get('evidenceVersion'):raise SystemExit('Input already rebuilt; restore the previous evidence first')
def world_to_geo(x,y,z=None):return x*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*y))))
def fc(features):return {'type':'FeatureCollection','features':features}
def feature(geom,props):return {'type':'Feature','geometry':mapping(geom),'properties':props}
@functools.lru_cache(None)
def inputs(x,y):
 # One z14 tile halo around the complete reviewed z12 tile.
 west=(x*4-1)/16384*360-180;east=(x*4+5)/16384*360-180
 north=world_to_geo(0,(y*4-1)/16384)[1];south=world_to_geo(0,(y*4+5)/16384)[1]
 scope=box(west,south,east,north);items=[];missing=[];files=[]
 for xx in range(x*4-1,x*4+5):
  for yy in range(y*4-1,y*4+5):
   for f in osm_network(14,xx,yy):
    geom=transform(world_to_geo,f['geometry']);items.append((geom,{**f['properties'],'evidenceOrigin':'Pinned Protomaps OSM input; tile-fragment endpoints are not surveyed endpoints'}))
 for source in ['usfs','nps','mvum_trails','mvum_roads']:
  seen=set()
  for xx in range((x*4-1)//8,(x*4+4)//8+1):
   for yy in range((y*4-1)//8,(y*4+4)//8+1):
    path=CACHE/'detail'/source/'11'/str(xx)/(str(yy)+'.json')
    if not path.exists():missing.append(str(path.relative_to(CACHE)));continue
    raw=path.read_bytes();files.append({'path':str(path.relative_to(CACHE)),'sha256':hashlib.sha256(raw).hexdigest()})
    data=json.loads(raw)
    for f in data:
     props=properties(source,f)
     if props is None or not f.get('geometry'):continue
     if props['id'] in seen:continue
     seen.add(props['id']);geom=shape(f['geometry'])
     if not geom.intersects(scope):continue
     props['class']='track' if source=='mvum_roads' else 'path'
     props['evidenceOrigin']='Full cached agency feature, before clipping and conflation'
     items.append((geom,props))
 return items,scope,missing,files
for c in report['candidates']:
 _,x,y=c['tile'];items,scope,missing,files=inputs(x,y);items=list(items)
 if 'PCTA' in c['agencies']:
  for geometry,props in pct_features():
   geo=transform(world_to_geo,geometry)
   if geo.intersects(scope):items.append((geo,{**props,'class':'path','evidenceOrigin':'Checked-in PCTA centerline before clipping/conflation'}))
 selected=[];context=[];wanted={i for group in c['sourceIds'] for i in group}
 for geom,props in items:
  family='trail' if props.get('class') in ('path','footway','cycleway','bridleway','steps','pedestrian','sidewalk','crossing') else 'road'
  match=props['agency'] in c['agencies'] and (props['id'] in wanted or (family==c['kind'] and normalized_name(props.get('name'))==normalized_name(c['name'])))
  if match:selected.append(feature(geom,props))
  else:
   clip=geom.intersection(scope)
   if not clip.is_empty and clip.geom_type in ('LineString','MultiLineString'):context.append(feature(clip,props))
 c['processedGeometry']=c['geometry'];c['geometry']=fc(selected);c['contextGeometry']=fc(context)
 c['inputScope']=list(scope.bounds);c['inputCoverage']={'missingAgencyCells':missing,'agencyCacheFiles':files,'osmSnapshot':'2026-08-11 Protomaps z14; 6×6 tile window before our conflation','agencyScope':'Complete features intersecting input window from existing source cache; not a fresh agency census'}
 c['inputSourceIds']=[[f['properties']['id'] for f in selected if f['properties']['agency']==a] for a in c['agencies']]
 c['evidenceVersion']='pre-conflation-v2'
 print(c['name'],len(selected),len(context),'missing',len(missing),flush=True)
report['evidenceVersion']='pre-conflation-v2'
d=p.parent/'evidence-v2';d.mkdir(exist_ok=True)
for c in report['candidates']:
 (d/(c['id']+'.json')).write_text(json.dumps(c,separators=(',',':')))
 for k in ['geometry','contextGeometry','processedGeometry']:c.pop(k)
p.write_text(json.dumps(report,separators=(',',':')))
