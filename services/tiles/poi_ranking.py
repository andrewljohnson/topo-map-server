"""Nationwide deterministic multi-scale label hierarchy, independent of requested tiles.

Only the offline builder needs scipy/numpy. Serving uses a local SQLite/R-tree.
Known-peak isolation is not terrain prominence; facility isolation reflects the
available catalog, not a complete census of buildings or public access.
"""
import json, math, os, sqlite3, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from feature_matching import name_key, match_reason, merge_into, distance
ROOT=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).parent/'data'))
DB=ROOT/'label-ranking'/'hierarchy-v1.sqlite'
FACILITIES={'visitor_center':95,'ranger_station':90,'trailhead':80,'shelter':80,'campground':75,'backcountry_camp':75,'viewpoint':65,'lodging':60,'picnic_site':45,'information':40}
DETAIL={'restroom','drinking_water','store','food','first_aid'}

def collect_features():
 import national_recreation as recreation
 from national_gazetteers import DB as gazetteer_db
 records={}
 for agency in ('nps','usfs'):
  for path in sorted((recreation.CACHE/'cells'/agency).rglob('*.json')):
   for raw in json.loads(path.read_text()).get('features',[]):
    feature=recreation.normalize(raw,agency)
    if feature:records.setdefault(feature['properties']['id'],feature)
 if recreation.RIDB_DB.exists():
  with sqlite3.connect(recreation.RIDB_DB) as db:
   for raw, in db.execute('SELECT feature FROM facilities'):
    f=json.loads(raw);records.setdefault(f['properties']['id'],f)
 with sqlite3.connect(gazetteer_db) as db:
  for raw, in db.execute('SELECT feature FROM landmarks ORDER BY rowid'):
   f=json.loads(raw);records.setdefault(f['properties']['id'],f)
 priority={'NPS':0,'USFS':1,'Recreation.gov':2,'USGS GNIS':3,'GeoNames':4}
 ordered=sorted(records.values(),key=lambda f:(priority.get(f['properties'].get('agency'),5),f['properties']['id']))
 by_name=defaultdict(set);by_external=defaultdict(set);result=[]
 for f in ordered:
  p=f['properties'];key=name_key(p['name'],p['kind']);kinds=[p['kind']]
  if p['kind'] in ('summit','rock'):kinds=['summit','rock']
  candidates=set().union(*(by_name[k,key] for k in kinds))
  for field in ('gnis_id','geonames_id','ridb_id'):
   if p.get(field):candidates.update(by_external[field,str(p[field])])
  matches=[]
  for i in candidates:
   why=match_reason(f,result[i])
   if why:matches.append((0 if why.endswith('_id') else 1,distance(f['geometry']['coordinates'],result[i]['geometry']['coordinates']),i,why))
  matches.sort()
  if matches and (matches[0][0]==0 or len(matches)==1 or matches[1][1]-matches[0][1]>=30):
   _,_,i,why=matches[0];merge_into(result[i],f,why)
  else:i=len(result);result.append(f)
  by_name[p['kind'],key].add(i)
  for field in ('gnis_id','geonames_id','ridb_id'):
   if p.get(field):by_external[field,str(p[field])].add(i)
 return result,{'raw_unique_records':len(records),'combined_records':len(result)}

def unit_xyz(coords):
 import numpy as np
 a=np.radians(coords);lon,lat=a[:,0],a[:,1]
 return np.column_stack((np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)))

def chord_km(value):
 import numpy as np
 return 12742*np.arcsin(np.minimum(value/2,1))

