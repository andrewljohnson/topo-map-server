#!/usr/bin/env python3
"""Generate statewide 20-foot contours from USGS 1/3-arc-second DEM COG windows.

Workers read bounded halo windows on one aligned NAD83 grid. Per-chunk checkpoints
are resumable; contours.sqlite is replaced only after all selected chunks succeed.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import multiprocessing
from multiprocessing.util import Finalize
import os
from pathlib import Path
import sqlite3
import time

import contourpy
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform as transform_coords, transform_bounds, transform_geom
from rasterio.windows import Window
from shapely import from_wkb
from shapely.geometry import LineString, box, mapping, shape
from shapely.ops import transform as transform_geometry

import tile_service as tiles

VERSION = 'usgs13-feet20-v1'
RESOLUTION = 1 / 10800  # Native 1/3 arc-second (~10 m north-south).
METERS_PER_FOOT = 0.3048  # Exact international-foot conversion.
_ENV = None
_CONTEXT = None
_SOURCES = []


def coverage_geometry():
    def inverse(x,y,z=None):
        x=np.asarray(x);y=np.asarray(y)
        return x*360-180,np.degrees(np.arctan(np.sinh(np.pi*(1-2*y))))
    geographic=transform_geometry(inverse,tiles.extract_boundary())
    geographic=geographic.intersection(box(*tiles.BOUNDS))
    return shape(transform_geom('EPSG:4326','EPSG:4269',mapping(geographic)))


def grid_spec(coverage,chunk_size):
    west,south,east,north=coverage.bounds
    left=math.floor(west/RESOLUTION)*RESOLUTION
    top=math.ceil(north/RESOLUTION)*RESOLUTION
    width=math.ceil((east-left)/RESOLUTION)
    height=math.ceil((top-south)/RESOLUTION)
    transform=Affine(RESOLUTION,0,left,0,-RESOLUTION,top)
    chunks=[]
    for row in range(0,height,chunk_size):
        for col in range(0,width,chunk_size):
            w=min(chunk_size,width-col);h=min(chunk_size,height-row)
            extent=box(left+col*RESOLUTION,top-(row+h)*RESOLUTION,left+(col+w)*RESOLUTION,top-row*RESOLUTION)
            if coverage.intersects(extent):
                chunks.append((row,col,h,w))
    return {'transform':list(transform)[:6],'width':width,'height':height,'chunks':chunks}


def contour_lines(elevations_m, transform, clip_geometry):
    """Yield (integer feet, LineString in NAD83); masked DEM never interpolates ocean edges."""
    values=np.ma.masked_invalid(np.asarray(elevations_m,dtype='float64')/METERS_PER_FOOT)
    if values.count()<4:
        return
    lo=float(values.min());hi=float(values.max())
    # Flat zero-height sea cells must not produce a spurious coastline contour.
    first=max(20,math.ceil(lo/20)*20)
    last=math.floor(hi/20)*20
    if first>last:
        return
    rows,cols=values.shape
    xs=transform.c+(np.arange(cols)+.5)*transform.a
    ys=transform.f+(np.arange(rows)+.5)*transform.e
    generator=contourpy.contour_generator(x=xs,y=ys,z=values,name='serial',corner_mask=False,line_type='Separate')
    for feet in range(first,last+1,20):
        for coords in generator.lines(float(feet)):
            if len(coords)<2:
                continue
            clipped=LineString(coords).intersection(clip_geometry)
            parts=list(clipped.geoms) if clipped.geom_type in ('MultiLineString','GeometryCollection') else [clipped]
            for line in parts:
                if line.geom_type=='LineString' and not line.is_empty and len(line.coords)>1:
                    yield feet,line


def worker_cleanup():
    global _ENV,_SOURCES
    for entry in _SOURCES:
        if entry.get('vrt') is not None:
            entry['vrt'].close()
        if entry.get('dataset') is not None:
            entry['dataset'].close()
    _SOURCES=[]
    if _ENV is not None:
        _ENV.__exit__(None,None,None)
        _ENV=None


def worker_init(context):
    global _ENV,_CONTEXT,_SOURCES
    _CONTEXT=context
    _ENV=rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_CACHEMAX=64*1024*1024,GDAL_HTTP_MAX_RETRY=3,GDAL_HTTP_RETRY_DELAY=1,GDAL_HTTP_TIMEOUT=90)
    _ENV.__enter__()
    Finalize(None,worker_cleanup,exitpriority=10)
    _SOURCES=[]
    for source in context['sources']:
        # Opening is lazy, so workers only fetch COG headers for intersecting sources.
        _SOURCES.append({'source':source,'dataset':None,'vrt':None})


def read_chunk(window):
    context=_CONTEXT;target=Affine(*context['grid']['transform'])
    dst=np.full((int(window.height),int(window.width)),np.nan,dtype='float32')
    extent=box(*rasterio.windows.bounds(window,target))
    for entry in _SOURCES:
        source=entry['source']
        if not extent.intersects(box(*source['bounds_nad83'])):
            continue
        if entry['dataset'] is None:
            dataset=rasterio.open(source['path'])
            entry['dataset']=dataset
            entry['vrt']=WarpedVRT(dataset,crs='EPSG:4269',transform=target,width=context['grid']['width'],height=context['grid']['height'],resampling=Resampling.bilinear,nodata=float('nan'),dtype='float32',warp_mem_limit=32)
        block=entry['vrt'].read(1,window=window,masked=True)
        data=block.filled(np.nan)
        good=np.isnan(dst)&np.isfinite(data)
        dst[good]=data[good]
    return dst


def process_chunk(chunk):
    context=_CONTEXT
    row,col,h,w=chunk
    key=f'{row}-{col}'
    directory=Path(context['checkpoint_dir'])
    completed=directory/(key+'.sqlite')
    if completed.exists():
        return key,'cached'
    halo=2
    r0=max(0,row-halo);c0=max(0,col-halo)
    r1=min(context['grid']['height'],row+h+halo);c1=min(context['grid']['width'],col+w+halo)
    window=Window(c0,r0,c1-c0,r1-r0)
    transform=Affine(*context['grid']['transform'])
    local=rasterio.windows.transform(window,transform)
    core=box(*rasterio.windows.bounds(Window(col,row,w,h),transform))
    coverage=from_wkb(bytes.fromhex(context['coverage_wkb']))
    clip=core.intersection(coverage)
    raster_cache=directory/(key+'.npy')
    if raster_cache.exists():
        elevations=np.load(raster_cache,allow_pickle=False)
    else:
        elevations=read_chunk(window)
        temporary_raster=directory/(key+'.tmp.npy')
        np.save(temporary_raster,elevations,allow_pickle=False)
        temporary_raster.replace(raster_cache)
    mask=geometry_mask([mapping(clip)],out_shape=elevations.shape,transform=local,invert=True)
    # Count only the core coverage; no-data oceans are expected, absent land is auditable.
    valid=int(np.count_nonzero(np.isfinite(elevations)&mask));expected=int(np.count_nonzero(mask))
    digest=hashlib.sha256(elevations.tobytes()).hexdigest()
    temporary=directory/(key+'.build.sqlite')
    temporary.unlink(missing_ok=True)
    con=sqlite3.connect(temporary)
    con.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; CREATE TABLE lines(ele_ft INTEGER, geometry BLOB); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
    count=0
    for feet,line in contour_lines(elevations,local,clip):
        coords=np.asarray(line.coords)
        # Explicit NAD83 -> WGS84 transformation, then normalized Web Mercator.
        xs,ys=transform_coords('EPSG:4269','EPSG:4326',coords[:,0],coords[:,1])
        xs=np.asarray(xs);ys=np.asarray(ys)
        projected=np.column_stack(((xs+180)/360,(1-np.arcsinh(np.tan(np.radians(ys)))/np.pi)/2))
        con.execute('INSERT INTO lines VALUES (?,?)',(feet,LineString(projected).wkb))
        count+=1
    summary={'chunk':key,'validPixels':valid,'coveragePixels':expected,'lineCount':count,'demSha256':digest}
    con.execute('INSERT INTO metadata VALUES (?,?)',('summary',json.dumps(summary)))
    con.commit();con.close();temporary.replace(completed)
    return key,summary


def prepare(manifest_path,workers=3,chunk_size=1024):
    manifest=json.loads(Path(manifest_path).read_text())
    sources=sorted(manifest['sources'],key=lambda source:source['id'])
    for source in sources:
        if source.get('vertical_units')!='meters':
            raise ValueError('Only DEM meters are supported; check manifest vertical units')
        if source.get('vertical_datum')!='NAVD88':
            raise ValueError('Expected consistent NAVD88 vertical datum')
    coverage=coverage_geometry();grid=grid_spec(coverage,chunk_size)
    print(f'Contour build: {len(grid["chunks"])} chunks on native 1/3 arc-second NAD83 grid; {workers} workers',flush=True)
    # Resolve metadata only, not complete rasters. Source content remains remote COG windows.
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_MAX_RETRY=3,GDAL_HTTP_TIMEOUT=90):
        for source in sources:
            with rasterio.open(source['path']) as dataset:
                source['bounds_nad83']=list(transform_bounds(dataset.crs,'EPSG:4269',*dataset.bounds,densify_pts=21))
                source['raster_crs']=dataset.crs.to_string()
                source['pixel_size']=list(dataset.res)
                source['nodata']=dataset.nodata
    fingerprint={'version':VERSION,'sources':sources,'coverage':coverage.wkb_hex,'chunk_size':chunk_size,'grid':grid}
    build_hash=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
    directory=tiles.DATA/'dem'/'checkpoints'/build_hash[:16]
    directory.mkdir(parents=True,exist_ok=True)
    context={'sources':sources,'grid':grid,'coverage_wkb':coverage.wkb_hex,'checkpoint_dir':str(directory)}
    (directory/'build.json').write_text(json.dumps(fingerprint,indent=2))
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),initializer=worker_init,initargs=(context,)) as pool:
        futures={pool.submit(process_chunk,chunk):chunk for chunk in grid['chunks']}
        for number,future in enumerate(as_completed(futures),1):
            key,summary=future.result()
            print(f'{number}/{len(futures)} chunks complete ({round(time.monotonic()-start)}s): {key} '+('cached' if summary=='cached' else f'{summary["lineCount"]} lines'),flush=True)
    output=tiles.DATA/'contours.build.sqlite';output.unlink(missing_ok=True)
    con=sqlite3.connect(output)
    con.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; CREATE TABLE contours(id INTEGER PRIMARY KEY,ele_ft INTEGER,is_index INTEGER,geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
    summaries=[];feature_count=0
    for chunk in grid['chunks']:
        key=f'{chunk[0]}-{chunk[1]}'
        with sqlite3.connect(directory/(key+'.sqlite')) as part:
            summaries.append(json.loads(part.execute("SELECT value FROM metadata WHERE key='summary'").fetchone()[0]))
            for feet,wkb in part.execute('SELECT ele_ft,geometry FROM lines'):
                geom=from_wkb(wkb);minx,miny,maxx,maxy=geom.bounds
                cursor=con.execute('INSERT INTO contours(ele_ft,is_index,geometry) VALUES (?,?,?)',(feet,int(feet%100==0),wkb))
                con.execute('INSERT INTO spatial VALUES (?,?,?,?,?)',(cursor.lastrowid,minx,maxx,miny,maxy))
                feature_count+=1
    source_hash=hashlib.sha256((build_hash+''.join(s['demSha256'] for s in summaries)).encode()).hexdigest()
    info={'status':'ready','sourceHash':source_hash,'intervalFt':20,'indexIntervalFt':100,'sourceResolution':'1/3 arc-second (approximately 10 m)','processingResolutionArcSeconds':1/3,'verticalDatum':'NAVD88','elevationUnit':'feet','feetDefinition':'international foot, exactly 0.3048 m','source':'USGS 3DEP 1/3 arc-second DEM','sourceUrls':[s['url'] for s in sources],'sources':sources,'featureCount':feature_count,'chunks':len(summaries),'validPixels':sum(s['validPixels'] for s in summaries),'coveragePixels':sum(s['coveragePixels'] for s in summaries),'buildVersion':VERSION}
    con.execute('INSERT INTO metadata VALUES (?,?)',('info',json.dumps(info)))
    con.execute('CREATE INDEX contour_index ON contours(is_index)')
    con.commit();con.close()
    output.replace(tiles.DATA/'contours.sqlite')
    (tiles.DATA/'dem'/'contours-provenance.json').write_text(json.dumps(info,indent=2))
    print(f'COMPLETE: {feature_count:,} contours; source hash {source_hash}',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path(__file__).resolve().parent/'dem_sources.json')
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--chunk-size',type=int,default=1024)
    args=parser.parse_args()
    prepare(args.manifest,args.workers,args.chunk_size)
