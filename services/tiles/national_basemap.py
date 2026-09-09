"""Pinned Protomaps PMTiles -> local range extraction -> app-compatible OSM MVT.

Only the server reads archive HTTP ranges; clients never hotlink a public tile API.
Requested archive blocks persist locally and normalized tiles use the server cache.
See https://docs.protomaps.com/basemaps/downloads for extraction and attribution.
"""
from functools import lru_cache
import fcntl
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
from cache_paths import working_path
import re
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import mapbox_vector_tile
from pmtiles.tile import Compression, TileType, deserialize_header, deserialize_directory, find_tile, zxy_to_tileid
from shapely.geometry import shape, Point, box
from shapely.ops import unary_union
from shapely.affinity import scale, translate

PINNED_URL = 'https://build.protomaps.com/20260811.pmtiles'
PINNED_SIZE = 137295889397
PINNED_BLAKE3 = 'b2aa7f4b1858ec873bd2fb6aff1393ce330ad4d236f2b4f9ad1875e910c1eb8e'
PINNED_ETAG = '"e4343a15fa4bf60f81112ba7784a3f73-512"'
SOURCE_URL = os.environ.get('NATIONAL_PMTILES_URL', PINNED_URL)
DATASET_ID = 'osm-us-pm20260811-b2aa7f4b1858-v9'
SOURCE_INFO = {'provider':'Protomaps','source':'OpenStreetMap and Natural Earth via Protomaps v4 basemap','snapshot':'2026-08-11','version':'4.15.1','url':PINNED_URL,'blake3':PINNED_BLAKE3,'archiveBytes':PINNED_SIZE,'etag':PINNED_ETAG,'attribution':'© OpenStreetMap contributors · Protomaps · Natural Earth','license':'ODbL Produced Work; OpenStreetMap attribution required','schemaVersion':'national-osm-v9','documentation':'https://docs.protomaps.com/basemaps/downloads'}
DATA = Path(os.environ.get('TILE_DATA_DIR',Path(__file__).resolve().parent/'data'))
LAYERS = ('land','residential','grass','forest','rock','water','waterline','building','rail','road','label','water_label','poi','area')
BLOCK_SIZE = 256*1024
MAX_READ = 16*1024*1024
USER_AGENT = 'topo-map-server/0.3'


