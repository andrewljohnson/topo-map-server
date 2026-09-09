"""Agency area labels and coarse fills carried inside the combined base map.

This replaces a separate multi-megabyte GeoJSON request for combined clients.
The reviewed precomputed visual centers remain authoritative; local OSM parks
supply labels where no corresponding agency area exists.
"""
from functools import lru_cache
import hashlib,re
from shapely.geometry import Point,box,shape,mapping
from shapely import make_valid
from shapely.ops import unary_union
from shapely.ops import transform
from shapely.affinity import affine_transform
from shapely.strtree import STRtree
from areas import area_data


def project(lon,lat):
    import math
    return (lon+180)/360,(1-math.asinh(math.tan(math.radians(max(-85.05112878,min(85.05112878,lat)))))/math.pi)/2


def normalized_name(name):
    return re.sub(r'[^a-z0-9]','',str(name).casefold())


@lru_cache(maxsize=1)
def index():
    features=[f for f in area_data()[1]['features'] if f['geometry']['type']=='Polygon' or f['geometry']['type']=='MultiPolygon']
    points=[Point(project(*f['properties']['label_center'])) for f in features]
    envelopes=[];names={}
    for i,f in enumerate(features):
        w,s,e,n=f['properties']['bounds'];x0,y0=project(w,n);x1,y1=project(e,s)
        envelopes.append(box(x0,y0,x1,y1))
        names.setdefault(normalized_name(f['properties']['name']),[]).append(i)
    return features,points,envelopes,STRtree(points),STRtree(envelopes),names


def owns_name(name,world_x,world_y):
    _,_,envelopes,_,_,names=index()
    point=Point(world_x,world_y)
    return any(envelopes[i].buffer(.0003).covers(point) for i in names.get(normalized_name(name),[]))


@lru_cache(maxsize=64)
def projected_geometry(i):
    geometry=transform(project,shape(index()[0][i]['geometry']))
    if not geometry.is_valid:geometry=make_valid(geometry)
    if geometry.geom_type=='GeometryCollection':
        geometry=unary_union([g for g in geometry.geoms if g.geom_type in ('Polygon','MultiPolygon')])
    return geometry


def features_for_tile(z,x,y):
    features,points,_,point_tree,area_tree,_=index();n=2**z
    clip=box(x/n,y/n,(x+1)/n,(y+1)/n);output=[]
    def emit(i,geometry):
        p=features[i]['properties'];props={k:p[k] for k in ('id','name','kind','min_zoom','priority')}
        props.update(label_source='agency',**{'class':p['kind']})
        ident=int.from_bytes(hashlib.sha256(str(p['id']).encode()).digest()[:6],'big')
        g=affine_transform(geometry,[4096*n,0,0,4096*n,-4096*x,-4096*y])
        output.append({'id':ident,'geometry':mapping(g),'properties':props})
    for value in point_tree.query(clip):
        i=int(value);p=features[i]['properties'];point=points[i]
        if p['min_zoom']>z+1 or not (x/n<=point.x<(x+1)/n and y/n<=point.y<(y+1)/n):continue
        emit(i,point)
    # Fine agency boundary tiles take over at z8; these are overview fills only.
    if 3<=z<8:
        for value in area_tree.query(clip):
            i=int(value);g=projected_geometry(i).intersection(clip).simplify(.35/512/n,preserve_topology=True)
            if not g.is_empty and g.geom_type in ('Polygon','MultiPolygon'):emit(i,g)
    return output
