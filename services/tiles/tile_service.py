#!/usr/bin/env python3
"""Regional OSM -> indexed geometry -> true Mapbox Vector Tiles, fully self hosted."""
import argparse
import base64
from contextlib import contextmanager, nullcontext
import gzip
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import signal
import shutil
import access_control
import object_cache
import coverage_policy
import weakref
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlsplit

import mapbox_vector_tile
from shapely import from_wkb, make_valid, STRtree
from shapely.geometry import Point, LineString, Polygon, box, mapping
from shapely.ops import polygonize, unary_union

MODE = os.environ.get('TILE_MODE', 'regional')
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('TILE_DATA_DIR', ROOT / 'data'))
DB = DATA / 'maryland.sqlite'
CONTOURS_DB = DATA / 'contours.sqlite'
BOUNDS = [-79.49, 37.88, -75.03, 39.73]
STYLE_VERSION = 'mvt-v3-osm'
CONTOUR_STYLE_VERSION = 'mvt-v1-contours'
META = {'name': 'Maryland', 'bounds': BOUNDS, 'center': [-76.6122, 39.2904], 'initialZoom': 12,
        'minZoom': 6, 'maxZoom': 14, 'tileUrl': '/tiles/{z}/{x}/{y}.pbf', 'gridZoom': 12, 'format': 'pbf', 'batchUrl': '/tile-batch', 'batchSize': 8,
        'attribution': '© OpenStreetMap contributors', 'source': 'Geofabrik Maryland extract',
        'description': 'Vector roads, trails, water, land cover, buildings and places. No elevation contours yet.'}
SOURCE_URL = 'https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf'
POLYGON_LAYERS = {'water','building','forest','grass','residential','rock','land'}
LAYERS = ['land','residential','grass','forest','rock','water','waterline','building','rail','road','label']

def project(lon, lat):
    lat = max(-85.05112878, min(85.05112878, lat))
    return ((lon + 180) / 360, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2)

def tile_range(z):
    if MODE == 'national':
        return (0,0,2**z-1,2**z-1)
    west, south, east, north = BOUNDS
    x0, y0 = project(west, north)
    x1, y1 = project(east, south)
    n = 2 ** z
    return (int(x0*n), int(y0*n), int(x1*n), int(y1*n))

EXTRA_TILE_MODULES = {'landcover':'national_landcover','trails':'national_trails','recreation':'national_recreation'}
def extra_module(name):
    import importlib
    return importlib.import_module(EXTRA_TILE_MODULES[name])

def valid_tile(z, x, y, tileset='osm'):
    if coverage_policy.enforced() and tileset!='osm' and not coverage_policy.allowed(tileset,z,x,y):return False
    if tileset not in ('osm', 'contours', 'amenities', 'boundaries', 'waterways', 'dem', *EXTRA_TILE_MODULES):
        return False
    if tileset=='dem':return MODE=='national' and 3<=z<=13 and 0<=x<2**z and 0<=y<2**z
    if tileset=='contours' and MODE=='national':return False
    minimum = 6 if tileset == 'waterways' else 8 if tileset == 'boundaries' else 10 if tileset == 'amenities' else 11 if tileset == 'contours' else (0 if MODE == 'national' else 6)
    if tileset in EXTRA_TILE_MODULES:
        minimum = extra_module(tileset).MIN_ZOOM
    if not minimum <= z <= 14 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        return False
    x0, y0, x1, y1 = tile_range(z)
    return x0 <= x <= x1 and y0 <= y <= y1

def connect():
    return sqlite3.connect(DB)

@lru_cache(maxsize=4)
def _read_contour_info(path, modified_ns, size):
    with sqlite3.connect(path) as con:
        return json.loads(con.execute("SELECT value FROM metadata WHERE key='info'").fetchone()[0])

def contour_metadata():
    if not CONTOURS_DB.exists():
        return {'status': 'not-ready', 'intervalFt': 20, 'indexIntervalFt': 100}
    stat = CONTOURS_DB.stat()
    info = _read_contour_info(str(CONTOURS_DB), stat.st_mtime_ns, stat.st_size)
    return {key: info[key] for key in ('status','sourceHash','intervalFt','indexIntervalFt','sourceResolution','verticalDatum','elevationUnit','source','featureCount','chunks') if key in info}

