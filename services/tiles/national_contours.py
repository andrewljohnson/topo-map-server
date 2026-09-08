"""On-demand USGS contours, independent of OSM extracts and tile_service globals.

Native 1/3-arcsecond NAD83 grid, persistent 1024-square DEM blocks, bounded COG
range reads, two-pixel contour halo. TNM source selections are pinned on first use
per one-degree catalog cell; delete/change the cache namespace to refresh sources.
30m fallback (60m in Alaska when needed) is explicit in each block/tile provenance. Network errors propagate.
"""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import contourpy
import mapbox_vector_tile
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform as transform_coords
from shapely.geometry import LineString, box

# Bump epoch when refreshing catalogs; server tile caches key on this ID.
DATASET_ID = 'usgs-national-dem-feet20-v2-' + os.environ.get('NATIONAL_CONTOURS_EPOCH', '20260905')
CACHE = Path(os.environ.get('NATIONAL_CONTOURS_DATA', str(Path(os.environ.get('TILE_DATA_DIR', str(Path(__file__).resolve().parent / 'data'))) / 'national_dem'))) / DATASET_ID
TNM = 'https://tnmaccess.nationalmap.gov/api/v1/products'
DATASETS = {10: 'National Elevation Dataset (NED) 1/3 arc-second', 30: 'National Elevation Dataset (NED) 1 arc-second', 60: 'National Elevation Dataset (NED) Alaska 2 arc-second'}
RESOLUTION = 1 / 10800
CHUNK = 1024
METERS_PER_FOOT = .3048
GLOBAL_WIDTH = 360 * 10800
GLOBAL_HEIGHT = 180 * 10800


class CoverageUnavailable(RuntimeError):
    """No source/valid samples; caller must return an explicit unavailable response."""


@contextmanager
def locked(path):
    # The backend runs on Linux; advisory locks coordinate independent render workers.
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as temp:
        json.dump(value, temp, sort_keys=True)
    os.replace(temp.name, path)


def request_json(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'topo-map-server/1 USGS DEM client'}), timeout=60) as response:
                data = json.load(response)
            if data.get('error') or data.get('errors'):
                raise RuntimeError(f'TNM catalog error: {data.get("error") or data.get("errors")}')
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def select_sources(items, resolution):
    """Retain latest dated edition of each published USGS DEM footprint."""
    groups = {}
    for item in items:
        url = item.get('downloadURL') or item.get('urls', {}).get('GeoTIFF')
        if not url or not urlparse(url).path.lower().endswith('.tif'):
            continue
        title = item.get('title', '')
        token = re.search(r'([ns]\d{2}[ew]\d{3})', title + ' ' + url, re.I)
        key = token.group(1).lower() if token else url
        dates = re.findall(r'(20\d{6})', title + ' ' + url)
        rank = (max(dates, default=''), item.get('dateCreated', ''), url)
        candidate = {'url': url, 'id': item.get('sourceId', item.get('id', '')), 'title': title,
                     'resolution_m': resolution, 'elevation_units': 'meters',
                     'vertical_datum': item.get('verticalDatum') or 'USGS source datum; NAVD88 in CONUS; consult product metadata outside CONUS',
                     'metadata_url': item.get('metaUrl') or item.get('sourceOriginId') or '',
                     'catalog_bounds': item.get('boundingBox')}
        if key not in groups or rank > groups[key][0]:
            groups[key] = (rank, candidate)
    return [groups[key][1] for key in sorted(groups)]


def catalog_cell(west, south, resolution):
    """Cache complete paginated TNM responses; failed requests never become empty caches."""
    path = CACHE / 'catalog' / f'{resolution}m_{west}_{south}.json'
    with locked(path.with_suffix('.lock')):
        if path.exists():
            return json.loads(path.read_text())['sources']
        items = []
        offset = 0
        while True:
            params = {'datasets': DATASETS[resolution], 'bbox': f'{west+.001},{south+.001},{west+.999},{south+.999}',
                      'prodFormats': 'GeoTIFF', 'max': 100, 'offset': offset}
            data = request_json(TNM + '?' + urlencode(params))
            if not isinstance(data.get('items'), list):
                raise RuntimeError('Malformed TNM response: missing items')
            page = data['items']
            items.extend(page)
            offset += len(page)
            total = int(data.get('total', offset))
            if offset >= total:
                break
            if not page:
                raise RuntimeError('Incomplete TNM catalog pagination')
        sources = select_sources(items, resolution)
        if items and not sources:
            raise RuntimeError('TNM returned products but no usable GeoTIFF URLs')
        atomic_json(path, {'dataset': DATASETS[resolution], 'queried_at': time.time(), 'sources': sources})
        return sources


def sources_for_bounds(bounds, resolution):
    west, south, east, north = bounds
    found = {}
    for lon in range(max(-180, math.floor(west)), min(180, math.ceil(east))):
        for lat in range(max(-90, math.floor(south)), min(90, math.ceil(north))):
            for source in catalog_cell(lon, lat, resolution):
                found[source['url']] = source
    return [found[key] for key in sorted(found)]


