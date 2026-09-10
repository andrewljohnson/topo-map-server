"""Bounded street/building context for scale-dependent walking-path presentation.

Uses fixed z12 streets (500m) and z14 buildings (150m), independent of the
output tile's clipping. It never removes or moves a path. Conservatively retain
backcountry presentation when any sampled part leaves the dense street grid.
"""
import math
from functools import lru_cache
from shapely.geometry import shape,Point,box,LineString,MultiLineString,mapping
from shapely.affinity import affine_transform
from shapely.ops import unary_union
from shapely.strtree import STRtree
import mapbox_vector_tile
import numpy as np
from scipy.ndimage import convolve

STREETS={'residential','unclassified','tertiary','secondary','primary','motorway','trunk','living_street'}
WALKING={'path','footway','pedestrian','sidewalk','crossing','steps'}

@lru_cache(maxsize=64)
def street_index(x,y):
 from national_basemap import archive,classify
 blob=archive().get(12,x,y)
 layer=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True}).get('roads',{}) if blob else {}
 extent=layer.get('extent',4096);clip=box(x/4096,y/4096,(x+1)/4096,(y+1)/4096);geometries=[]
 for f in layer.get('features',[]):
  match=classify('roads',f['properties'],f['geometry']['type'])
  if match and match[1] in STREETS:
   g=affine_transform(shape(f['geometry']),[1/extent/4096,0,0,1/extent/4096,x/4096,y/4096]).intersection(clip)
   if not g.is_empty:geometries.append(g)
 return geometries,STRtree(geometries)

@lru_cache(maxsize=64)
def building_index(x,y):
 """Use the fixed z14 buildings (z12 omits small lodge buildings); never an output-tile neighbor."""
 from national_basemap import archive
 blob=archive().get(14,x,y)
 layer=mapbox_vector_tile.decode(blob,default_options={'y_coord_down':True}).get('buildings',{}) if blob else {}
 extent=layer.get('extent',4096);clip=box(x/16384,y/16384,(x+1)/16384,(y+1)/16384);geometries=[]
 for f in layer.get('features',[]):
  g=affine_transform(shape(f['geometry']),[1/extent/16384,0,0,1/extent/16384,x/16384,y/16384]).intersection(clip)
  parts=list(g.geoms) if hasattr(g,'geoms') else [g]
  geometries.extend(part for part in parts if part.geom_type=='Polygon' and not part.is_empty)
 return geometries,STRtree(geometries)

@lru_cache(maxsize=32768)
def developed_at(wx,wy):
 # Building groups distinguish lodge/campus circulation from an isolated hut.
 # Quantized lookups are shared across paths; source geometry is never moved.
 metres=40075016.686/math.cosh(math.pi*(1-2*wy));radius=150/metres
 point=Point(wx,wy);clip=point.buffer(radius);near=[]
 for px in range(max(0,int((wx-radius)*16384)),min(16383,int((wx+radius)*16384))+1):
  for py in range(max(0,int((wy-radius)*16384)),min(16383,int((wy+radius)*16384))+1):
   geoms,tree=building_index(px,py)
   near.extend(geoms[int(i)].intersection(clip) for i in tree.query(clip) if geoms[int(i)].intersects(clip))
 if not near:return False
 buildings=unary_union(near);parts=list(buildings.geoms) if hasattr(buildings,'geoms') else [buildings]
 substantial=[g for g in parts if g.area*metres*metres>=20]
 return len(substantial)>=3 and buildings.area*metres*metres>=600 and point.distance(buildings)*metres<=70

GRID=2**19
@lru_cache(maxsize=64)
def street_mass(px,py):
 result=np.zeros((128,128),dtype=np.float64);g=unary_union(street_index(px,py)[0]);parts=[g]
 while parts:
  line=parts.pop()
  if hasattr(line,'geoms'):parts.extend(line.geoms);continue
  if line.is_empty or line.geom_type!='LineString':continue
  for a,b in zip(line.coords,list(line.coords)[1:]):
   dx=b[0]-a[0];dy=b[1]-a[1];steps=max(1,math.ceil(max(abs(dx),abs(dy))*GRID*2));length=math.hypot(dx,dy)/steps
   for i in range(steps):
    t=(i+.5)/steps;xx=math.floor((a[0]+dx*t)*GRID)-px*128;yy=math.floor((a[1]+dy*t)*GRID)-py*128
    if 0<=xx<128 and 0<=yy<128:result[yy,xx]+=length
 return result
