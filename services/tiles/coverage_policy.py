"""World overview through z7, detailed rendering restricted to CONUS."""
from functools import lru_cache
import json
import os
from pathlib import Path
from shapely.geometry import box,shape
from shapely.ops import transform
from shapely.prepared import prep
import math
WORLD_ZOOM=7

def project(x,y,z=None):
    return (x+180)/360,(1-math.asinh(math.tan(math.radians(max(-85.05112878,min(85.05112878,y)))))/math.pi)/2
@lru_cache(maxsize=1)
def conus():
    data=json.loads((Path(__file__).parent/'regions/us-warming.geojson').read_text())
    land=shape(data['geometry']).intersection(box(-125,24,-66,50))
    return transform(project,land)
@lru_cache(maxsize=18)
def geometry(z,halo=False):
    return prep(conus().buffer(2**-z if halo else 0))

def allowed(source,z,x,y):
    if not 0<=z<=14 or not 0<=x<2**z or not 0<=y<2**z:return False
    if source=='osm' and z<=WORLD_ZOOM:return True
    if source=='dem' and not 3<=z<=13:return False
    n=2**z
    return geometry(z,source=='dem').intersects(box(x/n,y/n,(x+1)/n,(y+1)/n))

def enforced():return os.environ.get('TILE_COVERAGE')=='world-conus'


def overzoom(blob,z,x,y):
    """Clip/reproject an existing overview tile; never fetch detailed world data."""
    import mapbox_vector_tile
    from shapely import affinity
    from shapely.geometry import mapping
    scale=2**(z-WORLD_ZOOM);layers=[]
    for name,layer in mapbox_vector_tile.decode(blob).items():
        extent=layer.get('extent',4096);span=extent/scale
        left=(x%scale)*span;bottom=(scale-1-y%scale)*span
        window=box(left,bottom,left+span,bottom+span);features=[]
        for feature in layer['features']:
            geom=shape(feature['geometry'])
            if not geom.is_valid:geom=geom.buffer(0)
            geom=geom.intersection(window)
            if geom.is_empty or geom.geom_type=='GeometryCollection':continue
            geom=affinity.scale(affinity.translate(geom,-left,-bottom),xfact=scale,yfact=scale,origin=(0,0))
            features.append({**feature,'geometry':mapping(geom)})
        layers.append({'name':name,'features':features})
    return mapbox_vector_tile.encode(layers)
