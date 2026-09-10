"""Public NPS/USFS recreation points and optional local RIDB facilities index.

Every symbol retains the agency point. Facility service descriptions are metadata,
not invented restroom/water locations. Cold queries are bounded z10 cells.
"""
import csv, hashlib, html, io, json, math, os, re, sqlite3, zipfile
from pathlib import Path
from cache_paths import working_path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import mapbox_vector_tile
from shapely.geometry import Point
from shapely.ops import nearest_points
from national_boundaries import cached, bounds
from feature_matching import match_reason, merge_into, osm_kind, name_key, GENERIC
from poi_ranking import features as ranked_features
DATASET_ID = 'us-agency-recreation-v9'
# Processing revisions reuse the pinned agency responses and RIDB import.
RAW_CACHE_VERSION = 'us-agency-recreation-v1'
MIN_ZOOM, MAX_ZOOM, CELL_ZOOM = 6, 14, 10
BOUNDS = [-180, 18, 180, 72]
CACHE = Path(os.environ.get('TILE_DATA_DIR', Path(__file__).parent/'data'))/'national-recreation'/RAW_CACHE_VERSION
RIDB_DB = CACHE/'ridb.sqlite'
SOURCES = {
 'nps': 'https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/MapServer/0',
 'usfs': 'https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0',
}
NPS_TYPES = {'Campground':('campground','campsite',12), 'Primitive Camping':('backcountry_camp','campsite',13), 'Trailhead':('trailhead','information',12), 'Ranger Station':('ranger_station','information',12), 'Visitor Center':('visitor_center','information',12), 'Restroom':('restroom','toilet',15), 'Drinking Water':('drinking_water','drinking-water',15), 'Picnic Area':('picnic_site','picnic-site',14), 'Viewpoint':('viewpoint','viewpoint',13), 'Waterfall':('waterfall','marker',13), 'Spring':('spring','marker',14), 'Hut':('shelter','lodging',13), 'Shelter':('shelter','marker',14), 'Store':('store','shop',15), 'Food Service':('food','restaurant',15), 'Lodging':('lodging','lodging',14), 'First Aid Station':('first_aid','hospital',14)}
FS_TYPES = {'CAMPGROUND':('campground','campsite',12),'GROUP CAMPGROUND':('campground','campsite',12),'CAMPING AREA':('backcountry_camp','campsite',13),'HORSE CAMP':('campground','campsite',13),'TRAILHEAD':('trailhead','information',12),'LOOKOUT/CABIN':('shelter','lodging',13),'OBSERVATION SITE':('viewpoint','viewpoint',13),'WILDLIFE VIEWING SITE':('viewpoint','viewpoint',13),'PICNIC SITE':('picnic_site','picnic-site',14),'GROUP PICNIC SITE':('picnic_site','picnic-site',14),'INFO SITE/FEE STATION':('information','information',14),'INTERPRETIVE VISITOR CENTER (MAJOR)':('visitor_center','information',12),'INTERPRETIVE VISITOR CENTER (MINOR)':('visitor_center','information',13)}

def clean(value, limit=1000):
 return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', str(value or '')))).strip()[:limit]

