from pathlib import Path
import json,hashlib,sys
from collections import defaultdict,Counter
from shapely import make_valid
from shapely.geometry import shape,mapping,LineString
from shapely.ops import unary_union,transform,split
from shapely.affinity import translate
BASE=Path(__file__).parent
sys.path.insert(0,str(BASE.parent))
from area_labels import label_center
SOURCES={'park':('UNIT_CODE','UNIT_NAME','UNIT_TYPE'),'forest':('adminforestid','forestname',None),'wilderness':('WID','NAME',None)}
def polygons(g):
 if g.geom_type=='Polygon':return [g]
 if hasattr(g,'geoms'):return [p for c in g.geoms for p in polygons(c)]
 return []
def wrap(poly):
 if poly.bounds[2]-poly.bounds[0]<=180:return [poly]
 def shift(x,y,z=None):
  try:return [v+360 if v<0 else v for v in x],y
  except TypeError:return (x+360 if x<0 else x),y
 shifted=transform(shift,poly)
 return [translate(p,xoff=-360) if p.representative_point().x>180 else p for p in split(shifted,LineString([(180,-90),(180,90)])).geoms]
features=[];counts={}
for kind,(idfield,namefield,typefield) in SOURCES.items():
 groups=defaultdict(list);props={};rawcount=0
 for path in sorted((BASE/'raw').glob(kind+'-*.geojson')):
  for f in json.loads(path.read_text())['features']:
   if not f.get('geometry'):continue
   a=f['properties'];name=str(a.get(namefield) or '').strip()
   if not name:continue
   ident=str(a.get(idfield) or name);key=kind+'-'+ident
   groups[key].extend([w for p in polygons(make_valid(shape(f['geometry']))) for w in wrap(p)])
   props[key]={'id':key,'name':name,'kind':kind,'designation':a.get(typefield) if typefield else 'National Forest' if kind=='forest' else 'Wilderness'}
   rawcount+=1
 for key,parts in groups.items():
  geometry=unary_union(parts).simplify(.005,preserve_topology=True)
  geometry=unary_union(polygons(make_valid(geometry)))
  if geometry.is_empty:continue
  components=polygons(geometry)
  main=max(components,key=lambda g:g.area)
  nav=main if geometry.bounds[2]-geometry.bounds[0]>180 else geometry
  p=main.representative_point();a=props[key];a['bounds']=[round(v,5) for v in nav.bounds];a['center']=[round(p.x,5),round(p.y,5)]
  # Compact coordinate precision without modifying the downloaded source records.
  def rounded(o):
   if isinstance(o,(list,tuple)):return [rounded(v) for v in o]
   return round(o,5) if isinstance(o,float) else o
  geom=mapping(geometry);geom['coordinates']=rounded(geom['coordinates'])
  checked=shape(geom)
  if not checked.is_valid:geom=mapping(unary_union(polygons(make_valid(checked))))
  a['label_center'],a['label_method']=label_center(geom)
  features.append({'type':'Feature','id':key,'properties':a,'geometry':geom})
 counts[kind]={'sourceRecords':rawcount,'areas':len(groups)}
features.sort(key=lambda f:f['properties']['name'])
output=BASE/'protected-areas.geojson';output.write_text(json.dumps({'type':'FeatureCollection','features':features},separators=(',',':')))
manifest={'retrieved':'2026-09-05','sources':{'park':'https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2','forest':'https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0','wilderness':'https://services1.arcgis.com/ERdCHt0sNM6dENSD/arcgis/rest/services/Wilderness_Areas_in_the_United_States/FeatureServer/0'},'counts':counts,'processing':'WGS84 polygons dissolved by agency unit identifier; topology-preserving overview simplification 0.005 degrees; coordinate precision 5 decimal places. Antimeridian overview retains split polygons, navigation uses dominant component. Overview boundaries do not imply public access. Label anchors use the Mercator centroid of the dominant component, with an interior pole fallback; navigation centers remain separate.','sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
(BASE/'protected-areas-sources.json').write_text(json.dumps(manifest,indent=2))
print(counts,output.stat().st_size,flush=True)
for term in ['Yosemite','Eldorado','Desolation','Haleakal','Denali']:
 print(term,[f['properties'] for f in features if term.lower() in f['properties']['name'].lower()][:3])