def read_sources(sources, transform, width, height):
    """Small target grid; GDAL fetches COG ranges, not complete degree rasters."""
    data = np.full((height, width), np.nan, dtype='float32')
    extent = (transform.c, transform.f-height*abs(transform.e), transform.c+width*transform.a, transform.f)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                      GDAL_CACHEMAX=32 * 1024 * 1024, GDAL_HTTP_MAX_RETRY=3,
                      GDAL_HTTP_RETRY_DELAY=1, GDAL_HTTP_TIMEOUT=90):
        for source in sources:
            footprint = source.get('catalog_bounds')
            if footprint and all(k in footprint for k in ('minX','minY','maxX','maxY')):
                # Catalog bboxes are geographic; small margin covers datum differences.
                if (footprint['maxX'] < extent[0]-.001 or footprint['minX'] > extent[2]+.001
                        or footprint['maxY'] < extent[1]-.001 or footprint['minY'] > extent[3]+.001):
                    continue
            with rasterio.open(source['url']) as dataset:
                with WarpedVRT(dataset, crs='EPSG:4269', transform=transform, width=width, height=height,
                               nodata=float('nan'), dtype='float32', resampling=Resampling.bilinear, warp_mem_limit=16) as vrt:
                    block = vrt.read(1, masked=True).filled(np.nan)
                    good = np.isnan(data) & np.isfinite(block)
                    data[good] = block[good]
    return data


def chunk_spec(cx, cy):
    col, row = cx * CHUNK, cy * CHUNK
    width, height = min(CHUNK, GLOBAL_WIDTH-col), min(CHUNK, GLOBAL_HEIGHT-row)
    transform = Affine(RESOLUTION, 0, -180 + col*RESOLUTION, 0, -RESOLUTION, 90-row*RESOLUTION)
    return transform, width, height


def load_chunk(cx, cy):
    """Return reusable native-grid DEM data plus explicit acquisition provenance."""
    path = CACHE / 'windows' / f'{cx}_{cy}.npz'
    provenance_path = path.with_suffix('.json')
    with locked(path.with_suffix('.lock')):
        if path.exists() and provenance_path.exists():
            with np.load(path, allow_pickle=False) as archive:
                return archive['elevation_m'], json.loads(provenance_path.read_text())
        transform, width, height = chunk_spec(cx, cy)
        bounds = (transform.c, transform.f-height*RESOLUTION, transform.c+width*RESOLUTION, transform.f)
        sources10 = sources_for_bounds(bounds, 10)
        elevations = read_sources(sources10, transform, width, height)
        count10 = int(np.isfinite(elevations).sum())
        sources30 = []
        count30 = 0
        if np.isnan(elevations).any():
            sources30 = sources_for_bounds(bounds, 30)
            if sources30:
                coarse = read_sources(sources30, transform, width, height)
                fill = np.isnan(elevations) & np.isfinite(coarse)
                count30 = int(fill.sum())
                elevations[fill] = coarse[fill]
        sources60 = []
        count60 = 0
        if np.isnan(elevations).any() and bounds[3] >= 50 and (bounds[0] < -129 or bounds[2] > 170):
            sources60 = sources_for_bounds(bounds, 60)
            if sources60:
                coarse = read_sources(sources60, transform, width, height)
                fill = np.isnan(elevations) & np.isfinite(coarse)
                count60 = int(fill.sum())
                elevations[fill] = coarse[fill]
        info = {'chunk': [cx, cy], 'bounds_nad83': bounds, 'processing_arcseconds': 1/3,
                'source10mPixels': count10, 'fallback30mPixels': count30, 'fallback60mPixels': count60,
                'coverageStatus': 'available' if np.isfinite(elevations).any() else 'no-source-samples',
                'nodataPixels': int(np.isnan(elevations).sum()), 'totalPixels': width*height,
                'sources': sources10+sources30+sources60, 'sha256': hashlib.sha256(elevations.tobytes()).hexdigest()}
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.npz', delete=False) as temp:
            np.savez_compressed(temp, elevation_m=elevations)
        os.replace(temp.name, path)
        atomic_json(provenance_path, info)
        return elevations, info


def tile_bounds(z, x, y):
    if not isinstance(z, int) or not isinstance(x, int) or not isinstance(y, int) or not 11 <= z <= 14 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise ValueError('Contour coordinates must be valid XYZ zoom 11–14')
    n = 2**z
    return x/n, y/n, (x+1)/n, (y+1)/n


def inverse_mercator(x, y):
    return x*360-180, math.degrees(math.atan(math.sinh(math.pi*(1-2*y))))


