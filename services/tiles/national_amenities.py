"""Durable, on-demand OSM facility groups, independent of the basemap cache."""
import fcntl, hashlib, json, math, os, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import mapbox_vector_tile
from shapely.geometry import Point
from regions.build_amenities import build, geometry, AMENITIES, TOURISM
DATASET_ID='osm-us-amenities-v3'
BUILD_VERSION=3
ROOT=Path(__file__).resolve().parent
CACHE=Path(os.environ.get('TILE_DATA_DIR',ROOT/'data'))/'national-amenities'/'osm-us-amenities-v1' # Raw extracts are reusable across processing revisions.
URL=os.environ.get('AMENITY_OVERPASS_URL','https://overpass-api.de/api/interpreter')
FALLBACK_URL=os.environ.get('AMENITY_OVERPASS_FALLBACK_URL','https://overpass.private.coffee/api/interpreter')
CELL_ZOOM=10
# Request only categories the renderer uses; broad leisure queries can pull
# enormous nature-reserve relations unrelated to facility icons.
TAGS=['amenity~"^('+ '|'.join(AMENITIES) +')$"',
      'tourism~"^('+ '|'.join(TOURISM) +')$"',
      'leisure~"^(swimming_area|swimming_pool)$"',
      'shop~"^(supermarket|convenience|outdoor|gift|general)$"',
      'waterway=slipway','sport=swimming','drinking_water=yes','toilets=yes']
def bounds(z,x,y):
    n=2**z
    lat=lambda t:math.degrees(math.atan(math.sinh(math.pi*(1-2*t/n))))
    return x/n*360-180,lat(y+1),(x+1)/n*360-180,lat(y)
def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as out:
        json.dump(data,out,separators=(',',':')); name=out.name
    Path(name).replace(path)
def query_box(box):
    w,s,e,n=box
    return '[out:json][timeout:45];('+''.join('nwr['+tag+']('+','.join(map(str,[s,w,n,e]))+');' for tag in TAGS)+');out body geom;'
def fetch(query):
    from osm_bulk import query_local
    local=query_local(query)
    if local is not None:return local
    CACHE.mkdir(parents=True,exist_ok=True)
    with (CACHE/'request.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        stamp=CACHE/'last-request.json'
        endpoints=list(dict.fromkeys([URL,FALLBACK_URL]))
        for attempt in range(3):
            previous=json.loads(stamp.read_text()).get('time',0) if stamp.exists() else 0
            time.sleep(max(0,5-(time.time()-previous)))
            atomic_json(stamp,{'time':time.time()})
            try:
                endpoint=endpoints[attempt % len(endpoints)]
                encoded=urlencode({'data':query})
                # GET also works through networks/providers that stall interpreter POSTs.
                use_get=endpoint != URL
                req=Request(endpoint+('?' + encoded if use_get else ''),data=None if use_get else encoded.encode(),headers={'User-Agent':'topo-map-server/1.0 (on-demand amenity tiles)','Content-Type':'application/x-www-form-urlencoded'})
                with urlopen(req,timeout=65) as response:data=json.load(response)
                if data.get('remark') or not isinstance(data.get('elements'),list):raise RuntimeError('Incomplete Overpass response: '+str(data.get('remark','missing elements')))
                data['_endpoint']=endpoint
                return data
            except Exception:
                if attempt==2:raise
                time.sleep(2**attempt*3)
def cell_data(x,y):
    path=CACHE/'cells'/str(x)/(str(y)+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():
            cached=json.loads(path.read_text())
            if cached.get('build_version')==BUILD_VERSION:return cached
            raw_path=path.with_suffix('.raw.json')
            if raw_path.exists():
                rebuilt=build(json.loads(raw_path.read_text()))
                cached.update(features=rebuilt['features'],build_version=BUILD_VERSION)
                atomic_json(path,cached)
                return cached
        w,s,e,n=bounds(CELL_ZOOM,x,y)
        # Halo supports groups near cell edges; full geometry keeps anchors stable.
        pad=.025; lonpad=pad/max(.2,math.cos(math.radians((s+n)/2)))
        extent=[max(-180,w-lonpad),max(-85,s-pad),min(180,e+lonpad),min(85,n+pad)]
        query=query_box(extent); raw=fetch(query)
        # Fetch complete member coverage of sites whose full polygons leave the
        # halo. Membership then remains the same from either side of a cell edge.
        expanded=list(extent)
        for element in raw['elements']:
            tags=element.get('tags',{})
            if not tags.get('name') or not (tags.get('tourism') in {'camp_site','caravan_site','picnic_site'} or tags.get('information')=='visitor_centre'):continue
            shape=geometry(element)
            if shape is None or shape.is_empty:continue
            a,b,c,d=shape.bounds
            if c-a>1 or d-b>1:raise RuntimeError('Site geometry too large for bounded amenity query')
            expanded=[min(expanded[0],a-.001),min(expanded[1],b-.001),max(expanded[2],c+.001),max(expanded[3],d+.001)]
        if expanded!=extent:
            query=query_box(expanded); raw=fetch(query); extent=expanded
        result=build(raw)
        result.update(build_version=BUILD_VERSION,bounds=extent,osm_timestamp=raw.get('osm3s',{}).get('timestamp_osm_base'),query=query,source=raw.get('_endpoint',URL))
        atomic_json(path.with_suffix('.raw.json'),raw)
        atomic_json(path,result)
        return result
def render_tile(z,x,y):
    if not 10<=z<=14 or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Invalid amenities tile')
    factor=2**(z-CELL_ZOOM);data=cell_data(x//factor,y//factor);features=[]
    for feature in data['features']:
        lon,lat=feature['geometry']['coordinates'];wx=(lon+180)/360*2**z
        wy=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z
        # Half-open ownership prevents duplicate icons on boundaries.
        if not(x<=wx<x+1 and y<=wy<y+1):continue
        props={k:v for k,v in feature['properties'].items() if isinstance(v,(str,int,float,bool))}
        if props['kind']=='group':
            icons=feature['properties']['icons'][:12]
            props.update(grid_image='amenity-grid:'+','.join(icons),grid_rows=math.ceil(len(icons)/3),min_zoom=13 if len(icons)==1 else 10)
        features.append({'geometry':Point((wx-x)*4096,(wy-y)*4096),'properties':props,'id':int.from_bytes(hashlib.sha256((props['osm_id']+props['kind']+props.get('poi_icon','')).encode()).digest()[:7],'big') & ((1<<53)-1)})
    return mapbox_vector_tile.encode([{'name':'amenities','features':features}],default_options={'extents':4096,'y_coord_down':True})
