"""Evidence-based, non-executable QA suggestions. Never interprets imagery or edits trails."""
import json,math,hashlib,subprocess,functools,concurrent.futures
from pathlib import Path
import numpy as np
from PIL import Image
from shapely.geometry import shape,box,Point
from shapely.ops import unary_union,transform,linemerge
ROOT=Path(__file__).resolve().parents[2];PUBLIC=ROOT/'apps/web/public/review';VERSION='geometry-dem-v1'

def lines(g):
 if g.geom_type=='LineString':return [g]
 return [p for p in getattr(g,'geoms',[]) if p.geom_type=='LineString']
def percentile(v,p):return round(float(np.percentile(v,p)),1) if v else None
def points(g,step=25):
 return [line.interpolate(d) for line in lines(g) for d in np.arange(0,line.length,step)]
def compare(a,b):
 distances=[[p.distance(other) for p in points(g)] for g,other in [(a,b),(b,a)]]
 cover=[[round(g.intersection(other.buffer(t)).length/max(g.length,1),3) for t in [15,30,50]] for g,other in [(a,b),(b,a)]]
 return {'coverage':cover,'medianOffsetM':[percentile(d,50) for d in distances],'p90OffsetM':[percentile(d,90) for d in distances]}
def choose(metrics,stats):
 cov=metrics['coverage'];ratio=max(s['lengthM'] for s in stats)/max(1,min(s['lengthM'] for s in stats));short=min(range(2),key=lambda i:stats[i]['lengthM']);novel=[s['outside50mM'] for s in stats]
 # A default identity assumption is inappropriate even for same-name paths.
 if cov[short][2]<.65:return 'uncertain',None,'low','The alignments diverge too much to choose or merge confidently from geometry alone.'
 if max(novel)>200 and (max(metrics['p90OffsetM'])>75 or any(s.get('endpointsBeyond75m',0)>0 and s['outside50mM']>200 for s in stats)):
  return 'partial',None,'low','Review a segment-level merge: keep one overlapping alignment and verify the outlying sections as possible unique ends or branches. Do not connect them automatically.'
 detail=min(range(2),key=lambda i:stats[i]['medianVertexSpacingM']);other=1-detail
 density_advantage=stats[other]['medianVertexSpacingM']/max(1,stats[detail]['medianVertexSpacingM'])
 if min(c[0] for c in cov)>.9 and ratio<1.08:
  return 'prefer',detail,'medium','The two representations are nearly coincident. Keep one geometry and transfer useful attributes; there is little evidence for drawing both.'
 if density_advantage>=1.7 and ratio<1.3 and stats[detail]['sharpReversalsPerKm']<=stats[other]['sharpReversalsPerKm']+3:
  return 'prefer',detail,'medium','Prefer the more densely represented alignment provisionally: its extra detail is not accompanied by substantial length inflation or a strong reversal-rate warning.'
 return 'uncertain',None,'low','There is substantial overlap, but neither source has a decisive geometric quality advantage. Inspect the shared bends and endpoints before choosing.'

@functools.lru_cache(40)
def dem(path):
 a=np.array(Image.open(path).convert('RGB')).astype(float);return a[:,:,0]*256+a[:,:,1]+a[:,:,2]/256-32768