@lru_cache(maxsize=512)
def context_grid(bx,by):
 metres=40075016.686/math.cosh(math.pi*(1-2*(by+.5)/16384));radius=500/metres*GRID;halo=math.ceil(radius)+1
 west=bx*32-halo;north=by*32-halo;side=32+2*halo;data=np.zeros((side,side))
 for px in range(max(0,west//128),min(4095,(west+side-1)//128)+1):
  for py in range(max(0,north//128),min(4095,(north+side-1)//128)+1):
   x0=max(west,px*128);y0=max(north,py*128);x1=min(west+side,(px+1)*128);y1=min(north+side,(py+1)*128)
   data[y0-north:y1-north,x0-west:x1-west]=street_mass(px,py)[y0-py*128:y1-py*128,x0-px*128:x1-px*128]
 yy,xx=np.ogrid[-halo:halo+1,-halo:halo+1];kernel=(xx*xx+yy*yy<=radius*radius).astype(float)
 return convolve(data,kernel,mode='constant')[halo:halo+32,halo:halo+32]*metres

@lru_cache(maxsize=32768)
def urban_at(wx,wy):
 # Cheap upper bound avoids grid work when the entire nearby network is sparse.
 metres=40075016.686/math.cosh(math.pi*(1-2*wy));radius=500/metres;clip=box(wx-radius,wy-radius,wx+radius,wy+radius);potential=0.0
 for px in range(max(0,int((wx-radius)*4096)),min(4095,int((wx+radius)*4096))+1):
  for py in range(max(0,int((wy-radius)*4096)),min(4095,int((wy+radius)*4096))+1):
   geoms,tree=street_index(px,py);potential+=sum(geoms[int(i)].length for i in tree.query(clip))
 if potential*metres<4000:return False
 gx=min(GRID-1,max(0,math.floor(wx*GRID)));gy=min(GRID-1,max(0,math.floor(wy*GRID)))
 return bool(context_grid(gx//32,gy//32)[gy%32,gx%32]>=4000)


def annotate(features,z,x,y,*,world=False):
 if z<12:return features,False
 result=[];changed=False;n=2**z
 for f in features:
  if f['properties'].get('class') not in WALKING:
   result.append(f);continue
  g=shape(f['geometry']);parts=list(g.geoms) if g.geom_type=='MultiLineString' else [g]
  groups={None:[],'urban':[],'developed':[]}
  for part in parts:
   if part.geom_type!='LineString':groups[None].append(part);continue
   points=[part.interpolate(t,normalized=True) for t in (0,.5,1)]
   # A stable ~60m context grid shares neighborhood work across tiny paths.
   # Only the lookup moves; original feature coordinates remain unchanged.
   grid=2**19
   positions=[(point.x,point.y) if world else ((x+point.x/4096)/n,(y+point.y/4096)/n) for point in points]
   urban=all(urban_at((math.floor(wx*grid)+.5)/grid,(math.floor(wy*grid)+.5)/grid) for wx,wy in positions)
   context='urban' if urban else None
   props=f['properties']
   # A name/ref/route is positive hiking-route evidence. Do not quiet it merely
   # because the route passes a lodge. Footway and path remain equivalent.
   signed=any(str(props.get(k,'')).strip() for k in ('name','ref','route_ref','badge'))
   if not signed and not urban:
    metres=40075016.686/math.cosh(math.pi*(1-2*positions[1][1]))
    length=part.length*metres if world else part.length/4096/n*metres
    samples=max(2,math.ceil(length/50))
    points=[part.interpolate(i/samples,normalized=True) for i in range(samples+1)]
    coords=[(v.x,v.y) if world else ((x+v.x/4096)/n,(y+v.y/4096)/n) for v in points]
    if all(developed_at((math.floor(wx*grid)+.5)/grid,(math.floor(wy*grid)+.5)/grid) for wx,wy in coords):context='developed'
   groups[context].append(part)
  if not groups['urban'] and not groups['developed']:result.append(f);continue
  changed=True
  for context,group in groups.items():
   if not group:continue
   geometry=group[0] if len(group)==1 else MultiLineString(group)
   props=dict(f['properties'])
   if context:props['path_context']=context
   result.append({**f,'geometry':mapping(geometry),'properties':props})
 return result,changed
