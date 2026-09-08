"""Detailed agency outlines. Extract true boundaries before tile clipping."""
import fcntl, hashlib, json, math, os, tempfile, time
from pathlib import Path
from functools import lru_cache
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import mapbox_vector_tile
from shapely import make_valid
from shapely.geometry import shape, box, mapping
from shapely.ops import transform, unary_union
DATASET_ID='us-agency-boundaries-v2'
CACHE=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).parent/'data'))/'national-boundaries'/'us-agency-boundaries-v1'
SOURCES={
'park':('https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2','UNIT_CODE','UNIT_NAME'),
'forest':('https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0','adminforestid','forestname'),
'wilderness':('https://services1.arcgis.com/ERdCHt0sNM6dENSD/arcgis/rest/services/Wilderness_Areas_in_the_United_States/FeatureServer/0','WID','NAME')}
CELL_ZOOM=8

def bounds(z,x,y):
 n=2**z;lat=lambda v:math.degrees(math.atan(math.sinh(math.pi*(1-2*v/n))))
 return x/n*360-180,lat(y+1),(x+1)/n*360-180,lat(y)

def query(kind,params):
 for attempt in range(3):
  try:
   req=Request(SOURCES[kind][0]+'/query?'+urlencode(params),headers={'User-Agent':'topo-map-server/1.0 (protected-area boundaries)'})
   with urlopen(req,timeout=60) as response:data=json.load(response)
   if 'error' in data or data.get('exceededTransferLimit'):raise RuntimeError('Incomplete agency boundary response: '+str(data.get('error','transfer limit')))
   return data
  except Exception:
   if attempt==2:raise
   time.sleep(2**attempt)

def cached(path,build):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.with_suffix('.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if path.exists():return json.loads(path.read_text())
  data=build()
  with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as out:
   json.dump(data,out,separators=(',',':'));name=out.name
  Path(name).replace(path);return data

def cell_ids(kind,x,y):
 def build():
  w,s,e,n=bounds(CELL_ZOOM,x,y);halo=.05
  data=query(kind,{'f':'json','where':'1=1','returnIdsOnly':'true','geometryType':'esriGeometryEnvelope','geometry':','.join(map(str,[max(-180,w-halo),s-halo,min(180,e+halo),n+halo])),'inSR':4326,'spatialRel':'esriSpatialRelIntersects'})
  if 'objectIds' in data and data['objectIds'] is None:data['objectIds']=[]
  if not isinstance(data.get('objectIds'),list):raise RuntimeError('Agency response missing object IDs')
  if len(data['objectIds'])>300:raise RuntimeError('Boundary query exceeds bounded cell limit')
  return data['objectIds']
 return cached(CACHE/'cells'/kind/str(x)/(str(y)+'.json'),build)

def object_data(kind,ident):
 def build():
  data=query(kind,{'f':'geojson','objectIds':ident,'outFields':'*','returnGeometry':'true','outSR':4326,'maxAllowableOffset':.000025,'geometryPrecision':7})
  if len(data.get('features',[]))!=1 or not data['features'][0].get('geometry'):raise RuntimeError('Agency object missing geometry')
  return data['features'][0]
 return cached(CACHE/'objects'/kind/(str(ident)+'.json'),build)

def project(lon,lat,z=None):
 return (lon+180)/360,(1-math.asinh(math.tan(math.radians(max(-85.05112878,min(85.05112878,lat)))))/math.pi)/2

def line_parts(geometry):
 if geometry.geom_type=='LineString':return [geometry]
 return [part for child in getattr(geometry,'geoms',[]) for part in line_parts(child)]

def dedupe_outline(line,previous,park_lines,units_per_metre,kind):
 """Cartographic stroke suppression only: retain original designation polygons.

 Agency datasets disagree slightly on shared edges. Five metres removes survey/
 digitization duplicates. Coarse forest administrative edges get a wider corridor
 only beside parks, and only for continuous runs of at least one kilometre. This
 leaves short crossings and forest branches intact. Work before tile clipping so
 a run is never classified differently on either side of a tile edge.
 """
 if kind=='forest' and not park_lines.is_empty:
  nearby=line.intersection(park_lines.simplify(units_per_metre).buffer(250*units_per_metre,quad_segs=2))
  runs=[p for p in line_parts(nearby) if p.length>=1000*units_per_metre]
  if runs:line=line.difference(unary_union(runs))
 for prior in (previous if isinstance(previous,list) else [previous]):
  if not prior.is_empty:line=line.difference(prior.simplify(.5*units_per_metre).buffer(5*units_per_metre,quad_segs=2))
 return line

def outline_features(feature,kind,z,x,y,outline=None):
 n=2**z;pad=8/512/n
 geometry=make_valid(shape(feature['geometry']))
 # Boundary first prevents fabricated lines on tile edges.
 clip=box(x/n-pad,y/n-pad,(x+1)/n+pad,(y+1)/n+pad)
 clipped=(transform(project,geometry.boundary) if outline is None else outline).intersection(clip).simplify(.35/512/n,preserve_topology=True)
 geographic_clip=transform(lambda u,v:(u*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*v))))),clip)
 fill=transform(project,geometry.intersection(geographic_clip)).simplify(.35/512/n,preserve_topology=True)
 _,idfield,namefield=SOURCES[kind];props=feature['properties'];ident=kind+'-'+str(props.get(idfield) or props.get(namefield))
 pieces=list(clipped.geoms) if clipped.geom_type=='GeometryCollection' else [clipped]
 pieces.extend(list(fill.geoms) if fill.geom_type=='GeometryCollection' else [fill])
 return [{'geometry':p,'id':int.from_bytes(hashlib.sha256(ident.encode()).digest()[:6],'big'),'properties':{'id':ident,'kind':kind,'name':str(props.get(namefield) or '')}} for p in pieces if not p.is_empty and p.geom_type in ('LineString','MultiLineString','Polygon','MultiPolygon')]