def metadata():
    if MODE == 'national':
        from national_basemap import DATASET_ID as osm_id
        from national_dem import DATASET_ID as dem_id, ATTRIBUTION as dem_attribution
        from national_amenities import DATASET_ID as amenity_id
        from national_boundaries import DATASET_ID as boundary_id
        from national_waterways import DATASET_ID as waterway_id
        bounds = [-180,-85.05112878,180,85.05112878]
        result = {**META,'name':'United States','bounds':bounds,'center':[-98.5,39.5],'initialZoom':3,'minZoom':0,'datasetId':osm_id,
          'tileUrl':'/tiles/{z}/{x}/{y}.pbf?datasetId='+osm_id,'source':'Protomaps OSM vector archive',
          'description':'On-demand vector basemap and raw elevation samples for contours and relief generated on the device.',
          'attribution':'© OpenStreetMap contributors · Protomaps · Natural Earth · Elevation: USGS 3DEP'}
        result['tilesets']={'osm':{key:result[key] for key in ('datasetId','tileUrl','batchUrl','batchSize','minZoom','maxZoom','bounds')},
          'dem':{'datasetId':dem_id,'tileUrl':'/dem/{z}/{x}/{y}.png?datasetId='+dem_id,'batchUrl':'/dem-batch','batchSize':8,'minZoom':3,'maxZoom':13,'bounds':[-180,-85.05112878,180,85.05112878],'format':'png','encoding':'terrarium','tileSize':512,'halo':1,'attribution':dem_attribution}}
        result['tilesets']['amenities']={'datasetId':amenity_id,'tileUrl':'/amenities/{z}/{x}/{y}.pbf?datasetId='+amenity_id,'batchUrl':'/amenity-batch','batchSize':8,'minZoom':10,'maxZoom':14,'bounds':[-180,18,180,72]}
        result['tilesets']['waterways']={'datasetId':waterway_id,'tileUrl':'/waterways/{z}/{x}/{y}.pbf?datasetId='+waterway_id,'batchUrl':'/waterway-batch','batchSize':8,'minZoom':6,'maxZoom':14,'bounds':[-180,18,180,72]}
        result['tilesets']['boundaries']={'datasetId':boundary_id,'tileUrl':'/boundaries/{z}/{x}/{y}.pbf?datasetId='+boundary_id,'batchUrl':'/boundary-batch','batchSize':8,'minZoom':8,'maxZoom':14,'bounds':[-180,18,180,72]}
        for name in EXTRA_TILE_MODULES:
            module=extra_module(name)
            result['tilesets'][name]={'datasetId':module.DATASET_ID,'tileUrl':f'/{name}/{{z}}/{{x}}/{{y}}.pbf?datasetId='+module.DATASET_ID,'batchUrl':f'/{name}-batch','batchSize':8,'minZoom':module.MIN_ZOOM,'maxZoom':module.MAX_ZOOM,'bounds':list(module.BOUNDS)}
        if coverage_policy.enforced():
            result['name']='World overview · CONUS detail'
            result['coveragePolicy']={'worldMaxZoom':7,'detailBounds':[-125,24,-66,50],'detailRegion':'CONUS','demMaxZoom':13}
            for source,spec in result['tilesets'].items():
                if source!='osm':spec['bounds']=[-125,24,-66,50]

        result['contours']={'status':'on-device','intervalFt':20,'indexIntervalFt':100,'source':'USGS 3DEP','sourceResolution':'Approximately 10 m where available, with coarser DEM fallback recorded in provenance'}
        return result
    result = dict(META)
    if DB.exists():
        with connect() as con:
            dataset = 'maryland-'+con.execute("SELECT value FROM metadata WHERE key='sourceSha256'").fetchone()[0][:12]+'-'+STYLE_VERSION
    else:
        dataset = 'maryland-pending'
    contours = contour_metadata()
    result['contours'] = contours
    result['datasetId'] = dataset
    result['tileUrl'] = '/tiles/{z}/{x}/{y}.pbf?datasetId=' + result['datasetId']
    result['tilesets'] = {'osm': {key:result[key] for key in ('datasetId','tileUrl','batchUrl','batchSize','minZoom','maxZoom','bounds')}}
    if contours['status'] == 'ready':
        contour_id = 'maryland-contours-' + contours['sourceHash'][:12] + '-' + CONTOUR_STYLE_VERSION
        result['tilesets']['contours'] = {'datasetId':contour_id,'tileUrl':'/contours/{z}/{x}/{y}.pbf?datasetId='+contour_id,'batchUrl':'/contour-batch','batchSize':8,'minZoom':11,'maxZoom':14,'bounds':list(BOUNDS)}
        result['description'] = 'Vector maps with 20-foot elevation contours and 100-foot index lines, derived from USGS 3DEP approximately 10 m DEMs.'
        result['attribution'] += ' · Elevation: USGS 3DEP (NAVD88)'
    return result

