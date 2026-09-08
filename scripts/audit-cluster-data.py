"""Snapshot every cached amenity cluster and build z10–14 offline fixtures for test-all-clusters.mjs. No upstream requests."""
import sys,json,math,collections,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/tiles'))
import mapbox_vector_tile
from shapely.geometry import Point
import national_amenities
groups={};members={};cell_count=0
for path in sorted((national_amenities.CACHE/'cells').glob('*/*.json')):
 if path.name.endswith('.raw.json'):continue
 cell_count+=1
 data=json.loads(path.read_text())
 raw_path=path.with_suffix('.raw.json')
 if data.get('build_version')!=national_amenities.BUILD_VERSION and raw_path.exists():data=national_amenities.build(json.loads(raw_path.read_text()))
 for feature in data['features']:
  props=feature['properties']
  if props['kind']=='group':groups[props['osm_id']]=feature
  else:members[(props['osm_id'],props['poi_icon'])]=feature
area=os.environ.get('CLUSTER_AUDIT_AREA')
if area:
 from areas import area_data
 from shapely.geometry import shape
 region=shape(next(f['geometry'] for f in area_data()[1]['features'] if f['properties']['name']==area and f['geometry']['type']!='Point')).buffer(.01)
 groups={gid:g for gid,g in groups.items() if region.covers(shape(g['geometry']))}
 members={key:f for key,f in members.items() if f['properties'].get('group_id') in groups}
service_checks=[]
for gid,g in groups.items():
 represented=set()
 for f in members.values():
  if f['properties'].get('group_id')!=gid:continue
  represented.add(f['properties']['poi_icon'])
  represented.update(filter(None,f['properties'].get('site_facilities','').split(',')))
 missing=set(g['properties']['icons'])-represented
 service_checks.append({'id':gid,'missing':sorted(missing)})
assert not any(c['missing'] for c in service_checks),'Cluster loses a facility icon after split: '+str([c for c in service_checks if c['missing']][:10])
d={'service_checks':service_checks,'groups':list(groups.values()),'features':list(members.values()),'cells':cell_count}
assert all(any(f['properties'].get('group_id')==gid for f in members.values()) for gid in groups),'Cluster without individual members'
Path('/tmp/topo-cluster-audit-data.json').write_text(json.dumps(d))

features=d['groups']+[f for f in d['features'] if f['properties'].get('group_id')]
root=Path('/tmp/topo-cluster-fixtures');root.mkdir(exist_ok=True)
for z in range(10,15):
 tiles=collections.defaultdict(list)
 for f in features:
  p=dict(f['properties']);lon,lat=f['geometry']['coordinates'];wx=(lon+180)/360*2**z;wy=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z;x,y=int(wx),int(wy)
  if p['kind']=='group':p.update(grid_image='amenity-grid:'+','.join(p['icons'][:12]),grid_rows=math.ceil(len(p['icons'][:12])/3),min_zoom=13 if len(p['icons'])==1 else 10)
  import hashlib
  fid=int.from_bytes(hashlib.sha256((p['osm_id']+p['kind']+p.get('poi_icon','')).encode()).digest()[:7],'big')&((1<<53)-1)
  tiles[(x,y)].append({'geometry':Point((wx-x)*4096,(wy-y)*4096),'id':fid,'properties':{k:v for k,v in p.items() if isinstance(v,(str,int,float,bool))}})
 for (x,y),fs in tiles.items():
  path=root/str(z)/str(x)/f'{y}.pbf';path.parent.mkdir(parents=True,exist_ok=True)
  path.write_bytes(mapbox_vector_tile.encode([{'name':'amenities','features':fs}],default_options={'extents':4096,'y_coord_down':True}))
print('groups',len(d['groups']),'grouped features',len(features)-len(d['groups']))
