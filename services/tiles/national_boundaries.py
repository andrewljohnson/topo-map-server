"""Detailed agency outlines. Extract true boundaries before tile clipping."""
import fcntl, hashlib, json, math, os, tempfile, time, threading
from pathlib import Path
from functools import lru_cache
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import mapbox_vector_tile
from shapely import make_valid
from shapely.geometry import shape, box, mapping
from shapely.ops import transform, unary_union
DATASET_ID='us-agency-boundaries-v3'
CACHE=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).parent/'data'))/'national-boundaries'/'us-agency-boundaries-v1'
SOURCES={
'park':('https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2','UNIT_CODE','UNIT_NAME'),
'forest':('https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0','adminforestid','forestname'),
'wilderness':('https://services1.arcgis.com/ERdCHt0sNM6dENSD/arcgis/rest/services/Wilderness_Areas_in_the_United_States/FeatureServer/0','WID','NAME')}
CELL_ZOOM=8
PREPARE_LOCK=threading.Lock()

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

def shared_forest_outline(line, polygon, neighbors, units_per_metre):
 """One cartographic stroke for adjacent, overlapping forest administrations.

 Retain all designation polygons. Distinct gaps, nested areas, crossings and
 other designation types cannot qualify solely because their lines are close.
 """
 from shapely.geometry import Point
 from shapely.ops import substring
 for prior_line,prior_polygon in neighbors:
  if not polygon.intersects(prior_polygon):continue
  corridor=prior_line.buffer(250*units_per_metre,quad_segs=2)
  for coherent in line_parts(line.intersection(corridor)):
   if coherent.length<1000*units_per_metre:continue
   chunks=max(1,int(coherent.length/(1500*units_per_metre)))
   for chunk in range(chunks):
    run=substring(coherent,coherent.length*chunk/chunks,coherent.length*(chunk+1)/chunks)
    opposite=0;count=9
    for i in range(count):
     distance=run.length*(i+.5)/count
     before=run.interpolate(max(0,distance-25*units_per_metre));after=run.interpolate(min(run.length,distance+25*units_per_metre))
     dx,dy=after.x-before.x,after.y-before.y;length=math.hypot(dx,dy)
     if not length:continue
     center=run.interpolate(distance);offset=300*units_per_metre
     left=Point(center.x-dy/length*offset,center.y+dx/length*offset)
     right=Point(center.x+dy/length*offset,center.y-dx/length*offset)
     if ((polygon.covers(left) and not polygon.covers(right) and prior_polygon.covers(right) and not prior_polygon.covers(left)) or
         (polygon.covers(right) and not polygon.covers(left) and prior_polygon.covers(left) and not prior_polygon.covers(right))):opposite+=1
    if opposite>=8:line=line.difference(run.buffer(.01*units_per_metre))
 return line


def area_geometry(raw):
 """Keep valid area components; collapsed repair lines have no land footprint."""
 geometry=make_valid(shape(raw))
 if geometry.geom_type in ('Polygon','MultiPolygon'):return geometry
 def polygons(g):
  if g.geom_type=='Polygon':yield g
  else:
   for child in getattr(g,'geoms',[]):yield from polygons(child)
 return unary_union(list(polygons(geometry)))

def outline_features(feature,kind,z,x,y,outline=None,geometry=None):
 n=2**z;pad=8/512/n
 geometry=area_geometry(feature['geometry']) if geometry is None else geometry
 if geometry.is_empty:return []
 # Boundary first prevents fabricated lines on tile edges.
 clip=box(x/n-pad,y/n-pad,(x+1)/n+pad,(y+1)/n+pad)
 clipped=(transform(project,geometry.boundary) if outline is None else outline).intersection(clip).simplify(.35/512/n,preserve_topology=True)
 geographic_clip=transform(lambda u,v:(u*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*v))))),clip)
 fill=transform(project,geometry.intersection(geographic_clip)).simplify(.35/512/n,preserve_topology=True)
 _,idfield,namefield=SOURCES[kind];props=feature['properties'];ident=kind+'-'+str(props.get(idfield) or props.get(namefield))
 pieces=list(clipped.geoms) if clipped.geom_type=='GeometryCollection' else [clipped]
 pieces.extend(list(fill.geoms) if fill.geom_type=='GeometryCollection' else [fill])
 return [{'geometry':p,'id':int.from_bytes(hashlib.sha256(ident.encode()).digest()[:6],'big'),'properties':{'id':ident,'kind':kind,'name':str(props.get(namefield) or '')}} for p in pieces if not p.is_empty and p.geom_type in ('LineString','MultiLineString','Polygon','MultiPolygon')]

@lru_cache(maxsize=4)
def prepared_cell(cx,cy):
 prepared=[];previous=[];parks=[];forests=[]
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
   if len(parts)>1:feature={**feature,'geometry':mapping(unary_union([area_geometry(p['geometry']) for p in parts]))}
   geometry=area_geometry(feature['geometry'])
   if geometry.is_empty:continue
   projected=transform(project,geometry)
   line=projected.boundary.intersection(work_clip)
   latitude=geometry.centroid.y
   units_per_metre=1/(40075016.686*math.cos(math.radians(latitude)))
   # Match the coherent edge before narrow suppression can split long runs.
   outline=shared_forest_outline(line,projected.intersection(work_clip),forests,units_per_metre) if kind=='forest' else line
   outline=dedupe_outline(outline,previous,unary_union(parks),units_per_metre,kind)
   prepared.append((feature,kind,outline,geometry))
   previous.append(line)
   if kind=='park':parks.append(line)
   if kind=='forest':forests.append((line,projected.intersection(work_clip)))
 return prepared

def render_tile(z,x,y):
 if not 8<=z<=14 or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Invalid boundary tile')
 factor=2**(z-CELL_ZOOM);features=[]
 # Cache lookup must occur under the lock: lru_cache alone allows concurrent
 # misses to build duplicate copies of the same large agency polygons.
 with PREPARE_LOCK:prepared=prepared_cell(x//factor,y//factor)
 for feature,kind,outline,geometry in prepared:
  features.extend(outline_features(feature,kind,z,x,y,outline,geometry))
 n=2**z
 return mapbox_vector_tile.encode([{'name':'areas','features':features}],default_options={'extents':4096,'y_coord_down':True,'quantize_bounds':(x/n,y/n,(x+1)/n,(y+1)/n)})