def analyze(c,dempath):
 lon,lat=c['center'];kx=111320*math.cos(math.radians(lat));ky=111320
 project=lambda x,y,z=None:((x-lon)*kx,(y-lat)*ky)
 scope=transform(project,box(*c['inputScope']));groups=[]
 for agency in c['agencies']:
  groups.append(unary_union([transform(project,shape(f['geometry'])).intersection(scope) for f in c['geometry']['features'] if f['properties']['agency']==agency]))
 metrics=compare(*groups);stats=[];z,tx,ty=c['tile'];n=2**z
 try:arr=dem(dempath)
 except Exception:arr=None
 def elevation(p):
  if arr is None:return None
  x=(p.x/kx+lon+180)/360*n-tx;latitude=p.y/ky+lat;y=(1-math.asinh(math.tan(math.radians(latitude)))/math.pi)/2*n-ty
  if not(0<=x<1 and 0<=y<1):return None
  h,w=arr.shape;xx=x*(w-1);yy=y*(h-1);ix=int(xx);iy=int(yy);fx=xx-ix;fy=yy-iy
  return float(arr[iy,ix]*(1-fx)*(1-fy)+arr[iy,min(ix+1,w-1)]*fx*(1-fy)+arr[min(iy+1,h-1),ix]*(1-fx)*fy+arr[min(iy+1,h-1),min(ix+1,w-1)]*fx*fy)
 for i,g in enumerate(groups):
  spacing=[];sharp=0;grades=[];attempted=0;ends=[]
  for line in lines(g):
   coords=list(line.coords);spacing += [math.dist(a,b) for a,b in zip(coords,coords[1:]) if math.dist(a,b)>.5]
   sampled=[line.interpolate(d) for d in np.arange(0,line.length,25)]
   for a,b,cpoint in zip(sampled,sampled[1:],sampled[2:]):
    va=np.array([b.x-a.x,b.y-a.y]);vb=np.array([cpoint.x-b.x,cpoint.y-b.y]);den=np.linalg.norm(va)*np.linalg.norm(vb)
    if den>1 and np.dot(va,vb)/den<math.cos(math.radians(135)):sharp+=1
   # Grades use only the mutually nearby corridor, inside the audited DEM tile.
   for d in np.arange(0,max(0,line.length-50),50):
    a=line.interpolate(d);b=line.interpolate(d+50)
    if a.distance(groups[1-i])>50 or b.distance(groups[1-i])>50:continue
    attempted+=1;ea=elevation(a);eb=elevation(b)
    if ea is not None and eb is not None:grades.append(abs(eb-ea)/50*100)
   for p in [Point(coords[0]),Point(coords[-1])]:
    # Exclude crop boundaries and OSM internal z14 tile seams. Remaining
    # endpoints are still candidates, never proof of trailheads or destinations.
    x=(p.x/kx+lon+180)/360*16384;latitude=p.y/ky+lat;y=(1-math.asinh(math.tan(math.radians(latitude)))/math.pi)/2*16384
    seam=min(abs(x-round(x)),abs(y-round(y)))*40075016.686*math.cos(math.radians(lat))/16384
    if scope.boundary.distance(p)>20 and seam>12:ends.append(p.distance(groups[1-i]))
  stats.append({'source':c['agencies'][i],'lengthM':round(g.length),'medianVertexSpacingM':percentile(spacing,50) or 0,'sharpReversalsPerKm':round(sharp/max(g.length/1000,1),2),'outside50mM':round(g.difference(groups[1-i].buffer(50)).length),'endpointCandidates':len(ends),'endpointsBeyond75m':sum(d>75 for d in ends),'demSamples':len(grades),'demEligibleSamples':attempted,'terrainGradeP90Percent':percentile(grades,90),'terrainGradeOver35Percent':round(sum(v>35 for v in grades)/len(grades)*100,1) if grades else None})
 action,best,confidence,summary=choose(metrics,stats)
 reasons=[f"{s['source']}: {metrics['coverage'][i][0]*100:.0f}% of its geometry lies within 15 m of the other source; {metrics['coverage'][i][2]*100:.0f}% within 50 m. Median nearest-line offset {metrics['medianOffsetM'][i]} m." for i,s in enumerate(stats)]
 reasons.append('Within the same input window, '+ '; '.join(f"{s['source']}: {s['lengthM']:,} m long, median vertex spacing {s['medianVertexSpacingM']} m, {s['outside50mM']:,} m outside the other source’s 50 m corridor" for s in stats)+'.')
 reasons.append('Endpoint check: '+ '; '.join(f"{s['source']} has {s['endpointsBeyond75m']} non-seam endpoint candidates over 75 m from the other alignment" for s in stats)+'. These can be real additions, branches, or source gaps; inspect their connections.')
 terrain=[]
 for s in stats:
  if s['demSamples']>=10:terrain.append(f"{s['source']}: 90th-percentile absolute terrain grade {s['terrainGradeP90Percent']}% over {s['demSamples']} sampled 50 m sections")
 if terrain:reasons.append('DEM sanity check in the shared corridor: '+'; '.join(terrain)+'. Lower grade alone does not mean a route is more accurate.')
 reasons.append('Vertex density measures representation detail, not survey accuracy. Sharp turns may be genuine switchbacks; geometry alone cannot diagnose GPS multipath.')
 return {'version':VERSION,'action':action,'preferredSource':c['agencies'][best] if best is not None else None,'confidence':confidence,'summary':summary,'reasons':reasons,'metrics':metrics,'sources':stats,'terrainAvailable':arr is not None,'evidenceHash':hashlib.sha256(json.dumps(c['geometry'],sort_keys=True).encode()).hexdigest(),'limitations':'Heuristic guidance, not an independent ground-truth verdict. Uses source geometry and frozen DEM only; no imagery interpretation or route editing. DEM measures ground surface, not surveyed trail elevation. Full agency inputs and OSM tile fragments have different lineage; no automatic edits.'}

def main():
 report=json.loads((PUBLIC/'candidates.json').read_text());cache=Path('/tmp/qa-recommendation-dem');cache.mkdir(exist_ok=True)
 def fetch(tile):
  z,x,y=tile;p=cache/f'{z}-{x}-{y}.png'
  if not p.exists():
   try:subprocess.run(['curl','-fsS','--max-time','30',f"https://topo-map.andrewljohnson.workers.dev/releases/{report['release']}/dem/{z}/{x}/{y}.png",'-o',str(p)],check=True,capture_output=True)
   except subprocess.CalledProcessError:return
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(fetch,sorted({tuple(c['tile']) for c in report['candidates']})))
 counts={}
 for item in report['candidates']:
  path=PUBLIC/'evidence-v2'/(item['id']+'.json');c=json.loads(path.read_text());z,x,y=c['tile'];rec=analyze(c,cache/f'{z}-{x}-{y}.png');c['recommendation']=rec;path.write_text(json.dumps(c,separators=(',',':')));counts[rec['action']]=counts.get(rec['action'],0)+1
  print(c['name'],rec['action'],rec['preferredSource'],[s['demSamples'] for s in rec['sources']],flush=True)
 print(counts)
if __name__=='__main__':main()
