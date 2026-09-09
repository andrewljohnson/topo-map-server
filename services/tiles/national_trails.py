"""Bounded, persistent official trails and vehicle-route tiles, plus PCTA centerline.

Agency fields describe published designations, not live access or closure status.
A failed agency request raises; incomplete/failed responses are never cached as empty.
"""
import gzip, hashlib, json, math, os, re, time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import mapbox_vector_tile
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union
from shapely.affinity import affine_transform
from trail_matching import conflate, lines, paved_surface
from shapely import make_valid
from national_boundaries import cached, bounds, project

DATASET_ID = 'us-official-trails-v12'
RAW_CACHE_VERSION = 'us-official-trails-v1'
MIN_ZOOM, MAX_ZOOM = 5, 14
BOUNDS = [-180, 18, -60, 72]
CACHE = Path(os.environ.get('TILE_DATA_DIR', Path(__file__).parent/'data'))/'national-trails'/RAW_CACHE_VERSION
SOURCES = {
 'usfs': 'https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0',
 'nps': 'https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_Trails_Geographic/FeatureServer/0',
 'mvum_roads': 'https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_MVUM_02/MapServer/1',
 'mvum_trails': 'https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_MVUM_02/MapServer/2',
}
ROUTES = {'PCT':'Pacific Crest Trail','AT':'Appalachian Trail','CDT':'Continental Divide Trail',
 'JMT':'John Muir Trail','TRT':'Tahoe Rim Trail','PNT':'Pacific Northwest Trail',
 'AZT':'Arizona Trail','FT':'Florida Trail','IAT':'Ice Age Trail','NCT':'North Country Trail',
 'NET':'New England Trail','PHT':'Potomac Heritage Trail','NTT':'Natchez Trace Trail'}
ROUTE_BOUNDS = {'JMT':(-120.0,36.4,-118.0,38.0),'TRT':(-120.4,38.5,-119.6,39.5),
 'AT':(-85,33,-66,47),'CDT':(-118,30,-104,50),'PNT':(-125,47,-112,50),
 'AZT':(-115,31,-108,38),'FT':(-88,24,-79,32),'IAT':(-94,42,-86,47),
 'NCT':(-105,38,-70,50),'NET':(-75,40,-69,44),'PHT':(-81,36,-75,42),'NTT':(-92,30,-86,37)}
# Official USFS national_trail_designation numeric codes are retained rather than
# guessed; recognized route identities use explicit trail names.

def route_ref(name):
 name=str(name).upper()
 if re.search(r'\b(SPUR|CONNECTOR|ACCESS|APPROACH)\b',name):return ''
 for ref,full in ROUTES.items():
  stem=full.removesuffix(' Trail').upper()
  if stem in name: return ref
 return ''

def query(source, params):
 for attempt in range(3):
  try:
   req=Request(SOURCES[source]+'/query?'+urlencode(params),headers={'User-Agent':'topo-map-server/1.0 (official trails)'})
   with urlopen(req,timeout=60) as response: data=json.load(response)
   if 'error' in data or data.get('exceededTransferLimit') or data.get('properties',{}).get('exceededTransferLimit'):
    raise RuntimeError('Incomplete official trails response: '+str(data.get('error','transfer limit')))
   return data
  except Exception:
   if attempt==2:raise
   time.sleep(2**attempt)

def cell_features(source,z,x,y,overview=False):
 """IDs first, then bounded batches avoids ArcGIS silently truncated geometries."""
 def build():
  w,s,e,n=bounds(z,x,y); halo=.003
  where='1=1'
  if overview:
   field='trail_name' if source=='usfs' else 'TRLNAME'
   where=' OR '.join("upper(%s) like '%%%s%%'"%(field,name.removesuffix(' Trail').upper()) for ref,name in ROUTES.items() if ref!='PCT')
  response=query(source,{'f':'json','where':where,'returnIdsOnly':'true','geometryType':'esriGeometryEnvelope',
    'geometry':','.join(map(str,[w-halo,s-halo,e+halo,n+halo])),'inSR':4326,'spatialRel':'esriSpatialRelIntersects'})
  if 'objectIds' not in response:raise RuntimeError('Missing official trail IDs')
  ids=response['objectIds']
  if ids is None:ids=[]
  if not isinstance(ids,list) or len(ids)>10000:raise RuntimeError('Official trails query exceeds bounded cell limit')
  features=[]
  for start in range(0,len(ids),100):
   batch=ids[start:start+100]
   data=query(source,{'f':'geojson','objectIds':','.join(map(str,batch)),'outFields':'*','outSR':4326,
       'returnGeometry':'true','returnZ':'false','returnM':'false','geometryPrecision':7,'maxAllowableOffset':.00001 if not overview else .001})
   if len(data.get('features',[]))!=len(batch):raise RuntimeError('Missing official trail objects')
   features.extend(data['features'])
  return features
 return cached(CACHE/('overview' if overview else 'detail')/source/str(z)/str(x)/(str(y)+'.json'),build)

