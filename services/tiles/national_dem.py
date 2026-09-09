"""Lossless elevation samples for device contours/relief; no rendered terrain graphics."""
import io,json,math,os
from pathlib import Path
from urllib.request import Request,urlopen
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject
import national_contours as usgs

DATASET_ID='dem-terrarium-usgs10m-v2-20260907'
MIN_ZOOM=3
MAX_ZOOM=13
TILE_SIZE=512
CACHE=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).resolve().parent/'data'))/'dem-samples'/DATASET_ID
GLOBAL_URL='https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
ATTRIBUTION='Elevation: USGS 3DEP · <a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md">Mapzen/AWS Terrain Tiles and elevation providers</a> · USGS (3DEP, SRTM, GMTED2010) · NOAA (ETOPO1)'

def decode_png(blob):
    with MemoryFile(blob) as mem:
        with mem.open() as src:rgb=src.read([1,2,3]).astype('float32')
    return rgb[0]*256+rgb[1]+rgb[2]/256-32768

def encode_png(data, *, compression=6):
    if not np.isfinite(data).all():raise ValueError('DEM still has missing samples')
    encoded=np.rint(np.clip(data+32768,0,65535.99609375)*256).astype('uint32')
    rgb=np.stack([(encoded>>16)&255,(encoded>>8)&255,encoded&255]).astype('uint8')
    with MemoryFile() as mem:
        with mem.open(driver='PNG',width=data.shape[1],height=data.shape[0],count=3,dtype='uint8',ZLEVEL=compression) as dst:dst.write(rgb)
        return mem.read()

def global_dem(z,x,y):
    path=CACHE/'global'/str(z)/str(x)/(str(y)+'.png')
    with usgs.locked(path.with_suffix('.lock')):
        if not path.exists():
            blob=urlopen(Request(GLOBAL_URL.format(z=z,x=x,y=y),headers={'User-Agent':'topo-map-server/1.0 elevation samples'}),timeout=60).read()
            data=decode_png(blob)
            if data.shape!=(256,256):raise ValueError('Unexpected global DEM dimensions')
            path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_bytes(blob);tmp.replace(path)
        return decode_png(path.read_bytes())

def render_samples(z,x,y):
    """Return float32 elevation samples before PNG encoding for bounded mosaics."""
    if not MIN_ZOOM<=z<=MAX_ZOOM or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Invalid DEM tile')
    span=20037508.342789244;step=2*span/2**z
    target=from_bounds(-span+x*step,span-(y+1)*step,-span+(x+1)*step,span-y*step,TILE_SIZE,TILE_SIZE)
    data=np.full((TILE_SIZE,TILE_SIZE),np.nan,dtype='float32');sources=[];native=0
    if z>=12:
        try:
            source,affine,sources=usgs.read_tile_dem(z,x,y)
            reproject(source,data,src_transform=affine,src_crs='EPSG:4269',src_nodata=np.nan,dst_transform=target,dst_crs='EPSG:3857',dst_nodata=np.nan,resampling=Resampling.bilinear)
            native=int(np.isfinite(data).sum())
        except usgs.CoverageUnavailable:
            pass
    fallback=int(np.isnan(data).sum())
    if z<=11:
        # Preserve native overview samples: upsampling would quadruple download
        # and decode work without adding elevation information.
        data=global_dem(z,x,y);fallback=int(data.size)
    elif fallback:
        coarse=global_dem(z,x,y)
        expanded=np.empty_like(data)
        # Bilinear reconstruction of measured elevations, never encoded RGB channels.
        reproject(coarse,expanded,src_transform=from_bounds(*rasterio.transform.array_bounds(TILE_SIZE,TILE_SIZE,target),256,256),src_crs='EPSG:3857',dst_transform=target,dst_crs='EPSG:3857',resampling=Resampling.bilinear)
        data[np.isnan(data)]=expanded[np.isnan(data)]
    usgs.atomic_json(CACHE/'provenance'/str(z)/str(x)/(str(y)+'.json'),{'tile':[z,x,y],'encoding':'terrarium','units':'meters','tileSize':data.shape[0],'usgsPixels':native,'globalFallbackPixels':fallback,'usgsChunks':sources,'globalSource':GLOBAL_URL.format(z=z,x=x,y=y) if fallback else None,'processing':'Elevation samples reprojected to Web Mercator; no contour or hillshade generation. Terrarium quantization 1/256 meter, not source accuracy.'})
    return data

def render_tile(z,x,y):
    return encode_png(render_samples(z,x,y))