def read_tile_dem(z, x, y):
    normalized = tile_bounds(z, x, y)
    pad = 8/256/(2**z)
    west, north = inverse_mercator(normalized[0]-pad, normalized[1]-pad)
    east, south = inverse_mercator(normalized[2]+pad, normalized[3]+pad)
    # Consistent global integer grid; halo extends beyond the MVT buffer.
    col0=max(0,math.floor((west+180)/RESOLUTION)-2); col1=min(GLOBAL_WIDTH,math.ceil((east+180)/RESOLUTION)+2)
    row0=max(0,math.floor((90-north)/RESOLUTION)-2); row1=min(GLOBAL_HEIGHT,math.ceil((90-south)/RESOLUTION)+2)
    data=np.full((row1-row0,col1-col0),np.nan,dtype='float32')
    used=[]
    for cy in range(row0//CHUNK,(row1-1)//CHUNK+1):
        for cx in range(col0//CHUNK,(col1-1)//CHUNK+1):
            chunk,info=load_chunk(cx,cy)
            r0=max(row0,cy*CHUNK);r1=min(row1,cy*CHUNK+chunk.shape[0])
            c0=max(col0,cx*CHUNK);c1=min(col1,cx*CHUNK+chunk.shape[1])
            data[r0-row0:r1-row0,c0-col0:c1-col0]=chunk[r0-cy*CHUNK:r1-cy*CHUNK,c0-cx*CHUNK:c1-cx*CHUNK]
            used.append(info)
    if not np.isfinite(data).any():
        raise CoverageUnavailable(f'No valid USGS DEM samples for tile {z}/{x}/{y}; inspect cached window provenance')
    transform=Affine(RESOLUTION,0,-180+col0*RESOLUTION,0,-RESOLUTION,90-row0*RESOLUTION)
    return data,transform,used


def contour_lines(elevations, transform, clip_geometry, interval=20):
    values=np.ma.masked_invalid(np.asarray(elevations,dtype='float64')/METERS_PER_FOOT)
    if values.count()<4:
        return
    # Include below-sea-level terrain (Death Valley); omit only the flat zero level.
    first=math.ceil(float(values.min())/interval)*interval
    last=math.floor(float(values.max())/interval)*interval
    rows,cols=values.shape
    generator=contourpy.contour_generator(x=transform.c+(np.arange(cols)+.5)*transform.a,
        y=transform.f+(np.arange(rows)+.5)*transform.e,z=values,name='serial',corner_mask=False,line_type='Separate')
    for feet in range(first,last+1,interval):
        if feet==0:
            continue
        for coordinates in generator.lines(feet):
            if len(coordinates)<2:
                continue
            clipped=LineString(coordinates).intersection(clip_geometry)
            parts=clipped.geoms if clipped.geom_type in ('MultiLineString','GeometryCollection') else [clipped]
            for line in parts:
                if line.geom_type=='LineString' and not line.is_empty:
                    yield feet,line


def render_tile(z, x, y):
    bounds=tile_bounds(z,x,y)
    elevations,transform,provenance=read_tile_dem(z,x,y)
    pad=8/256/(2**z)
    clip=box(bounds[0]-pad,bounds[1]-pad,bounds[2]+pad,bounds[3]+pad)
    west,north=inverse_mercator(bounds[0]-pad,bounds[1]-pad)
    east,south=inverse_mercator(bounds[2]+pad,bounds[3]+pad)
    features=[]
    for feet,line in contour_lines(elevations,transform,box(west,south,east,north),100 if z<13 else 20):
        coords=np.asarray(line.coords)
        lons,lats=transform_coords('EPSG:4269','EPSG:4326',coords[:,0],coords[:,1])
        lons=np.asarray(lons);lats=np.asarray(lats)
        normalized=np.column_stack(((lons+180)/360,(1-np.arcsinh(np.tan(np.radians(lats)))/np.pi)/2))
        geometry=LineString(normalized).simplify(1.5/(2**z)/4096,preserve_topology=True).intersection(clip)
        if geometry.is_empty or geometry.geom_type not in ('LineString','MultiLineString'):
            continue
        features.append({'geometry':geometry,'properties':{'ele_ft':feet,'index':bool(feet%100==0),'name':f'{feet} ft'}})
    blob=mapbox_vector_tile.encode([{'name':'contour','features':features}],default_options={'quantize_bounds':bounds,'extents':4096,'y_coord_down':True})
    atomic_json(CACHE/'tiles'/str(z)/str(x)/(str(y)+'.json'), {'datasetId':DATASET_ID,'tile':[z,x,y],
        'intervalFt':100 if z<13 else 20,'validPixels':int(np.isfinite(elevations).sum()),'nodataPixels':int(np.isnan(elevations).sum()),
        'chunks':[{'chunk':p['chunk'],'sha256':p['sha256'],'fallback30mPixels':p['fallback30mPixels'],'fallback60mPixels':p.get('fallback60mPixels',0),'nodataPixels':p['nodataPixels']} for p in provenance]})
    return blob
