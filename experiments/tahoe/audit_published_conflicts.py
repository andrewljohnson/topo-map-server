import argparse,re,sys,json,math,gzip,concurrent.futures,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/tiles'))
import mapbox_vector_tile as m
from shapely.geometry import shape
from shapely.affinity import affine_transform
from shapely.ops import unary_union
from trail_matching import normalized_name
regions=[('Twin Peaks',-120.23739,39.10252),('Mount Rose',-119.92356,39.33387),('Desolation',-120.14,38.9),('Yosemite Valley',-119.5975,37.7439),('Tuolumne',-119.36,37.88),('Mammoth',-119.03,37.63),('Bishop',-118.56,37.25),('Whitney',-118.292,36.579),('Sequoia',-118.75,36.56),('Kings Canyon',-118.56,36.79),('Shasta',-122.194,41.409),('Trinity Alps',-122.96,40.96),('Lassen',-121.51,40.49),('Marble Mountains',-123.1,41.57),('Redwood',-123.99,41.39),('Mendocino',-122.86,39.48),('Point Reyes',-122.84,38.04),('Marin',-122.59,37.9),('Golden Gate Park',-122.486,37.769),('Mount Diablo',-121.915,37.881),('Big Basin',-122.214,37.17),('Pinnacles',-121.19,36.49),('Big Sur',-121.77,36.25),('Ventana',-121.71,36.29),('Los Padres',-119.068,34.65),('Santa Barbara',-119.69,34.48),('Angeles',-118.10,34.33),('San Gabriel',-117.645,34.288),('Big Bear',-116.91,34.24),('San Jacinto',-116.679,33.814),('Cuyamaca',-116.58,32.95),('Joshua Tree',-116.16,34.02),('Death Valley',-117.09,36.24),('Anza Borrego',-116.40,33.25)]
parser=argparse.ArgumentParser(description='Read-only named cross-source overlap triage. Candidates require review; this never edits map data.')
parser.add_argument('--release',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
if not re.fullmatch(r'[a-z0-9-]{1,80}',args.release):parser.error('Invalid release ID')
release=args.release;root=args.output/release;root.mkdir(parents=True,exist_ok=True)
def tile(lon,lat):return int((lon+180)/360*4096),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*4096)
def fetch(row):
 label,lon,lat=row;x,y=tile(lon,lat);p=root/f'{x}-{y}.pbf'
 if not p.exists():
  temp=p.with_suffix('.part')
  subprocess.run(['curl','--fail','--silent','--show-error','--max-time','60',f'https://topo-map.andrewljohnson.workers.dev/releases/{release}/tiles/12/{x}/{y}.pbf','-o',str(temp)],check=True)
  temp.replace(p)
 return row,x,y,p
results=[];fail=[];summaries=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 futures={pool.submit(fetch,r):r for r in regions}
 for fut in concurrent.futures.as_completed(futures):
  try:
   row,x,y,p=fut.result();blob=p.read_bytes();layers=m.decode(gzip.decompress(blob) if blob[:2]==b'\x1f\x8b' else blob,default_options={'y_coord_down':True})
   layer=layers['trails__network'];extent=layer['extent'];scale=40075016.686*math.cos(math.atan(math.sinh(math.pi*(1-2*(y+.5)/4096))))/4096/extent
   groups={};props={}
   for f in layer['features']:
    a=f['properties'];name=normalized_name(a.get('name'));agency=a.get('agency','');kind='trail' if a.get('class') in ('path','footway','cycleway','bridleway','steps','pedestrian','sidewalk','crossing') else 'road'
    if not name or name in ('trail','path','road') or not agency:continue
    key=(name,agency,kind);groups.setdefault(key,[]).append(affine_transform(shape(f['geometry']),[scale,0,0,scale,0,0]));props.setdefault(key,[]).append(a)
   groups={k:unary_union(v) for k,v in groups.items()};keys=list(groups);count=0
   for i,a in enumerate(keys):
    for b in keys[i+1:]:
     if a[0]!=b[0] or a[1]==b[1] or a[2]!=b[2]:continue
     ga,gb=groups[a],groups[b]
     close=ga.intersection(gb.buffer(50,cap_style=2));reverse=gb.intersection(ga.buffer(50,cap_style=2));overlap=min(close.length,reverse.length)
     ratio=overlap/max(1,min(ga.length,gb.length))
     if overlap<100 or ratio<.5:continue
     q=close.interpolate(.5,normalized=True) if close.geom_type=='LineString' else close.representative_point()
     wx=(x+q.x/scale/extent)/4096;wy=(y+q.y/scale/extent)/4096;lon=wx*360-180;lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*wy))))
     results.append({'region':row[0],'tile':[12,x,y],'kind':a[2],'name':props[a][0].get('name'),'agencies':[a[1],b[1]],'overlapM':round(overlap),'shorterCoverage':round(ratio,3),'center':[round(lon,6),round(lat,6)],'url':f'https://topo-map.andrewljohnson.workers.dev/#16/{lat:.6f}/{lon:.6f}','sourceIds':[sorted({v.get('id','') for v in props[k]}) for k in (a,b)]});count+=1
   summaries.append({'region':row[0],'tile':[12,x,y],'networkFragments':len(layer['features']),'candidateGroups':count})
  except Exception as e:fail.append({'region':futures[fut][0],'error':str(e)})
report={'release':release,'method':'34 deliberately selected regional z12 tiles; named cross-agency same-kind network groups with >=100m bilateral overlap within50m and >=50% shorter coverage; candidates NOT confirmed duplicates','regions':sorted(summaries,key=lambda r:r['region']),'candidates':sorted(results,key=lambda r:(-r['overlapM'],r['region'],r['name'])),'failures':fail}
(root/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({'regions':len(summaries),'failures':fail,'candidates':len(results),'regionsWithCandidates':sum(r['candidateGroups']>0 for r in summaries),'top':report['candidates'][:15]},indent=2))