def normalize(feature, agency):
 p=feature.get('properties',{}); geom=feature.get('geometry')
 if not geom or geom.get('type')!='Point':return None
 lon,lat=geom['coordinates'][:2]
 if not(-180<=lon<=180 and (lon<=-60 or lon>=170) and 18<=lat<=72):return None
 if agency=='nps':
  if p.get('ISEXTANT')=='No' or p.get('OPENTOPUBLIC')=='No' or p.get('PUBLICDISPLAY') not in (None,'Public Map Display') or p.get('DATAACCESS') not in (None,'Unrestricted'):return None
  info=NPS_TYPES.get(p.get('POITYPE')); name=clean(p.get('MAPLABEL') or p.get('POINAME'),180)
  ident=p.get('FEATUREID') or p.get('GEOMETRYID') or p.get('OBJECTID'); unit=p.get('UNITNAME'); url=SOURCES[agency]
  details={'season':p.get('SEASDESC'),'access_notes':p.get('ACCESSNOTES'),'coordinate_accuracy':p.get('XYACCURACY')}
 else:
  if p.get('development_status') not in (None,'EXISTING'):return None
  info=FS_TYPES.get(p.get('site_type')); name=clean(p.get('public_site_name') or p.get('site_name'),180)
  # Public name reflects a changed use in several USFS records (e.g. Bayview).
  if 'trailhead' in name.lower():info=FS_TYPES['TRAILHEAD']
  ident=p.get('site_cn') or p.get('globalid') or p.get('objectid'); unit=p.get('recarea_name'); url=p.get('usda_portal_url') or SOURCES[agency]
  details={k:p.get(v) for k,v in {'description':'recarea_description','water':'water_availability','restrooms':'restroom_availability','fee':'fee_description','season':'open_season','services':'service_type_list','activities':'activity_type_list','restrictions':'restrictions','ridb_id':'rec1stop_id'}.items()}
 if not info or not ident:return None
 kind,icon,minzoom=info; frame='circle' if kind in ('viewpoint','spring','waterfall') else 'square'
 props={'id':agency+':'+str(ident),'name':name,'kind':kind,'poi_icon':icon,'poi_frame':frame,'poi_image':'poi-'+frame+'-'+icon,'min_zoom':minzoom,'agency':agency.upper(),'unit':clean(unit,180),'source_url':url}
 props.update({k:clean(v) for k,v in details.items() if clean(v) not in ('','No Data','Unknown')})
 props['website']=url
 props['details']=props.get('description','')
 return {'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':props}

def query_cell(agency,x,y):
 w,s,e,n=bounds(CELL_ZOOM,x,y)
 params={'f':'geojson','where':'1=1','geometryType':'esriGeometryEnvelope','geometry':','.join(map(str,[w,s,e,n])),'inSR':4326,'outSR':4326,'outFields':'*','returnGeometry':'true','resultRecordCount':2000}
 request=Request(SOURCES[agency]+'/query?'+urlencode(params),headers={'User-Agent':'topo-map-server/1.0 public recreation map'})
 with urlopen(request,timeout=50) as response:data=json.load(response)
 if data.get('error') or data.get('exceededTransferLimit') or not isinstance(data.get('features'),list):raise RuntimeError('Incomplete '+agency+' recreation query')
 return data

def cell_data(agency,x,y):
 return cached(CACHE/'cells'/agency/str(x)/(str(y)+'.json'),lambda:query_cell(agency,x,y))

def normalized_name(name):
 return re.sub(r'[^a-z0-9]', '',str(name).lower())

def distance(a,b):
 return math.hypot(((a[0]-b[0]+180)%360-180)*111320*math.cos(math.radians(a[1])),(a[1]-b[1])*111320)

def dedupe(features):
 result=[]
 for f in features:
  p=f['properties']; coords=f['geometry']['coordinates']
  identical=next((g for g in result if g['properties']['id']==p['id']),None)
  if identical is not None:
   merge_into(identical,f,'source_id');continue
  candidates=[]
  for g in result:
   why=match_reason(f,g)
   if why:candidates.append((0 if why in ('gnis_id','geonames_id','ridb_id') else 1,distance(coords,g['geometry']['coordinates']),g,why))
  candidates.sort(key=lambda c:(c[0],c[1],c[2]['properties']['id']))
  if candidates and (candidates[0][0]==0 or len(candidates)==1 or candidates[1][1]-candidates[0][1]>=30):
   _,_,duplicate,why=candidates[0];merge_into(duplicate,f,why)
  else:result.append(f)
 return result

def ridb_features(extent):
 if not RIDB_DB.exists():return []
 w,s,e,n=extent
 with sqlite3.connect('file:'+str(RIDB_DB)+'?mode=ro',uri=True) as db:
  return [json.loads(r[0]) for r in db.execute('SELECT feature FROM facilities WHERE lon>=? AND lon<? AND lat>=? AND lat<?',(w,e,s,n))]