class RangeSource:
    """Durable aligned archive block cache; RAM capped at 32 blocks (~8 MiB)."""
    def __init__(self,url=SOURCE_URL,cache_dir=None,block_size=BLOCK_SIZE,etag=None):
        self.url=url
        self.block_size=block_size
        self.etag=etag if etag is not None else (PINNED_ETAG if url==PINNED_URL else '')
        identity=hashlib.sha256((url+'|'+self.etag+'|'+PINNED_BLAKE3).encode()).hexdigest()[:20]
        self.cache_dir=Path(cache_dir) if cache_dir is not None else DATA/'national-basemap'/'ranges'/identity
        self.locks=[threading.Lock() for _ in range(32)]
        self.remote=url.startswith(('https://','http://'))
        self._cached_block=lru_cache(maxsize=32)(self._read_block)

    def _fetch(self,start):
        if not self.remote:
            path=Path(self.url.removeprefix('file://'))
            with path.open('rb') as stream:
                stream.seek(start)
                return stream.read(self.block_size)
        headers={'Range':f'bytes={start}-{start+self.block_size-1}','Accept-Encoding':'identity','User-Agent':USER_AGENT}
        if self.etag:
            headers['If-Match']=self.etag
        for attempt in range(3):
            try:
                with urlopen(Request(self.url,headers=headers),timeout=30) as response:
                    if response.status!=206:
                        raise ValueError('Archive server ignored HTTP Range; refusing full-file download')
                    match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                    if not match or int(match[1])!=start:
                        raise ValueError('Incorrect Content-Range in archive response')
                    end,total=int(match[2]),int(match[3])
                    if end>=start+self.block_size or end>=total:
                        raise ValueError('Invalid archive byte range')
                    if self.url==PINNED_URL and total!=PINNED_SIZE:
                        raise ValueError('Pinned archive length changed; refusing mixed snapshots')
                    actual_etag=response.headers.get('ETag','')
                    if self.etag and actual_etag and actual_etag.strip('"')!=self.etag.strip('"'):
                        raise ValueError('Pinned archive ETag changed; refresh the reviewed source manifest')
                    blob=response.read(self.block_size+1)
                    if len(blob)!=end-start+1:
                        raise IOError('Truncated archive range')
                    return blob
            except HTTPError as exc:
                if exc.code not in (408,429,500,502,503,504) or attempt==2:
                    raise
            except (URLError,TimeoutError,OSError):
                if attempt==2:
                    raise
            time.sleep(.25*2**attempt)
        raise RuntimeError('Archive range retries exhausted')

    def _read_block(self,index):
        path=working_path(self.cache_dir/f'{index:012x}.bin')
        with self.locks[index%len(self.locks)]:
            try:return path.read_bytes()
            except FileNotFoundError:pass
            path.parent.mkdir(parents=True,exist_ok=True)
            # Thread locks cover one RangeSource instance. The generation pool
            # has separate processes/instances, so cold blocks also need a shared
            # file lock. Cache hits above stay lock-free across processes.
            with path.with_suffix('.lock').open('a+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                try:return path.read_bytes()
                except FileNotFoundError:pass
                blob=self._fetch(index*self.block_size)
                if not blob:
                    raise IOError('Empty archive range')
                with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as temporary:
                    temporary.write(blob)
                Path(temporary.name).replace(path)
                return blob

    def get_bytes(self,offset,length):
        if offset<0 or not 0<=length<=MAX_READ:
            raise ValueError('Invalid or excessive PMTiles range')
        if not length:
            return b''
        first=offset//self.block_size;last=(offset+length-1)//self.block_size
        chunks=[self._cached_block(index) for index in range(first,last+1)]
        joined=b''.join(chunks)
        result=joined[offset-first*self.block_size:offset-first*self.block_size+length]
        if len(result)!=length:
            raise IOError('PMTiles range extends beyond available bytes')
        return result


class Archive:
    def __init__(self,source):
        self.source=source
        self.header=deserialize_header(source.get_bytes(0,127))
        if self.header['tile_type']!=TileType.MVT or self.header['internal_compression']!=Compression.GZIP:
            raise ValueError('Expected the pinned gzip-directory MVT PMTiles v3 archive')
        self.directory=lru_cache(maxsize=64)(self._directory)

    def _directory(self,offset,length):
        return deserialize_directory(self.source.get_bytes(offset,length))

    def get(self,z,x,y):
        tileid=zxy_to_tileid(z,x,y)
        offset=self.header['root_offset'];length=self.header['root_length']
        for _ in range(4):
            entry=find_tile(self.directory(offset,length),tileid)
            if entry is None:
                return None
            if entry.run_length:
                blob=self.source.get_bytes(self.header['tile_data_offset']+entry.offset,entry.length)
                compression=self.header['tile_compression']
                if compression==Compression.GZIP:
                    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
                        blob=stream.read(64*1024*1024+1)
                    if len(blob)>64*1024*1024:
                        raise ValueError('Decompressed vector tile exceeds memory limit')
                elif compression!=Compression.NONE:
                    raise ValueError('Unsupported source tile compression')
                return blob
            offset=self.header['leaf_directory_offset']+entry.offset;length=entry.length
        raise ValueError('PMTiles directory exceeds supported depth')


@lru_cache(maxsize=1)
def archive():
    return Archive(RangeSource())


# Explicit groups keep land-use centroids and administrative labels out of POIs.
POI_AMENITIES={
    'restaurant':'restaurant','fast_food':'restaurant','food_court':'restaurant',
    'cafe':'cafe','bar':'cafe','pub':'cafe','toilets':'toilet','toilet':'toilet',
    'drinking_water':'drinking-water','water_point':'drinking-water',
    'parking':'parking','parking_entrance':'parking','fuel':'fuel','charging_station':'fuel',
    'information':'information','visitor_centre':'information','ranger_station':'information',
    'hospital':'hospital','clinic':'hospital','doctors':'hospital','pharmacy':'pharmacy',
    'picnic_site':'picnic-site','picnic_table':'picnic-site',
    'supermarket':'shop','convenience':'shop','shop':'shop','bakery':'shop',
    'school':'marker','college':'marker','university':'marker','library':'marker',
    'bank':'marker','atm':'marker','post_office':'marker','police':'marker',
    'fire_station':'marker','shelter':'marker','place_of_worship':'marker',
}
POI_OTHER={
    'camp_site':'campsite','caravan_site':'campsite',
    'hotel':'lodging','motel':'lodging','hostel':'lodging','guest_house':'lodging','alpine_hut':'lodging',
    'peak':'mountain','volcano':'mountain','saddle':'mountain',
    'viewpoint':'viewpoint','park':'park','national_park':'park','nature_reserve':'park',
    'monument':'monument','memorial':'monument','heritage':'monument','ruins':'monument',
    'museum':'museum','beach':'swimming','swimming_pool':'swimming',
    'attraction':'marker','landmark':'marker','trailhead':'marker','marina':'marker',
}


def poi_properties(props):
    kind=props.get('kind_detail') or props.get('kind','')
    if kind not in POI_AMENITIES and kind not in POI_OTHER:
        kind=props.get('kind','')
    if kind in POI_AMENITIES:
        return {'poi_icon':POI_AMENITIES[kind],'poi_frame':'square'}
    if kind in POI_OTHER:
        return {'poi_icon':POI_OTHER[kind],'poi_frame':'circle'}
    return None


def classify(layer,properties,geometry_type):
    kind=properties.get('kind','')
    detail=properties.get('kind_detail','')
    polygon=geometry_type in ('Polygon','MultiPolygon')
    line=geometry_type in ('LineString','MultiLineString')
    point=geometry_type in ('Point','MultiPoint')
    if layer=='pois' and point and kind in ('water','lake','reservoir','basin'):
        return 'water_label',detail or kind
    if layer=='pois' and point and kind in ('park','national_park','nature_reserve','forest','protected_area'):
        return 'area',kind
    if layer=='pois' and point and poi_properties(properties):
        return 'poi',detail or kind
    if layer=='earth' and polygon:
        return 'land','earth'
    if layer=='water':
        if point and (detail in ('lake','reservoir','basin') or kind in ('water','lake')):
            return 'water_label',detail or kind
        return ('water',detail or kind) if polygon else ('waterline',detail or 'river') if line else None
    if layer=='buildings' and polygon:
        return 'building',kind or 'building'
    if layer=='roads' and line:
        if kind=='rail':
            return 'rail',detail or 'rail'
        if kind not in ('highway','major_road','minor_road','path'):
            return None
        return 'road',detail or {'highway':'motorway','major_road':'primary','minor_road':'residential','path':'path'}[kind]
    if layer=='places' and point:
        return 'label',detail or {'locality':'city','region':'state','macrohood':'suburb','neighbourhood':'suburb'}.get(kind,kind)
    if layer in ('landcover','landuse','natural') and polygon:
        if kind in ('forest','wood'):
            return 'forest',kind
        if kind in ('barren','bare_rock','sand','beach','glacier'):
            return 'rock',kind
        if kind in ('residential','commercial','industrial','urban_area','neighbourhood','school','college','university','hospital'):
            return 'residential',kind
        if kind in ('farmland','farmyard','grassland','grass','scrub','meadow','orchard','park','garden','golf_course','pitch','recreation_ground','nature_reserve','national_park','protected_area','wetland'):
            return 'grass',kind
    return None


def road_properties(props):
    result={key:props[key] for key in ('ref','network','shield_text','surface','is_bridge','is_tunnel','is_link') if key in props and isinstance(props[key],(str,bool,int,float))}
    network=str(props.get('network',''))
    text=str(props.get('shield_text','')).strip()
    # Preserve authoritative network/number pairs; unknown refs are neutral badges.
    if not text:
        text=str(props.get('ref','')).split(';')[0].strip()
    if text and len(text)<=8:
        result['shield_text']=text
        result['shield_kind']='interstate' if (network=='US:I' or network.startswith('US:I:')) else 'us' if (network=='US:US' or network.startswith('US:US:')) else 'county' if network.startswith('US:') and ('county' in network.lower() or network.count(':')>=2) else 'state' if network.startswith('US:') else 'generic'
    return result


def merge_water_labels(features):
    """Water POIs and polygon-label records may describe the same anchor.

    Keep the earliest supplied zoom and the more specific water classification.
    Equal names at distinct locations remain separate lakes.
    """
    merged={}
    for feature in features:
        props=feature['properties'];key=(props['name'].strip().casefold(),feature['geometry'].wkb)
        previous=merged.get(key)
        if previous is None:
            merged[key]=feature
            continue
        minimum=min(previous['properties']['min_zoom'],props['min_zoom'])
        if props['class']!='water':previous['properties'].update(props)
        previous['properties']['min_zoom']=minimum
    return list(merged.values())


def normalize_tile(blob,z):
    result={name:[] for name in LAYERS}
    if blob:
        decoded=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True})
        for source_name,layer in decoded.items():
            extent=layer.get('extent',4096)
            for feature in layer['features']:
                props=feature.get('properties',{})
                minimum=props.get('min_zoom')
                if isinstance(minimum,(int,float)) and minimum>z+1:
                    continue
                geometry=feature['geometry']
                destination=classify(source_name,props,geometry['type'])
                if destination is None:
                    continue
                target,subtype=destination
                name=props.get('name:en') or props.get('name') or props.get('name_en') or ''
                if target in ('label','water_label','area') and not name:
                    continue
                shape_value=shape(geometry)
                if extent!=4096:
                    shape_value=scale(shape_value,xfact=4096/extent,yfact=4096/extent,origin=(0,0))
                output={'class':subtype,'name':str(name)}
                if target=='area':
                    output.update(kind='forest' if subtype=='forest' else 'park',min_zoom=minimum if isinstance(minimum,(int,float)) else 12,priority=3,label_source='osm')
                if target=='poi':
                    output.update(poi_properties(props))
                    output['min_zoom']=minimum if isinstance(minimum,(int,float)) else 14
                if target=='road':
                    output.update(road_properties(props))
                    from cartographic_names import display_name
                    display=display_name(name)
                    if display!=name:output['display_name']=display
                if target=='water_label':
                    # Upstream uses the full polygon's point-on-surface and area-based
                    # zoom priority, avoiding new anchors on every clipped tile fragment.
                    output['min_zoom']=minimum if isinstance(minimum,(int,float)) else 6
                    output['sort_rank']=props.get('sort_rank',200)
                result[target].append({'id':len(result[target])+1,'geometry':shape_value,'properties':output})
    result['water_label']=merge_water_labels(result['water_label'])
    return mapbox_vector_tile.encode([{'name':name,'features':features} for name,features in result.items()],default_options={'extents':4096,'y_coord_down':True})