def properties(source, feature):
 p={k.lower():v for k,v in feature.get('properties',{}).items()}
 name=p.get('trail_name') or p.get('trlname') or p.get('name') or ''
 ident=str(p.get('globalid') or p.get('featureid') or p.get('objectid') or feature.get('id') or '')
 out={'id':source+'-'+ident,'name':name,'agency':'NPS' if source=='nps' else 'USFS',
  'kind':'forest_road' if source=='mvum_roads' else 'motorized_trail' if source=='mvum_trails' else 'trail',
  'ref':str(p.get('trail_no') or p.get('id') or ''),'surface':str(p.get('trail_surface') or p.get('trlsurface') or p.get('surfacetype') or ''),
  'trail_class':str(p.get('trail_class') or p.get('trlclass') or p.get('trailclass') or ''),
  'use':str(p.get('trluse') or p.get('allowed_terra_use') or ''),
  'seasonal':str(p.get('seasonal') or ''),'season_description':str(p.get('seasdesc') or ''),
  'access':str(p.get('opentopublic') or p.get('accessnotes') or ''),'mvum_symbol':str(p.get('mvum_symbol_name') or p.get('mvum_symbol') or ''),
  'route_ref':route_ref(name),'source_url':SOURCES[source]}
 if source=='nps' and str(p.get('opentopublic','')).lower() in ('no','n','false'):return None
 if source=='usfs' and p.get('trail_type') not in (None,'TERRA'):return None
 if source.startswith('mvum'):
  # Preserve vehicle permissions separately from dates; never infer all vehicles allowed.
  for key,value in p.items():
   if key.endswith('_datesopen') or key in ('passengervehicle','highclearancevehicle','motorcycle','atv','fourwd_gt50inches','e_bike_class1','e_bike_class2','e_bike_class3','operationalmaintlevel','routestatus','trailstatus'):
    if value is not None:out[key]=str(value)
 return out

@lru_cache(maxsize=1)
def pct_features():
 path=Path(__file__).parent/'regions/pct-centerline-2026.geojson.gz'
 with gzip.open(path,'rt') as stream: data=json.load(stream)
 return [(transform(project,shape(f['geometry'])),{'id':'pcta-'+str(i),'name':'Pacific Crest Trail','route_ref':'PCT','badge':'trail-PCT','agency':'PCTA','kind':'long_distance_trail','section':f['properties'].get('section','')}) for i,f in enumerate(data['features'])]

def clipped_feature(geometry, props, clip, n):
 if not geometry.intersects(clip):return None
 geom=geometry.intersection(clip).simplify(.22/512/n,preserve_topology=True)
 if geom.is_empty or geom.geom_type not in ('LineString','MultiLineString'):return None
 return {'geometry':geom,'id':int.from_bytes(hashlib.sha256(props['id'].encode()).digest()[:6],'big'),'properties':props}

def osm_network(z,x,y,blob=None):
 from national_basemap import archive, normalize_tile
 if blob is None:blob=normalize_tile(archive().get(z,x,y),z)
 layer=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True}).get('road',{})
 extent=layer.get('extent',4096);n=2**z
 result=[]
 for f in layer.get('features',[]):
  geometry=affine_transform(shape(f['geometry']),[1/extent/n,0,0,1/extent/n,x/n,y/n])
  props={**f['properties'],'id':f"osm-{z}-{x}-{y}-{f['id']}",'agency':'OpenStreetMap','route_ref':route_ref(f['properties'].get('name','')),'source_url':'https://www.openstreetmap.org/copyright'}
  result.append({'id':f['id'],'properties':props,'geometry':geometry})
 return result