def mark_osm_duplicates(features,x,y):
 # Read only already available OSM cells; no Overpass request blocks this source.
 from national_amenities import CACHE as OSM_CACHE
 osm={};site_polygons={}
 # Neighbor cells cover matches straddling a cache boundary; never fetch upstream.
 for cx in range(max(0,x-1),min(1024,x+2)):
  for cy in range(max(0,y-1),min(1024,y+2)):
   path=working_path(OSM_CACHE/'cells'/str(cx)/(str(cy)+'.json'))
   try:
    for g in json.loads(path.read_text()).get('features',[]):
     q=g.get('properties',{});coords=g.get('geometry',{}).get('coordinates',[])
     if q.get('osm_id') and len(coords)==2 and isinstance(coords[0],(int,float)):osm[q['osm_id']]=g
   except (OSError,ValueError):continue
   # Retained raw outlines distinguish a facility's extent from its label anchor.
   # Never fetch or infer an extent from the distance between representative points.
   try:
    from regions.build_amenities import geometry
    for element in json.loads(path.with_suffix('.raw.json').read_text()).get('elements',[]):
     if element.get('tags',{}).get('tourism') not in ('camp_site','caravan_site'):continue
     polygon=geometry(element)
     if polygon is not None and polygon.geom_type in ('Polygon','MultiPolygon') and polygon.is_valid:
      site_polygons[element['type']+'/'+str(element['id'])]=polygon
   except (OSError,ValueError,KeyError):pass
 for f in features:
  p=f['properties'];candidates=[]
  for g in osm.values():
   q=g['properties'];candidate={**g,'properties':{**q,'kind':osm_kind(q)}}
   why=match_reason(f,candidate)
   # A campground's point-on-surface can be far from an agency entrance point.
   # Matching names + site polygon (10m survey tolerance) is facility evidence;
   # a wider radius alone is not. Do not apply to toilets, loops, or other kinds.
   polygon=site_polygons.get(q['osm_id'])
   name=name_key(p.get('name'),'campground')
   if not why and p.get('kind')==candidate['properties']['kind']=='campground' and not p.get('match_ambiguous') and name not in GENERIC and name==name_key(q.get('name'),'campground') and polygon is not None and distance(f['geometry']['coordinates'],list(nearest_points(polygon,Point(f['geometry']['coordinates']))[0].coords)[0])<=10:
    why='name_kind_site_polygon'
   if why:candidates.append((distance(f['geometry']['coordinates'],g['geometry']['coordinates']),q,why))
  candidates.sort(key=lambda c:c[0])
  if candidates and (len(candidates)==1 or candidates[1][0]-candidates[0][0]>=30):
   meters,q,why=candidates[0];p.update(osm_duplicate=True,matched_osm_id=q['osm_id'],osm_match_distance_m=round(meters,1),osm_match_reason=why)

 return features

def prepare_cell(detail_zoom,cx,cy):
 """Prepare one source cell once for a bounded offline build; caller owns caching.

Returned records are read-only to tile encoders. No process-wide cache is used:
agency/ranking/amenity inputs may change between independent builds.
 """
 if not CELL_ZOOM<=detail_zoom<=MAX_ZOOM:raise ValueError('Invalid recreation detail zoom')
 features=[]
 for agency in SOURCES:
  for raw in cell_data(agency,cx,cy)['features']:
   f=normalize(raw,agency)
   if f:features.append(f)
 w,s,e,n=bounds(CELL_ZOOM,cx,cy);extent=(w-.005,s-.005,e+.005,n+.005)
 ranked=[f for f in ranked_features(extent,14) if f['properties']['rank_family'] in ('destination','detail') or f['properties']['label_minzoom']<=detail_zoom]
 return mark_osm_duplicates(dedupe(features+ridb_features(extent)+ranked),cx,cy)

