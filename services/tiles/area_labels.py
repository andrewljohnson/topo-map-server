"""Stable visual centers for overview area labels, independent of navigation bounds."""
import math
from shapely.geometry import shape, Point
from shapely.ops import transform, polylabel

R=6378137.0

def project(x,y,z=None):
    return R*math.radians(x),R*math.asinh(math.tan(math.radians(max(-85.05112878,min(85.05112878,y)))))

def unproject(x,y):
    return [math.degrees(x/R),math.degrees(math.atan(math.sinh(y/R)))]

def polygons(g):
    if g.geom_type=='Polygon':return [g]
    return [p for c in getattr(g,'geoms',[]) for p in polygons(c)]

def label_center(geometry):
    # Match the displayed Mercator shape, including at high latitudes. Work on
    # one connected component so offshore islands and split dateline parts cannot
    # put a label in the sea or halfway around the world.
    parts=[transform(project,p) for p in polygons(shape(geometry)) if not p.is_empty]
    if not parts:raise ValueError('Area label requires polygon geometry')
    main=max(parts,key=lambda p:p.area)
    point=main.centroid
    method='mercator_centroid'
    if not main.covers(point):
        w,s,e,n=main.bounds
        point=polylabel(main,tolerance=max(1,min(100,min(e-w,n-s)/500)))
        method='interior_visual_center'
    coords=unproject(point.x,point.y)
    return coords,method