def isolation(coords,elevations=None):
 """Nearest other point, or nearest strictly higher catalog peak, in kilometres."""
 import numpy as np
 from scipy.spatial import cKDTree
 if not len(coords):return np.empty(0)
 if len(coords)==1:return np.array([20015.0])
 xyz=unit_xyz(coords);tree=cKDTree(xyz)
 if elevations is None:
  d,_=tree.query(xyz,k=2);return chord_km(d[:,1])
 heights=np.asarray(elevations);result=np.full(len(coords),20015.0)
 pending=np.flatnonzero(heights<heights.max());k=min(16,len(coords))
 while len(pending):
  unresolved=[]
  # Bound transient query matrices even for an exceptionally isolated summit.
  for start in range(0,len(pending),max(1,500000//k)):
   indices=pending[start:start+max(1,500000//k)]
   d,neighbors=tree.query(xyz[indices],k=k)
   higher=heights[neighbors]>heights[indices,None]
   found=higher.any(axis=1);first=higher.argmax(axis=1)
   result[indices[found]]=chord_km(d[found,first[found]])
   unresolved.extend(indices[~found])
  if k==len(coords):break
  pending=np.asarray(unresolved,dtype=int);k=min(k*2,len(coords))
 return result

def world(lon,lat):
 return ((lon+180)/360)%1,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2

def hierarchy(entries,spacing=112,detail_spacing=None):
 """Greedy nested selection across zooms; spatial buckets accelerate, not define, winners.

 entries: (stable ID, lon, lat, importance, earliest zoom). Decisions include
 neighboring buckets and wrap at the date line. Once selected a point stays selected.
 """
 ordered=sorted(entries,key=lambda f:(-f[3],f[0]));selected={};coords={f[0]:world(f[1],f[2]) for f in entries}
 for zoom in range(6,14):
  radius=(detail_spacing if detail_spacing is not None and zoom>=10 else spacing)/(512*2**zoom);columns=max(1,math.floor(1/radius));width=1/columns
  buckets=defaultdict(list)
  def add(ident):
   x,y=coords[ident];buckets[int(x/width)%columns,int(y/width)].append((x,y))
  for ident in selected:add(ident)
  for ident,lon,lat,score,earliest in ordered:
   if ident in selected or zoom<earliest:continue
   x,y=coords[ident];cx,cy=int(x/width),int(y/width)
   nearby=(p for dx in (-1,0,1) for dy in (-1,0,1) for p in buckets[(cx+dx)%columns,cy+dy])
   if any(min(abs(x-u),1-abs(x-u))**2+(y-v)**2<radius**2 for u,v in nearby):continue
   selected[ident]=zoom;add(ident)
 return {f[0]:selected.get(f[0],max(14,f[4])) for f in entries}

def rank_features(features):
 import numpy as np
 peaks=[f for f in features if f['properties']['kind']=='summit']
 known=[f for f in peaks if isinstance(f['properties'].get('elevation_m'),(int,float)) and -500<=f['properties']['elevation_m']<=9000]
 higher=isolation([f['geometry']['coordinates'] for f in known],[f['properties']['elevation_m'] for f in known])
 peak_nearest=isolation([f['geometry']['coordinates'] for f in peaks])
 higher_by_id={f['properties']['id']:float(d) for f,d in zip(known,higher)}
 groups=defaultdict(list)
 for f,near in zip(peaks,peak_nearest):
  p=f['properties'];ident=p['id'];d=higher_by_id.get(ident)
  if d is not None:
   score=100*math.log1p(d)+max(0,p['elevation_m'])*.035
   earliest=6 if d>=250 else 7 if d>=70 else 8 if d>=25 else 9 if d>=8 else 10 if d>=2 else 11 if d>=.7 else 12 if d>=.2 else 13
   if d<20015:p['higher_peak_km']=round(d,2)
   else:p['highest_known_peak']=True
   p['rank_elevation_m']=p['elevation_m']
  else:score=35*math.log1p(float(near));earliest=11 if near>=10 else 12
  p['isolation_km']=round(float(near),2);p['poi_importance']=round(score,3);p['rank_family']='summit'
  groups['summit'].append((ident,*f['geometry']['coordinates'],score,earliest))
 facilities=[f for f in features if f['properties']['kind'] in FACILITIES and f['properties'].get('name')]
 nearest=isolation([f['geometry']['coordinates'] for f in facilities])
 for f,d in zip(facilities,nearest):
  p=f['properties'];importance=FACILITIES[p['kind']];score=importance+12*math.log1p(min(float(d),40))
  earliest=9 if d>=15 and importance>=60 else 10 if d>=3 and importance>=60 else 11 if importance>=75 else 12
  p.update(isolation_km=round(float(d),2),poi_importance=round(score,3),rank_family='destination')
  groups['destination'].append((p['id'],*f['geometry']['coordinates'],score,earliest))
 for f in features:
  p=f['properties']
  if 'rank_family' in p:continue
  earliest={'pass':11,'waterfall':12,'arch':13,'rock':13,'cave':14,'spring':14}.get(p['kind'],p.get('min_zoom',14))
  score={'pass':65,'waterfall':60,'arch':50,'rock':45,'cave':35,'spring':30}.get(p['kind'],20)
  p.update(poi_importance=score,rank_family='landmark' if p['kind'] not in DETAIL else 'detail')
  groups[p['rank_family']].append((p['id'],*f['geometry']['coordinates'],score,earliest))
 minimum={};order={}
 for family,entries in groups.items():
  minimum.update(hierarchy(entries,120,72) if family=='summit' else hierarchy(entries,104))
  order.update({e[0]:i for i,e in enumerate(sorted(entries,key=lambda f:(-f[3],f[0])))})
 for f in features:
  p=f['properties'];p['label_minzoom']=minimum[p['id']];p['label_rank']=order[p['id']]
 return features

def build(destination=None):
 destination=Path(destination or DB);destination.parent.mkdir(parents=True,exist_ok=True)
 pending=destination.with_suffix('.pending.sqlite');pending.unlink(missing_ok=True)
 start=time.monotonic();features,stats=collect_features();rank_features(features)
 with sqlite3.connect(pending) as db:
  db.execute('CREATE TABLE features(id TEXT PRIMARY KEY,lon REAL,lat REAL,minzoom INTEGER,feature TEXT)')
  for f in features:
   p=f['properties'];lon,lat=f['geometry']['coordinates']
   db.execute('INSERT INTO features VALUES(?,?,?,?,?)',(p['id'],lon,lat,min(p['label_minzoom'],14),json.dumps(f,separators=(',',':'))))
  db.execute('CREATE VIRTUAL TABLE position USING rtree(id,minlon,maxlon,minlat,maxlat)')
  db.execute('INSERT INTO position SELECT rowid,lon,lon,lat,lat FROM features')
  stats.update(created_at=datetime.now(timezone.utc).isoformat(),seconds=round(time.monotonic()-start,2),families=dict(Counter(f['properties']['rank_family'] for f in features)),zooms=dict(Counter(f['properties']['label_minzoom'] for f in features)),known_peak_elevations=sum('rank_elevation_m' in f['properties'] for f in features))
  db.execute('CREATE TABLE metadata(json TEXT)');db.execute('INSERT INTO metadata VALUES(?)',(json.dumps(stats),));db.commit()
  if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Invalid hierarchy index')
 pending.replace(destination);return stats

def features(extent,zoom,database=None):
 path=Path(database or DB)
 if not path.exists():raise RuntimeError('POI hierarchy index has not been built')
 w,s,e,n=extent
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  return [json.loads(row[0]) for row in db.execute('SELECT f.feature FROM position p JOIN features f ON f.rowid=p.id WHERE p.maxlon>=? AND p.minlon<=? AND p.maxlat>=? AND p.minlat<=? AND f.minzoom<=? ORDER BY f.id',(w,e,s,n,zoom))]

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args();print(json.dumps(build(args.output),indent=2))