@lru_cache(maxsize=64)
def water_shapes(z,x,y):
    """Use a fixed reference zoom, independent of the displayed tile's clipping."""
    blob=archive().get(z,x,y)
    if not blob:
        return []
    layer=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True}).get('water',{})
    factor=4096/layer.get('extent',4096)
    values=[]
    for feature in layer.get('features',[]):
        if feature['geometry']['type'] not in ('Polygon','MultiPolygon'):
            continue
        value=shape(feature['geometry'])
        if not value.is_valid:
            value=value.buffer(0)
        value=translate(scale(value,xfact=factor,yfact=factor,origin=(0,0)),xoff=x*4096,yoff=y*4096)
        values.append(value)
    return values


@lru_cache(maxsize=2048)
def lake_axis(world_x,world_y,name="Lake"):
    for zoom in (10,12):
        px,py=world_x*4096*2**zoom,world_y*4096*2**zoom
        tx,ty=int(px//4096),int(py//4096)
        anchor=Point(px,py)
        candidates=[p for p in water_shapes(zoom,tx,ty) if p.covers(anchor)]
        if not candidates:
            continue
        lake=min(candidates,key=lambda p:p.area)
        # Merge adjoining fragments before measuring a lake that crosses a tile edge.
        core=box(tx*4096,ty*4096,(tx+1)*4096,(ty+1)*4096)
        if not core.contains(lake):
            neighbors=[]
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    if 0<=tx+dx<2**zoom and 0<=ty+dy<2**zoom:
                        neighbors.extend(water_shapes(zoom,tx+dx,ty+dy))
            merged=unary_union(neighbors)
            pieces=list(merged.geoms) if merged.geom_type=='MultiPolygon' else [merged]
            lake=next((p for p in pieces if p.covers(anchor)),lake)
        if lake.geom_type=='MultiPolygon':
            lake=next((p for p in lake.geoms if p.covers(anchor)),max(lake.geoms,key=lambda p:p.area))
        rectangle=lake.minimum_rotated_rectangle
        if rectangle.geom_type!='Polygon':
            continue
        points=list(rectangle.exterior.coords)
        edges=[(math.hypot(b[0]-a[0],b[1]-a[1]),math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))) for a,b in zip(points,points[1:])]
        length,angle=max(edges)
        width=min(e[0] for e in edges)
        # Fit a padded, single-line text rectangle inside the polygon at its anchor.
        # Conservative font estimate (including letter spacing); clients select the
        # horizontal layer at the resulting zoom, including overzoomed offline tiles.
        low,high=0.0,max(lake.bounds[2]-lake.bounds[0],lake.bounds[3]-lake.bounds[1])
        half_width=max(1,len(name))*.34
        for _ in range(24):
            em=(low+high)/2
            if lake.covers(box(px-half_width*em,py-.85*em,px+half_width*em,py+.85*em)):
                low=em
            else:
                high=em
        world_em=low/(4096*2**zoom)
        horizontal_zoom=24.0
        for step in range(50,221):
            display_zoom=step/10
            font=11+(min(display_zoom,12)-5)*3/7 if display_zoom<=12 else 14+(min(display_zoom,18)-12)*.5
            if world_em*512*2**display_zoom>=font:
                horizontal_zoom=display_zoom
                break
        # Round lakes retain horizontal labels; elongated lakes use their major axis.
        if width<=0 or length/width<1.4:
            return 0.0,False,0.0
        return round((angle+90)%180-90,1),True,horizontal_zoom
    return 0.0,False,0.0