def agency_road_class(props):
 # MVUM includes paved passenger-car roads as well as tracks. Preserve the
 # raw agency surface in provenance, and never infer pavement from access.
 return 'unclassified' if paved_surface(props.get('surface')) else 'track'


@lru_cache(maxsize=32)
def prepared_agency_features(source,z,x,y,overview=False):
 """Parse/project a raw source cell once for its adjacent fine children."""
 result=[]
 for raw in cell_features(source,z,x,y,overview):
  props=properties(source,raw)
  if props is None or not raw.get('geometry'):continue
  geometry=transform(project,make_valid(shape(raw['geometry'])))
  ref=props['route_ref']
  if ref in ROUTE_BOUNDS and not geometry.intersects(transform(project,box(*ROUTE_BOUNDS[ref]))):
   props['route_ref']=''
  if overview and not props['route_ref']:continue
  props['class']=agency_road_class(props) if source=='mvum_roads' else 'path'
  result.append((geometry,props))
 return tuple(result)


def render_tile(z,x,y,*,basemap_tile=None):
 if not MIN_ZOOM<=z<=MAX_ZOOM or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Invalid official trails tile')
 n=2**z;pad=8/512/n;clip=box(x/n-pad,y/n-pad,(x+1)/n+pad,(y+1)/n+pad)
 # Match before final clipping so tile-edge fragments have enough context.
 workclip=box(x/n-64/512/n,y/n-64/512/n,(x+1)/n+64/512/n,(y+1)/n+64/512/n)
 layers={'trails':[],'roads':[],'routes':[],'network':[]};additions=[]
 for geometry,props in pct_features():
  f=clipped_feature(geometry,props,workclip,n)
  if f:
   layers['routes'].append(f)
   additions.append({**f,'properties':{**props,'class':'path'}})
 overview=z<11;cellz=min(z,7 if overview else 11);factor=2**(z-cellz)
 sources=['usfs','nps'] if overview else ['nps','usfs','mvum_trails','mvum_roads']
 for source in sources:
  for geometry,cached_props in prepared_agency_features(source,cellz,x//factor,y//factor,overview):
   props=dict(cached_props)
   f=clipped_feature(geometry,props,workclip,n)
   if not f:continue
   ref=props['route_ref']
   if ref and ref!='PCT':
    layers['routes'].append({**f,'properties':{**props,'kind':'long_distance_trail','badge':'trail-'+ref}})
   if not overview:additions.append(f)
 # Use a local ground-distance scale (Web Mercator distorts lengths by latitude).
 latitude=math.atan(math.sinh(math.pi*(1-2*(y+.5)/n)))
 scale=40075016.68557849*math.cos(latitude)
 def metres(f):return {**f,'geometry':affine_transform(f['geometry'],[scale,0,0,scale,-x/n*scale,-y/n*scale]),'properties':dict(f['properties'])}
 def world(f):return {**f,'geometry':affine_transform(f['geometry'],[1/scale,0,0,1/scale,x/n,y/n])}
 # Route badge identities remain separate even where two routes share a path.
 route_groups={}
 for f in layers['routes']:route_groups.setdefault(f['properties'].get('route_ref',''),[]).append(metres(f))
 layers['routes']=[world(f) for group in route_groups.values() for f in conflate([],group)]
 if not overview:
  base=osm_network(z,x,y,basemap_tile)
  network=[world(f) for f in conflate([metres(f) for f in base],[metres(f) for f in additions])]
  layers['network']=network if z>=13 else []
  # Below z13 only overview routes and nonduplicated MVUM road additions draw.
  layers['roads']=[f for f in network if f['properties'].get('kind')=='forest_road'] if z<13 else []
 for name,features in layers.items():
  output=[]
  for f in features:
   geometry=unary_union(lines(f['geometry'].intersection(clip)))
   if not geometry.is_empty:
    from cartographic_names import display_name
    props=dict(f['properties']);display=display_name(props.get('name',''))
    if display!=props.get('name',''):props['display_name']=display
    output.append({**f,'geometry':geometry,'properties':props})
  # Presentation context must never split reference features before matching.
  from path_context import annotate
  layers[name]=annotate(output,z,x,y,world=True)[0] if name=='network' else output
 return mapbox_vector_tile.encode([{'name':name,'features':features} for name,features in layers.items()],default_options={'extents':4096,'y_coord_down':True,'quantize_bounds':(x/n,y/n,(x+1)/n,(y+1)/n)})