def download():
    DATA.mkdir(parents=True, exist_ok=True)
    download_boundary()
    target = DATA / 'maryland.osm.pbf'
    if target.exists():
        print('Using existing source:', target, flush=True)
        return target
    print('Downloading OSM source from', SOURCE_URL, flush=True)
    req = Request(SOURCE_URL, headers={'User-Agent': 'topo-map-server/0.2 local OSM vector renderer'})
    with urlopen(req, timeout=180) as response, open(target.with_suffix('.part'), 'wb') as out:
        while chunk := response.read(1024*1024):
            out.write(chunk)
    target.with_suffix('.part').replace(target)
    return target

def minimum_zoom(kind, subtype):
    if kind == 'building':
        return 14
    if kind == 'label':
        return {'city':6,'town':8,'village':10,'hamlet':12,'suburb':12}.get(subtype,13)
    if kind == 'road':
        return 6 if subtype in ('motorway','trunk') else 8 if subtype in ('primary','secondary','motorway_link','trunk_link') else 10 if subtype in ('tertiary','primary_link','secondary_link') else 12 if subtype in ('residential','unclassified','living_street','tertiary_link') else 14
    return {'land':6,'water':6,'forest':8,'grass':10,'residential':10,'rock':10,'waterline':10,'rail':10}.get(kind,12)

def download_boundary():
    path = DATA / 'maryland.poly'
    if not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        with urlopen('https://download.geofabrik.de/north-america/us/maryland.poly', timeout=60) as response:
            path.write_bytes(response.read())
    return path

def extract_boundary():
    # Osmosis polygon format: named outer rings and optional ! inner rings.
    rings, holes, current = [], [], []
    interior = False
    lines = (DATA / 'maryland.poly').read_text().splitlines()[1:]
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'END':
            if current:
                (holes if interior else rings).append(Polygon(current))
                current = []
        elif len(parts) == 2:
            current.append(project(float(parts[0]), float(parts[1])))
        else:
            interior = parts[0].startswith('!')
    extent = unary_union(rings)
    return extent.difference(unary_union(holes)) if holes else extent

def build_coastal_water(coasts):
    """Polygonize directed OSM coastline: water is on the right of the way."""
    if not coasts:
        return []
    x0,y0 = project(BOUNDS[0],BOUNDS[3])
    x1,y1 = project(BOUNDS[2],BOUNDS[1])
    extent = extract_boundary().intersection(box(x0,y0,x1,y1))
    segments = []
    clipped = []
    for coords in coasts:
        line = LineString(coords)
        piece = line.intersection(extent)
        if not piece.is_empty:
            clipped.append(piece)
        for a,b in zip(coords,coords[1:]):
            if a != b:
                segments.append(LineString([a,b]))
    tree = STRtree(segments)
    waters = []
    for poly in polygonize(unary_union([extent.boundary,*clipped])):
        probe = poly.representative_point()
        nearest = segments[tree.nearest(probe)]
        a,b = list(nearest.coords)
        # Normalized Mercator y points south, reversing the Cartesian orientation.
        cross = (b[0]-a[0])*(probe.y-a[1]) - (b[1]-a[1])*(probe.x-a[0])
        if cross > 0:
            waters.append(poly)
    return waters