def orient_lake_labels(blob,z,x,y):
    decoded=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True})
    from area_tiles import features_for_tile,owns_name
    local=[]
    for feature in decoded.get('area',{}).get('features',[]):
        point=shape(feature['geometry']);wx=(x+point.x/4096)/2**z;wy=(y+point.y/4096)/2**z
        if not owns_name(feature['properties']['name'],wx,wy):local.append(feature)
    area_features=local+features_for_tile(z,x,y)
    from path_context import annotate
    # Fine reference geometry stays aggregated until agency matching is complete.
    roads,paths_changed=annotate(decoded.get('road',{}).get('features',[]),z,x,y) if z==12 else ([],False)
    if paths_changed:decoded['road']={'features':roads}
    if not decoded.get('water_label',{}).get('features') and not area_features and not decoded.get('area',{}).get('features') and not paths_changed:
        return blob
    decoded['area']={'features':area_features}
    for feature in decoded.get('water_label',{}).get('features',[]):
        point=shape(feature['geometry'])
        if point.geom_type!='Point':
            continue
        wx=(x+point.x/4096)/2**z;wy=(y+point.y/4096)/2**z
        angle,elongated,horizontal_zoom=lake_axis(round(wx,9),round(wy,9),feature['properties']['name'])
        feature['properties'].update(label_angle=angle,label_elongated=elongated,label_horizontal_zoom=horizontal_zoom)
    return mapbox_vector_tile.encode([{'name':name,'features':layer['features']} for name,layer in decoded.items()],default_options={'extents':4096,'y_coord_down':True})


def render_tile(z,x,y):
    if not 0<=z<=14 or not 0<=x<2**z or not 0<=y<2**z:
        raise ValueError('National basemap accepts valid XYZ coordinates at zooms 0–14')
    blob=normalize_tile(archive().get(z,x,y),z)
    return orient_lake_labels(blob,z,x,y)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('z',type=int);parser.add_argument('x',type=int);parser.add_argument('y',type=int)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    start=time.monotonic();blob=render_tile(args.z,args.x,args.y)
    if args.output:
        args.output.write_bytes(blob)
    decoded=mapbox_vector_tile.decode(blob)
    print(json.dumps({'datasetId':DATASET_ID,'bytes':len(blob),'seconds':round(time.monotonic()-start,3),'layers':{name:len(layer['features']) for name,layer in decoded.items()}},indent=2))
