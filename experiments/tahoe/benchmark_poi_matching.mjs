#!/usr/bin/env node
// Actual local combined tiles, current mobile matcher versus a trusted local Git baseline.
// Node timings measure matching CPU, not physical phone frame times or tile transport.
import fs from 'node:fs';import vm from 'node:vm';import path from 'node:path';import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {createHash} from 'node:crypto';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),args=process.argv.slice(2);
const option=name=>args[args.indexOf(name)+1];
for(const name of ['--base','--baseline-ref','--output'])if(!args.includes(name))throw Error('Required: --base PATH --baseline-ref LOCAL_GIT_REF --output PATH');
const baselineRef=option('--baseline-ref');if(!/^[\w./-]+$/.test(baselineRef)||baselineRef.startsWith('-'))throw Error('Invalid local Git ref');
const fixtures=JSON.parse(execFileSync(root+'/services/tiles/.venv/bin/python',['-c',String.raw`
import mapbox_vector_tile as m,json,gzip,math,sys
from pathlib import Path
root=Path(sys.argv[1]);sets={}
for name,cx,cy in [('sf',655,1583),('tahoe',682,1565)]:
 out={'osm':[],'amenities':[],'recreation':[]}
 for x in range(cx-1,cx+2):
  for y in range(cy-1,cy+2):
   p=root/'12'/str(x)/f'{y}.pbf'
   if not p.exists():raise RuntimeError(f'Missing fixture {p}')
   blob=p.read_bytes();d=m.decode(gzip.decompress(blob) if blob[:2]==b'\x1f\x8b' else blob,default_options={'y_coord_down':True})
   for layer,key in [('osm__poi','osm'),('amenities__amenities','amenities'),('recreation__recreation','recreation')]:
    if layer not in d:continue
    extent=d[layer]['extent']
    for f in d[layer]['features']:
     if f['geometry']['type']!='Point':continue
     u,v=f['geometry']['coordinates'];f['geometry']['coordinates']=[(x+u/extent)/4096*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+v/extent)/4096))))];out[key].append(f)
 sets[name]=out
print(json.dumps(sets))
`,path.resolve(option('--base'))],{maxBuffer:64*1024*1024}));
const decode=literal=>JSON.parse(literal.slice(literal.indexOf('=')+1).trim().replace(/;$/,''));
const candidateRef=args.includes('--candidate-ref')?option('--candidate-ref'):null;
if(candidateRef&&(!/^[\w./-]+$/.test(candidateRef)||candidateRef.startsWith('-')))throw Error('Invalid local candidate Git ref');
const before=decode(execFileSync('git',['show',baselineRef+':apps/mobile/src/poiMatching.ts'],{cwd:root,encoding:'utf8'})),after=decode(candidateRef?execFileSync('git',['show',candidateRef+':apps/mobile/src/poiMatching.ts'],{cwd:root,encoding:'utf8'}):fs.readFileSync(root+'/apps/mobile/src/poiMatching.ts','utf8'));
function run(code,sources,zoom){
 const events={},layouts={},layers=['amenity-details','amenity-secondary-details','amenity-group-members','recreation-pois','recreation-poi-details','ranked-peaks','amenity-groups','peak-labels'].map(id=>({id,filter:['==',['get','kind'],id.startsWith('amenity')?'amenity':'campground']}));
 const map={getZoom:()=>zoom,getStyle:()=>({sources:Object.fromEntries(Object.keys(sources).map(k=>[k,{type:'vector'}])),layers}),getSource:name=>sources[name],querySourceFeatures:name=>sources[name],setFilter:(id,filter)=>{layers.find(l=>l.id===id).filter=filter},setLayoutProperty:(id,key,value)=>layouts[id+':'+key]=value,on:(event,fn)=>events[event]=fn,off:event=>delete events[event]};
 const context=vm.createContext({setTimeout,clearTimeout});vm.runInContext(code,context);context.installPoiMatching(map);
 const milliseconds=[];for(let i=0;i<3;i++){const start=performance.now();events.idle();milliseconds.push(performance.now()-start)}
 const snapshot=JSON.parse(JSON.stringify({layers,layouts,details:[...map.__topoPoiDetails],stats:map.__topoPoiMatchStats}));events.remove();return {milliseconds,snapshot};
}
const report={baselineRef,candidateRef,matcherSha256:{before:createHash('sha256').update(before).digest('hex'),after:createHash('sha256').update(after).digest('hex')},currentCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),scope:'Nine actual z12 parents per fixture; Node matching CPU only; current working matcher may be uncommitted.',fixtures:[]};
for(const [name,sources] of Object.entries(fixtures))for(const zoom of [11,12,14.99,15,17,18]){
 const old=run(before,sources,zoom),current=run(after,sources,zoom);assert.deepEqual(current.snapshot,old.snapshot,`${name} z${zoom} matching output changed`);
 report.fixtures.push({name,zoom,inputCounts:Object.fromEntries(Object.entries(sources).map(([key,value])=>[key,value.length])),beforeMs:old.milliseconds,afterMs:current.milliseconds,equivalent:true,snapshotSha256:createHash('sha256').update(JSON.stringify(current.snapshot)).digest('hex'),stats:current.snapshot.stats});
 console.log(JSON.stringify({name,zoom,beforeMs:old.milliseconds,afterMs:current.milliseconds,equivalent:true}));
}
fs.writeFileSync(option('--output'),JSON.stringify(report,null,2));