def import_source(source):
    import osmium
    download_boundary()
    DATA.mkdir(parents=True, exist_ok=True)
    temporary = DATA / 'maryland.build.sqlite'
    temporary.unlink(missing_ok=True)
    con = sqlite3.connect(temporary)
    con.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; CREATE TABLE features (id INTEGER PRIMARY KEY, kind TEXT, subtype TEXT, name TEXT, minzoom INTEGER, area REAL, geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);')
    count = 0
    def add(kind, subtype, name, geometry):
        nonlocal count
        if geometry.is_empty:
            return
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        if geometry.is_empty:
            return
        minx,miny,maxx,maxy = geometry.bounds
        cur = con.execute('INSERT INTO features(kind,subtype,name,minzoom,area,geometry) VALUES (?,?,?,?,?,?)', (kind,subtype,name,minimum_zoom(kind,subtype),geometry.area,geometry.wkb))
        con.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid,minx,maxx,miny,maxy))
        count += 1
        if count % 100000 == 0:
            print(f'Imported {count:,} features...',flush=True)
    coasts = []
    class Importer(osmium.SimpleHandler):
        def node(self, n):
            place = n.tags.get('place')
            if place in ('city','town','village','hamlet','suburb') and n.tags.get('name'):
                add('label',place,n.tags['name'],Point(project(n.location.lon,n.location.lat)))
        def way(self, w):
            highway, waterway, railway = w.tags.get('highway'), w.tags.get('waterway'), w.tags.get('railway')
            coastline = w.tags.get('natural') == 'coastline'
            kind = 'road' if highway else 'waterline' if waterway else 'rail' if railway == 'rail' else None
            if kind or coastline:
                pts = [project(n.lon,n.lat) for n in w.nodes if n.location.valid()]
                if len(pts)<2:
                    return
                if coastline:
                    coasts.append(pts)
                if kind:
                    add(kind,highway or waterway or railway,w.tags.get('name',''),LineString(pts))
        def area(self, a):
            natural, landuse, leisure = a.tags.get('natural'), a.tags.get('landuse'), a.tags.get('leisure')
            kind = 'building' if a.tags.get('building') else 'water' if natural == 'water' or landuse == 'reservoir' or a.tags.get('waterway') == 'riverbank' else 'forest' if natural == 'wood' or landuse == 'forest' else 'grass' if landuse in ('grass','meadow','farmland','orchard','vineyard') or natural in ('grassland','scrub') or leisure in ('park','garden','golf_course','pitch') else 'residential' if landuse in ('residential','commercial','industrial') else 'rock' if natural in ('bare_rock','scree') else None
            if not kind:
                return
            for outer in a.outer_rings():
                shell = [project(n.lon,n.lat) for n in outer if n.location.valid()]
                holes = [[project(n.lon,n.lat) for n in inner if n.location.valid()] for inner in a.inner_rings(outer)]
                if len(shell)>=4:
                    add(kind,landuse or natural or leisure or '',a.tags.get('name',''),Polygon(shell,[ring for ring in holes if len(ring)>=4]))
    Importer().apply_file(str(source), locations=True, idx='flex_mem')
    print(f'Assembling water from {len(coasts)} coastline ways...',flush=True)
    (DATA/'coastlines.json').write_text(json.dumps(coasts,separators=(',',':')))
    waters = build_coastal_water(coasts)
    x0,y0 = project(BOUNDS[0],BOUNDS[3])
    x1,y1 = project(BOUNDS[2],BOUNDS[1])
    add('land','background','',box(x0,y0,x1,y1))
    for poly in waters:
        add('water','coastal','',poly)
    digest = hashlib.file_digest(open(source,'rb'),'sha256').hexdigest()
    con.execute('INSERT INTO metadata VALUES (?,?)', ('sourceSha256',digest))
    con.execute('CREATE INDEX feature_zoom ON features(minzoom)')
    con.commit()
    con.close()
    temporary.replace(DB)
    print(f'Imported {count:,} features and {len(waters)} coastal water polygons; SHA256 {digest}', flush=True)
    return count

@lru_cache(maxsize=8)
def simplified_large_geometry(wkb, tolerance):
    # Source bytes are part of the key, so replacing the database cannot reuse stale shapes.
    return from_wkb(wkb).simplify(tolerance, preserve_topology=True)

def render_tile(z, x, y):
    if MODE == 'national':
        from national_basemap import render_tile as render
        return render(z,x,y)
    n = 2**z
    bounds = (x/n,y/n,(x+1)/n,(y+1)/n)
    # Eight-pixel buffer avoids clipped line ends and gives symbol placement context.
    padding = 8/256/n
    clip = box(bounds[0]-padding,bounds[1]-padding,bounds[2]+padding,bounds[3]+padding)
    resolution = 1/n/4096
    min_area = (1/n/256)**2 * .5
    layers = {name:[] for name in LAYERS}
    with connect() as con:
        rows = con.execute('SELECT id,kind,subtype,name,geometry FROM features JOIN spatial USING(id) WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=? AND minzoom<=? AND (area=0 OR area>=?)', (bounds[2]+padding,bounds[0]-padding,bounds[3]+padding,bounds[1]-padding,z,min_area))
        for ident,kind,subtype,name,wkb in rows:
            if 1024*1024 <= len(wkb) <= 8*1024*1024:
                geometry = simplified_large_geometry(wkb, resolution*1.5)
            else:
                geometry = from_wkb(wkb).simplify(resolution*1.5, preserve_topology=True)
            geometry = geometry.intersection(clip)
            if geometry.is_empty:
                continue
            # Clipping may yield mixed dimensions for invalid/repaired polygons.
            pieces = list(geometry.geoms) if geometry.geom_type == 'GeometryCollection' else [geometry]
            for piece in pieces:
                if kind in POLYGON_LAYERS and piece.geom_type not in ('Polygon','MultiPolygon'):
                    continue
                if kind in ('road','waterline','rail') and piece.geom_type not in ('LineString','MultiLineString'):
                    continue
                layers[kind].append({'id':ident,'geometry':piece,'properties':{'class':subtype,'name':name}})
    return mapbox_vector_tile.encode([{'name':name,'features':features} for name,features in layers.items()],default_options={'quantize_bounds':bounds,'extents':4096,'y_coord_down':True})