def render_tile(z,x,y,*,detail_zoom=None,extent=4096,prepared=None):
 if not MIN_ZOOM<=z<=MAX_ZOOM or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Invalid recreation tile')
 detail_zoom=z if detail_zoom is None else detail_zoom
 if not z<=detail_zoom<=MAX_ZOOM or extent not in (4096,16384):raise ValueError('Invalid recreation detail encoding')
 if z>=CELL_ZOOM:
  factor=2**(z-CELL_ZOOM)
  features=prepare_cell(detail_zoom,x//factor,y//factor) if prepared is None else prepared
 else:
  if prepared is not None or detail_zoom!=z:raise ValueError('Detailed parents must be within a source cell')
  features=ranked_features(bounds(z,x,y),z)
 result=[]
 for f in features:
  lon,lat=f['geometry']['coordinates']; wx=(lon+180)/360*2**z;wy=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z
  if not(x<=wx<x+1 and y<=wy<y+1):continue
  p=f['properties'];result.append({'geometry':Point((wx-x)*extent,(wy-y)*extent),'properties':p,'id':int.from_bytes(hashlib.sha256(p['id'].encode()).digest()[:6],'big')})
 return mapbox_vector_tile.encode([{'name':'recreation','features':result}],default_options={'extents':extent,'y_coord_down':True})

def import_ridb(archive, destination=None):
 """Import only facilities with actual coordinates, never permit sales centroids.

Pass a local official RIDBFullExport_V1_CSV.zip. Atomic replacement means readers
continue using a complete previous import during refresh.
 """
 destination=Path(destination or RIDB_DB);destination.parent.mkdir(parents=True,exist_ok=True)
 pending=destination.with_suffix('.pending.sqlite');pending.unlink(missing_ok=True)
 count=0
 with zipfile.ZipFile(archive) as z, sqlite3.connect(pending) as db:
  db.execute('CREATE TABLE facilities(id TEXT PRIMARY KEY,lon REAL,lat REAL,feature TEXT)')
  for r in csv.DictReader(io.TextIOWrapper(z.open('Facilities_API_v1.csv'),encoding='utf-8-sig')):
   category=r.get('FacilityTypeDescription');name=clean(r.get('FacilityName'),180)
   if category not in ('Campground','Visitor Center') or r.get('Enabled','true').lower()=='false':continue
   try:lon=float(r['FacilityLongitude']);lat=float(r['FacilityLatitude'])
   except (ValueError,KeyError):continue
   if not(-180<=lon<=180 and (lon<=-60 or lon>=170) and 18<=lat<=72):continue
   icon='campsite' if category=='Campground' else 'information';ident=r['FacilityID'];url=r.get('FacilityReservationURL') or 'https://www.recreation.gov/'+('camping/campgrounds/' if category=='Campground' else '')+ident
   if category!='Campground' and not r.get('FacilityReservationURL'):url='https://ridb.recreation.gov/download'
   p={'id':'ridb:'+ident,'ridb_id':ident,'name':name,'kind':'campground' if category=='Campground' else 'visitor_center','poi_icon':icon,'poi_frame':'square','poi_image':'poi-square-'+icon,'min_zoom':12,'agency':'Recreation.gov','unit':'','source_url':url,'website':url}
   for key,field in {'description':'FacilityDescription','fee':'FacilityUseFeeDescription','phone':'FacilityPhone','accessibility':'FacilityAccessibilityText','stay_limit':'StayLimit','updated':'LastUpdatedDate'}.items():
    value=clean(r.get(field),1800 if key=='description' else 1000)
    if value:p[key]=value
   p['details']=p.get('description','')
   f={'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':p}
   db.execute('INSERT OR REPLACE INTO facilities VALUES(?,?,?,?)',(p['id'],lon,lat,json.dumps(f,separators=(',',':'))));count+=1
  db.execute('CREATE INDEX facilities_position ON facilities(lon,lat)');db.commit()
 pending.replace(destination)
 return count

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--import-ridb',type=Path,required=True)
 args=parser.parse_args();print('Imported',import_ridb(args.import_ridb),'RIDB facilities into',RIDB_DB)