@lru_cache(maxsize=8)
def prepared_cell(cx,cy):
 prepared=[];previous=[];parks=[]
 # Bound expensive buffer operations to the source cell plus a generous halo.
 # The halo exceeds the longest matching threshold, well outside visible tiles.
 cn=2**CELL_ZOOM;halo=.0005
 work_clip=box(cx/cn-halo,cy/cn-halo,(cx+1)/cn+halo,(cy+1)/cn+halo)
 # Detailed NPS edges first, then wilderness, then coarse forest outlines.
 for kind in ('park','wilderness','forest'):
  groups={}
  for ident in sorted(cell_ids(kind,cx,cy)):
   feature=object_data(kind,ident);key=str(feature['properties'].get(SOURCES[kind][1]) or ident)
   groups.setdefault(key,[]).append(feature)
  for parts in groups.values():
   feature=parts[0]
   if len(parts)>1:feature={**feature,'geometry':mapping(unary_union([make_valid(shape(p['geometry'])) for p in parts]))}
   geometry=make_valid(shape(feature['geometry']))
   line=transform(project,geometry.boundary).intersection(work_clip)
   latitude=geometry.centroid.y
   units_per_metre=1/(40075016.686*math.cos(math.radians(latitude)))
   outline=dedupe_outline(line,previous,unary_union(parks),units_per_metre,kind)
   prepared.append((feature,kind,outline))
   previous.append(line)
   if kind=='park':parks.append(line)
 return prepared

def render_tile(z,x,y):
 if not 8<=z<=14 or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Invalid boundary tile')
 factor=2**(z-CELL_ZOOM);features=[]
 for feature,kind,outline in prepared_cell(x//factor,y//factor):
  features.extend(outline_features(feature,kind,z,x,y,outline))
 n=2**z
 return mapbox_vector_tile.encode([{'name':'areas','features':features}],default_options={'extents':4096,'y_coord_down':True,'quantize_bounds':(x/n,y/n,(x+1)/n,(y+1)/n)})