def render_waterway_tile(z,x,y):
    from national_waterways import render_tile
    return render_tile(z,x,y)

def render_boundary_tile(z,x,y):
    from national_boundaries import render_tile
    return render_tile(z,x,y)

def render_amenity_tile(z,x,y):
    from national_amenities import render_tile
    return render_tile(z,x,y)

def render_contour_tile(z, x, y):
    if MODE == 'national':
        from national_contours import render_tile as render, CoverageUnavailable, atomic_json, CACHE, DATASET_ID
        try:
            return render(z,x,y)
        except CoverageUnavailable:
            # A documented absence of DEM samples over open water is a valid empty overlay.
            # Missing terrain over land stays an error and must never poison the tile cache.
            from national_basemap import render_tile as basemap
            from shapely.geometry import shape
            layers = mapbox_vector_tile.decode(basemap(z,x,y))
            land = layers.get('land',{}).get('features',[])
            if any(shape(f['geometry']).intersection(box(0,0,4096,4096)).area > 0 for f in land):
                raise
            atomic_json(CACHE/'tiles'/str(z)/str(x)/(str(y)+'.json'),{'datasetId':DATASET_ID,'tile':[z,x,y],'coverageStatus':'open-water','reason':'No DEM samples and no land in the basemap tile'})
            return mapbox_vector_tile.encode([{'name':'contour','features':[]}])
    n = 2**z
    bounds = (x/n,y/n,(x+1)/n,(y+1)/n)
    padding = 8/256/n
    clip = box(bounds[0]-padding,bounds[1]-padding,bounds[2]+padding,bounds[3]+padding)
    resolution = 1/n/4096
    features = []
    if z >= 11 and CONTOURS_DB.exists():
        with sqlite3.connect(CONTOURS_DB) as con:
            contours = con.execute('SELECT id,ele_ft,is_index,geometry FROM contours JOIN spatial USING(id) WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=? AND (is_index=1 OR ? >=13)', (bounds[2]+padding,bounds[0]-padding,bounds[3]+padding,bounds[1]-padding,z))
            for ident, feet, is_index, wkb in contours:
                geometry = from_wkb(wkb).simplify(resolution*1.5, preserve_topology=True).intersection(clip)
                if geometry.is_empty or geometry.geom_type not in ('LineString','MultiLineString'):
                    continue
                features.append({'id':ident,'geometry':geometry,'properties':{'ele_ft':feet,'index':bool(is_index),'name':f'{feet} ft'}})
    return mapbox_vector_tile.encode([{'name':'contour','features':features}],default_options={'quantize_bounds':bounds,'extents':4096,'y_coord_down':True})

class RenderGate:
    """Bound CPU-heavy work; queued interactive requests precede download batches."""
    def __init__(self, limit=2):
        self.limit = limit
        self.active = 0
        self.interactive_waiters = 0
        self.condition = threading.Condition()

    @contextmanager
    def slot(self, batch=False, background=False):
        with self.condition:
            if not batch:
                self.interactive_waiters += 1
            try:
                self.condition.wait_for(lambda: self.active < (max(1,self.limit-1) if batch or background else self.limit) and (not batch or self.interactive_waiters == 0))
                self.active += 1
            finally:
                if not batch:
                    self.interactive_waiters -= 1
        try:
            yield
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()

