"""Independent hydrology overlay preserving OSM flow flags and clipping lake interiors."""
import fcntl, json, os, time
from pathlib import Path
from cache_paths import working_path
import mapbox_vector_tile
from shapely import make_valid
from shapely.geometry import shape
from shapely.affinity import scale
from shapely.ops import unary_union
from national_basemap import archive
DATASET_ID = 'osm-waterways-pm20260811-v2'
CACHE = Path(os.environ.get('TILE_DATA_DIR', Path(__file__).parent/'data'))/'national-waterways'/DATASET_ID

def osm_id(ident):
    return ident & ((1 << 44)-1) if isinstance(ident,int) and ident >> 44 == 2 else None

def stream_tags(ids):
    from national_amenities import fetch, atomic_json, URL
    CACHE.mkdir(parents=True, exist_ok=True)
    # Cached tags must remain readable while an unrelated cold query is waiting.
    # Writers replace JSON atomically, so a complete cache hit needs no writer lock.
    cached={}
    for ident in sorted(set(ids)):
        path=working_path(CACHE/'ways'/str(ident//100000)/(str(ident)+'.json'))
        if not path.exists():break
        cached[ident]=json.loads(path.read_text())['tags']
    else:return cached
    # One enrichment writer avoids duplicate queries for shared ways across zooms.
    with (CACHE/'enrich.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = {}
        missing = []
        for ident in sorted(set(ids)):
            path=working_path(CACHE/'ways'/str(ident//100000)/(str(ident)+'.json'))
            if path.exists(): result[ident]=json.loads(path.read_text())['tags']
            else: missing.append(ident)
        for start in range(0,len(missing),200):
            batch=missing[start:start+200]
            data=fetch('[out:json][timeout:45];way(id:'+','.join(map(str,batch))+');out tags;')
            found={e['id']:e.get('tags',{}) for e in data['elements'] if e.get('type')=='way'}
            for ident in batch:
                tags=found.get(ident,{})
                # Missing/deleted objects are explicitly unknown, never perennial.
                atomic_json(working_path(CACHE/'ways'/str(ident//100000)/(str(ident)+'.json')),{'tags':tags,'found':ident in found,'source':data.get('_endpoint',URL),'osm_timestamp':data.get('osm3s',{}).get('timestamp_osm_base'),'retrieved':time.time()})
                result[ident]=tags
        return result

def active(value):
    return value is not None and str(value).strip().lower() not in ('', 'no', 'false', '0', 'none')

def flow_properties(props):
    intermittent = active(props.get('intermittent'))
    seasonal = active(props.get('seasonal'))
    result = {'intermittent': intermittent, 'seasonal': seasonal,
              'flow': 'seasonal' if seasonal else 'intermittent' if intermittent else 'perennial' if props.get('intermittent') in (False,'no','false',0) or props.get('seasonal') in (False,'no','false',0) else 'unknown'}
    if seasonal:
        result['seasonal_value'] = str(props['seasonal'])
    return result

def normalize_tile(blob, z, tags_by_id=None):
    layer = mapbox_vector_tile.decode(blob, default_options={'y_coord_down': True}).get('water', {}) if blob else {}
    factor = 4096 / layer.get('extent', 4096)
    polygons, lines = [], []
    for feature in layer.get('features', []):
        geometry = shape(feature['geometry'])
        if factor != 1:
            geometry = scale(geometry, xfact=factor, yfact=factor, origin=(0, 0))
        if geometry.geom_type in ('Polygon', 'MultiPolygon'):
            polygons.append(make_valid(geometry))
        elif geometry.geom_type in ('LineString', 'MultiLineString'):
            props = feature.get('properties', {})
            if isinstance(props.get('min_zoom'), (int, float)) and props['min_zoom'] > z + 1:
                continue
            lines.append((feature, geometry))
    water = unary_union(polygons) if polygons else None
    features = []
    for original, geometry in lines:
        if water is not None:
            geometry = geometry.difference(water)
        if geometry.geom_type == 'GeometryCollection':
            geometry = unary_union([g for g in geometry.geoms if g.geom_type in ('LineString', 'MultiLineString')])
        if geometry.is_empty or geometry.geom_type not in ('LineString', 'MultiLineString'):
            continue
        props = dict(original.get('properties', {}))
        ident = osm_id(original.get('id'))
        if tags_by_id is not None and ident in tags_by_id:
            tags=tags_by_id[ident]
            # Geometry/name remain from the pinned archive; current tags only
            # enrich flow when the original object is still a waterway.
            if tags.get('waterway') in ('stream','river','canal','ditch','drain'):
                props.update({key:tags[key] for key in ('intermittent','seasonal') if key in tags})
        output = {'class': props.get('kind_detail') or props.get('kind') or 'stream',
                  'name': str(props.get('name:en') or props.get('name') or props.get('name_en') or ''), **flow_properties(props)}
        features.append({'id': original.get('id', 0), 'geometry': geometry, 'properties': output})
    return mapbox_vector_tile.encode([{'name': 'waterline', 'features': features}], default_options={'extents': 4096, 'y_coord_down': True})

def render_tile(z, x, y):
    if not 6 <= z <= 14 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise ValueError('Waterways accept valid XYZ tiles at zooms 6–14')
    blob=archive().get(z,x,y)
    features=mapbox_vector_tile.decode(blob).get('water',{}).get('features',[]) if blob else []
    ids=[osm_id(f.get('id')) for f in features if 'Line' in f['geometry']['type']]
    tags=stream_tags([ident for ident in ids if ident is not None]) if any(ident is not None for ident in ids) else {}
    return normalize_tile(blob, z, tags)
