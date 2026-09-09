"""USGS Annual NLCD 2024 categorical raster -> bounded, offline vector tiles.

The public USFS/GeoPlatform ImageServer serves the CONUS mosaic. No invented
classification outside its footprint: the basemap retains its OSM land cover.
"""
import fcntl
import json
import math
import os
import tempfile
import time
from functools import lru_cache
from urllib.error import URLError, HTTPError
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import mapbox_vector_tile
import numpy as np
from rasterio.io import MemoryFile
from rasterio.features import shapes, sieve
from rasterio.transform import from_bounds
from shapely.geometry import shape

DATASET_ID = 'usgs-annual-nlcd-2024-c1v1-v1'
MIN_ZOOM, MAX_ZOOM = 6, 14
BOUNDS = [-129.28, 21.80, -63.11, 52.93]
SOURCE = 'https://imagery.geoplatform.gov/iipp/rest/services/Vegetation/USFS_EDW_NLCD_Landcover_CONUS/ImageServer'
CACHE = Path(os.environ.get('TILE_DATA_DIR', Path(__file__).parent / 'data')) / 'national-landcover' / DATASET_ID
HALF_WORLD = 20037508.342789244
# Water is deliberately omitted: accurate OSM lake/river polygons sit above
# terrestrial cover. Unknown/nodata values are never silently colored.
CLASSES = {12: ('ice', 'snow_ice'), 21: ('developed', 'open_space'),
 22: ('developed', 'low_intensity'), 23: ('developed', 'medium_intensity'),
 24: ('developed', 'high_intensity'), 31: ('rock', 'barren'),
 41: ('forest', 'deciduous'), 42: ('forest', 'evergreen'), 43: ('forest', 'mixed'),
 51: ('scrub', 'dwarf_scrub'), 52: ('scrub', 'shrub'), 71: ('grass', 'herbaceous'),
 72: ('grass', 'sedge'), 73: ('grass', 'lichens'), 74: ('grass', 'moss'),
 81: ('farmland', 'pasture'), 82: ('farmland', 'crops'),
 90: ('wetland', 'woody'), 95: ('wetland', 'emergent')}


def tile_bounds(z, x, y):
    width = 2 * HALF_WORLD / 2**z
    return (-HALF_WORLD+x*width, HALF_WORLD-(y+1)*width,
            -HALF_WORLD+(x+1)*width, HALF_WORLD-y*width)


def covered(bbox):
    w,s,e,n = bbox
    # Published service extent in EPSG:3857; pixels outside CONUS are nodata.
    return e > -14391085.4222 and w < -7026295.4222 and n > 2488123.6211 and s < 6967723.6211


def fetch_raster(bbox, size):
    params = {'f':'image', 'format':'tiff', 'bbox':','.join(map(str,bbox)),
      'bboxSR':3857, 'imageSR':3857, 'size':f'{size},{size}',
      'pixelType':'U8', 'interpolation':'RSP_NearestNeighbor',
      'adjustAspectRatio':'false', 'noData':0,
      'renderingRule':json.dumps({'rasterFunction':'None'}),
      'mosaicRule':json.dumps({'mosaicMethod':'esriMosaicLockRaster','lockRasterIds':[40], 'mosaicOperation':'MT_FIRST'})}
    req = Request(SOURCE+'/exportImage?'+urlencode(params), headers={'User-Agent':'topo-map-server/1.0 (USGS NLCD basemap)'})
    for attempt in range(4):
        try:
            with urlopen(req, timeout=60) as response:
                data=response.read(4*1024*1024+1)
            break
        except (URLError, TimeoutError, ConnectionError) as error:
            if isinstance(error, HTTPError) and error.code not in (408,429,500,502,503,504):
                raise
            if attempt==3: raise
            time.sleep(2**attempt)

    if len(data)>4*1024*1024: raise RuntimeError('Land cover raster exceeds bounded response size')
    with MemoryFile(data) as mem, mem.open() as ds:
        if ds.count!=1 or ds.width!=size or ds.height!=size:
            raise RuntimeError('Unexpected categorical land cover raster')
        values=ds.read(1)
        if not set(np.unique(values)).issubset({0,11,255,*CLASSES}):
            raise RuntimeError('Land cover response contains unknown classes')
    return data


def cached_raster(path,bbox,size):
    if os.environ.get('TOPO_SCRATCH_ROOT') and not path.exists():
        path=Path(os.environ['TOPO_SCRATCH_ROOT'])/'nlcd'/DATASET_ID/path.relative_to(CACHE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists(): return path.read_bytes()
        data=fetch_raster(bbox,size)
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as out:
            out.write(data); name=out.name
        Path(name).replace(path)
        return data


@lru_cache(maxsize=8)
def batch_values(cache,x,y,size):
    # 256 high-detail children share one request with exactly the same pixel
    # spacing/alignment. The pinned raster/year and nearest interpolation stay
    # unchanged. Cache root is part of the key for isolated jobs and tests.
    path=Path(cache)/'metatiles-z14'/str(size)/str(x)/(str(y)+'.tif')
    data=cached_raster(path,tile_bounds(10,x,y),size*16)
    with MemoryFile(data) as mem, mem.open() as ds: values=ds.read(1)
    values.flags.writeable=False
    return values


def raster(z,x,y,bbox,size):
    path=CACHE/'rasters'/str(z)/str(x)/(str(y)+'.tif')
    if path.exists(): return path.read_bytes()
    if z!=14: return cached_raster(path,bbox,size)
    values=batch_values(str(CACHE),x//16,y//16,size)
    dx,dy=x%16,y%16
    child=values[dy*size:(dy+1)*size,dx*size:(dx+1)*size]
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=size,height=size,count=1,dtype='uint8',
                      crs='EPSG:3857',transform=from_bounds(*bbox,size,size)) as ds:
            ds.write(child,1)
        return mem.read()


def vector_features(values,bbox):
    # Keep a one-pixel mask of no-data/water: sieve cannot spread vegetation
    # into an unclassified footprint. Small islands are omitted, not invented.
    mask=np.isin(values,list(CLASSES))
    clean=sieve(values.astype('uint8'),size=4,mask=mask,connectivity=4)
    transform=from_bounds(*bbox, values.shape[1],values.shape[0])
    tolerance=(bbox[2]-bbox[0])/values.shape[1]*.25
    features=[]
    for geom,value in shapes(clean,mask=mask,transform=transform,connectivity=4):
        code=int(value)
        if code not in CLASSES: continue
        geometry=shape(geom).simplify(tolerance,preserve_topology=True)
        klass,subclass=CLASSES[code]
        features.append({'geometry':geometry,'properties':{'class':klass,'subclass':subclass,'nlcd':code,'year':2024,'source':'USGS Annual NLCD'}})
    return features


def render_tile(z,x,y):
    if not MIN_ZOOM<=z<=MAX_ZOOM or not 0<=x<2**z or not 0<=y<2**z:
        raise ValueError('Invalid land cover tile')
    bbox=tile_bounds(z,x,y)
    features=[]
    if covered(bbox):
        # Never request more than 256 squared pixels or oversample the 30 m
        # categorical source at high zoom. Clients overzoom maxzoom14 tiles.
        size=max(16,min(256,math.ceil((bbox[2]-bbox[0])/30)))
        data=raster(z,x,y,bbox,size)
        with MemoryFile(data) as mem, mem.open() as ds: values=ds.read(1)
        features=vector_features(values,bbox)
    return mapbox_vector_tile.encode([{'name':'landcover','features':features}],
        default_options={'extents':4096,'quantize_bounds':bbox})