_viewport_warmer = None
_render_pool = None  # Created only by the CLI serving entry point, never while importing.
_render_gate = RenderGate(max(1, int(os.environ.get('TILE_RENDER_CONCURRENCY', '2'))))
_waterway_gate = RenderGate(2)
_boundary_gate = RenderGate(2)
_amenity_gate = RenderGate(2)
_dem_gate = RenderGate(2)
_extra_gates = {name:RenderGate(2) for name in EXTRA_TILE_MODULES}
_tile_locks = weakref.WeakValueDictionary()
_tile_locks_guard = threading.Lock()
def tile_lock(key):
    # Unrelated cold tiles must not block one another through striped-lock collisions.
    with _tile_locks_guard:
        lock = _tile_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _tile_locks[key] = lock
        return lock
def tile_bytes(z,x,y, *, batch=False, dataset_id=None, tileset='osm', background=False):
    if not valid_tile(z,x,y,tileset):
        raise ValueError('Tile outside Maryland coverage or tileset zoom range')
    if coverage_policy.enforced() and tileset=='osm' and not coverage_policy.allowed('osm',z,x,y):
        parent=tile_bytes(7,x>>(z-7),y>>(z-7),batch=batch,dataset_id=dataset_id,background=background)
        return coverage_policy.overzoom(parent,z,x,y)
    spec = metadata()['tilesets'].get(tileset)
    if spec is None:
        raise RuntimeError('Requested tileset is not ready')
    renderer = render_waterway_tile if tileset == 'waterways' else render_boundary_tile if tileset == 'boundaries' else render_amenity_tile if tileset == 'amenities' else render_contour_tile if tileset == 'contours' else render_tile
    if tileset=='dem':
        from national_dem import render_tile as renderer
    if tileset in EXTRA_TILE_MODULES:
        renderer = extra_module(tileset).render_tile
    path = DATA / 'cache' / (dataset_id or spec['datasetId']) / str(z) / str(x) / f'{y}.pbf'
    # Cache reads bypass scheduling. A queued download must never hold a tile
    # lock while waiting for its lower-priority render slot.
    remote=object_cache.current()
    key=remote.key(spec['datasetId'],z,x,y,tileset) if remote else None
    if remote is None and path.exists():return path.read_bytes()
    if remote:
        cached=remote.local_get(key,path)
        if cached is not None:return cached
    gate = _extra_gates.get(tileset) or {'dem':_dem_gate,'waterways':_waterway_gate,'boundaries':_boundary_gate,'amenities':_amenity_gate}.get(tileset,_render_gate)
    with gate.slot(batch=batch,background=background), tile_lock(str(path)):
        if remote:
            cached=remote.get(key,path)
            if cached is not None:return cached
        elif path.exists():return path.read_bytes()
        access_control.generation()
        minimum = float(os.environ.get('TILE_MIN_FREE_GB', '0')) * 10**9
        if minimum and shutil.disk_usage(DATA).free < minimum:
            raise RuntimeError('Tile cache disk reserve reached')
        blob = _render_pool.submit(renderer,z,x,y).result() if tileset in ('osm','contours') and _render_pool is not None else renderer(z,x,y)
        if remote:
            remote.put(key,path,blob,tileset)
            return blob
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as temp:
            temp.write(blob)
        Path(temp.name).replace(path)
        return blob

def accepts_gzip(value):
    for encoding in value.lower().split(','):
        parts = [part.strip() for part in encoding.split(';')]
        if parts[0] == 'gzip':
            try:
                return all(float(part[2:]) > 0 for part in parts[1:] if part.startswith('q='))
            except ValueError:
                return False
    return False

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    disable_nagle_algorithm = True

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def respond(self,status,body,content_type='application/json',cache='no-cache'):
        compressed = len(body) > 256 and accepts_gzip(self.headers.get('Accept-Encoding', ''))
        if compressed:
            body = gzip.compress(body, compresslevel=4, mtime=0)
        access=access_control.current()
        if access and getattr(self,'authorized',False):
            try:access.charge('download_bytes',len(body)+1024)
            except access_control.Denied as exc:
                status=exc.status;body=json.dumps({'error':str(exc)}).encode();compressed=False
                content_type='application/json'
            cache='private, no-store'
        self.send_response(status)
        if status==429:self.send_header('Retry-After','60')
        if status==401:self.send_header('WWW-Authenticate','Bearer')
        if compressed:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Vary', 'Accept-Encoding')
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Cache-Control',cache)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Content-Length', '0')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods','GET, HEAD, OPTIONS')
        self.end_headers()
    def do_HEAD(self):
        self.do_GET()
    def do_batch(self, tileset='osm'):
        try:
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=4)
            if set(query) != {'datasetId', 'tiles'} or any(len(value) != 1 for value in query.values()):
                raise ValueError('Exactly one datasetId and tiles parameter are required')
            meta = metadata()
            spec = meta.get('tilesets', {}).get(tileset, meta if tileset == 'osm' else None)
            if spec is None:
                return self.respond(503, b'{"error":"Requested tileset is not ready"}')
            dataset_id = spec['datasetId']
            if query['datasetId'][0] != dataset_id:
                return self.respond(409, json.dumps({'error': 'Dataset changed; refresh metadata', 'datasetId': dataset_id}).encode())
            keys = query['tiles'][0].split(',')
            if not 1 <= len(keys) <= 8 or len(set(keys)) != len(keys):
                raise ValueError('Request 1–8 distinct tile keys')
            coordinates = []
            for key in keys:
                if not re.fullmatch(r'(?:0|[1-9]\d?)/(?:0|[1-9]\d{0,6})/(?:0|[1-9]\d{0,6})', key):
                    raise ValueError('Malformed tile key: ' + key[:60])
                coords = tuple(map(int, key.split('/')))
                if not valid_tile(*coords, tileset=tileset):
                    raise ValueError('Tile outside Maryland coverage or zoom range: ' + key)
                coordinates.append(coords)
        except ValueError as exc:
            return self.respond(400, json.dumps({'error': str(exc)}).encode())
        result = {'datasetId': dataset_id, 'tiles': [], 'errors': []}
        # A batch uses one rendering slot at a time; cached tiles never enter the gate.
        for key, coords in zip(keys, coordinates):
            try:
                blob = tile_bytes(*coords, batch=True, dataset_id=dataset_id, tileset=tileset)
                result['tiles'].append({'key': key, 'data': base64.b64encode(blob).decode('ascii')})
            except access_control.Denied:raise
            except Exception as exc:
                print('Batch tile error:', key, exc, flush=True)
                result['errors'].append({'key': key, 'error': 'Tile generation failed; retry this key'})
        return self.respond(200, json.dumps(result, separators=(',', ':')).encode(), cache='no-store')

    def do_GET(self):
        self.authorized=False
        access=access_control.current()
        if access is None or self.path.split('?')[0]=='/health':return self.route_get()
        try:
            with access.request(self.headers.get('Authorization','')) as role:
                self.authorized=True
                if self.path.startswith('/jobs/') and role!='warm':
                    return self.respond(403,b'{"error":"Operator access required"}')
                return self.route_get()
        except access_control.Denied as exc:
            self.authorized=False
            return self.respond(exc.status,json.dumps({'error':str(exc)}).encode(),cache='private, no-store')
        except Exception as exc:
            print('Protected request failed:',type(exc).__name__,flush=True)
            self.authorized=False
            return self.respond(503,b'{"error":"Map service unavailable"}',cache='private, no-store')
    def route_get(self):
        path = self.path.split('?')[0]
        if path=='/usage':
            access=access_control.current()
            return self.respond(200,json.dumps(access.status() if access else {'status':'unrestricted-local'}).encode())
        if path=='/dem-batch':return self.do_batch('dem')
        if path in {f'/{name}-batch' for name in EXTRA_TILE_MODULES}:
            return self.do_batch(path[1:-6])
        if path in ('/tile-batch', '/contour-batch', '/amenity-batch', '/boundary-batch', '/waterway-batch'):
            return self.do_batch('waterways' if path == '/waterway-batch' else 'boundaries' if path == '/boundary-batch' else 'amenities' if path == '/amenity-batch' else 'contours' if path == '/contour-batch' else 'osm')
        if path == '/jobs/viewport':
            return self.respond(200,json.dumps(_viewport_warmer.status() if _viewport_warmer else {'status':'disabled'}).encode())
        if path == '/jobs/california':
            job = DATA/'jobs'/'california-status.json'
            return self.respond(200,job.read_bytes() if job.exists() else b'{"status":"not-started"}')
        if path in ('/areas','/areas.geojson'):
            from areas import area_bytes
            try:
                return self.respond(200,area_bytes(path.endswith('.geojson')),cache='public, max-age=3600')
            except FileNotFoundError:
                return self.respond(503,b'{"error":"Area directory is not installed"}')
        if path == '/health':
            ready = MODE == 'national' or DB.exists()
            return self.respond(200 if ready else 503,json.dumps({'status':'ok' if ready else 'not-ready','mode':MODE,'database':DB.exists(),'format':'pbf'}).encode())
        if path == '/metadata':
            return self.respond(200,json.dumps(metadata()).encode())
        match = re.fullmatch(r'/(tiles|contours|amenities|boundaries|waterways|landcover|trails|recreation|dem)/(\d{1,2})/(\d{1,7})/(\d{1,7})\.(?:pbf|png)',path)
        if match:
            tileset = match.group(1) if match.group(1) in (*EXTRA_TILE_MODULES,'dem') else 'waterways' if match.group(1) == 'waterways' else 'boundaries' if match.group(1) == 'boundaries' else 'amenities' if match.group(1) == 'amenities' else 'contours' if match.group(1) == 'contours' else 'osm'
            meta = metadata()
            spec = meta.get('tilesets', {}).get(tileset, meta if tileset == 'osm' else None)
            if spec is None:
                return self.respond(503, b'{"error":"Requested tileset is not ready"}')
            try:
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=4)
            except ValueError as exc:
                return self.respond(400, json.dumps({'error':str(exc)}).encode())
            if 'datasetId' in query:
                current = spec['datasetId']
                if query['datasetId'] != [current]:
                    return self.respond(409, json.dumps({'error':'Dataset changed; refresh metadata','datasetId':current}).encode())
            try:
                coords = tuple(map(int,match.groups()[1:]))
                with _viewport_warmer.foreground() if _viewport_warmer else nullcontext():
                    body = tile_bytes(*coords, tileset=tileset)
                if _viewport_warmer:
                    _viewport_warmer.observe(*coords)
            except access_control.Denied:raise
            except ValueError as exc:
                return self.respond(404,json.dumps({'error':str(exc)}).encode())
            except Exception as exc:
                print('Tile error:',exc,flush=True)
                return self.respond(503,b'{"error":"Vector tile renderer unavailable"}')
            return self.respond(200,body,'image/png' if tileset=='dem' else 'application/vnd.mapbox-vector-tile','public, max-age=3600')
        self.respond(404,b'{"error":"Not found"}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','serve','warm'])
    parser.add_argument('--mode',choices=['national','regional'],default=os.environ.get('TILE_MODE','national'))
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','3001')))
    parser.add_argument('--source',type=Path)
    parser.add_argument('--tileset',choices=['osm','dem','contours','amenities','boundaries','waterways',*EXTRA_TILE_MODULES],default='osm')
    parser.add_argument('--min-zoom',type=int,default=6)
    parser.add_argument('--max-zoom',type=int,default=8)
    args = parser.parse_args()
    MODE = args.mode
    os.environ['TILE_MODE'] = MODE
    if args.command == 'prepare':
        import_source(args.source or download())
    elif args.command == 'warm':
        count = 0
        for z in range(args.min_zoom,args.max_zoom+1):
            x0,y0,x1,y1 = tile_range(z)
            for x in range(x0,x1+1):
                for y in range(y0,y1+1):
                    tile_bytes(z,x,y,tileset=args.tileset)
                    count += 1
        print(f'Cached {count} vector tiles',flush=True)
    else:
        if MODE == 'regional' and not DB.exists():
            parser.error('Run prepare before serve')
        workers = max(0, int(os.environ.get('TILE_RENDER_WORKERS', '2')))
        if workers:
            _render_pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
        if MODE == 'national' and os.environ.get('VIEWPORT_WARMING','1') != '0':
            from viewport_warmer import ViewportWarmer
            specs = metadata()['tilesets']
            def warm_cached(key):
                source,z,x,y = key
                return (DATA/'cache'/specs[source]['datasetId']/str(z)/str(x)/f'{y}.pbf').exists()
            def warm_render(key):
                source,z,x,y = key
                tile_bytes(z,x,y,tileset=source,batch=True,background=True)
            _viewport_warmer = ViewportWarmer(warm_render,warm_cached,valid_tile)
            _viewport_warmer.start()
        access_control.current()
        if access_control.current():access_control.current().config()
        object_cache.current()
        import scratch_cache
        scratch_cache.start(DATA)
        server = ThreadingHTTPServer(('0.0.0.0',args.port),Handler)
        print(f'OSM vector tile service: http://0.0.0.0:{server.server_port} (render workers: {workers})',flush=True)
        def stop_server(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop_server)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if _viewport_warmer:
                _viewport_warmer.stop()
            server.server_close()
            if _render_pool is not None:
                _render_pool.shutdown(wait=True, cancel_futures=True)
