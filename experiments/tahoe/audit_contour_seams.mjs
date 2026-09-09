/** Offline seam audit of the actual bundled device contour worker.
 * Checks six Tahoe/SF parent boundaries at z12–15, including rough terrain and
 * both seam directions. Python uses the production Terrarium decoder. No API
 * calls, uploads, source edits or browser automation are performed.
 */
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';import {execFileSync} from 'node:child_process';import {Worker} from 'node:worker_threads';import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const args=process.argv.slice(2),option=name=>args[args.indexOf(name)+1];
if(!args.includes('--dem-root')||!args.includes('--output'))throw Error('Use --dem-root PATH/containing/12 --output report.json; all inputs are local.');
const demRoot=path.resolve(option('--dem-root')),output=path.resolve(option('--output')),decoded=new Map();
function dem(key){
 let data=decoded.get(key);if(data){decoded.delete(key);decoded.set(key,data);return data.slice()}
 const filename=path.join(demRoot,key+'.png');
 const decoder="import sys;sys.path.insert(0,sys.argv[1]);from national_dem import decode_png;from pathlib import Path;a=decode_png(Path(sys.argv[2]).read_bytes());assert a.shape==(1024,1024);sys.stdout.buffer.write(a.astype('<f4').tobytes())";
 const b=execFileSync(root+'/services/tiles/.venv/bin/python',['-c',decoder,root+'/services/tiles',filename],{maxBuffer:5*1024*1024,stdio:['ignore','pipe','pipe']});
 data=new Float32Array(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));decoded.set(key,data);while(decoded.size>24)decoded.delete(decoded.keys().next().value);return data.slice();
}
const req=createRequire(root+'/apps/mobile/package.json'),glReq=createRequire(req.resolve('maplibre-gl'));
const {VectorTile}=await import(glReq.resolve('@mapbox/vector-tile'));const {default:Pbf}=await import(glReq.resolve('pbf'));
const source=JSON.parse(fs.readFileSync(root+'/apps/mobile/src/terrainWorkerSource.ts','utf8').split('export const terrainWorkerSource=')[1].trim().replace(/;$/,''));
const worker=new Worker(`const {parentPort}=require('node:worker_threads');globalThis.self=globalThis;globalThis.postMessage=(m,t)=>parentPort.postMessage(m,t);parentPort.on('message',data=>globalThis.onmessage({data}));${source}`,{eval:true});
const pending=new Map(),demKeys=new Set();let sequence=0;
worker.on('error',e=>{for(const p of pending.values())p.reject(e)});
worker.on('message',m=>{if(m.type==='dem'){
 try{demKeys.add(m.key);const data=dem(m.key);worker.postMessage({type:'demResult',id:m.id,tile:{width:1024,height:1024,data}},[data.buffer])}catch(e){worker.postMessage({type:'demResult',id:m.id,error:String(e)})}
 }else if(m.type==='contourResult'){const p=pending.get(m.id);if(!p)return;pending.delete(m.id);m.error?p.reject(Error(m.error)):p.resolve({buffer:m.buffer,ms:m.ms})}});
worker.postMessage({type:'configure',maxZoom:12,minZoom:12});
const tile=(z,x,y)=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});worker.postMessage({type:'contour',id,z,x,y})});
function crossings(buffer,axis,edge){const layer=new VectorTile(new Pbf(new Uint8Array(buffer))).layers.contour,out=new Map();if(!layer)return out;
 for(let n=0;n<layer.length;n++){const f=layer.feature(n),height=f.properties.ele_ft;for(const line of f.loadGeometry())for(let i=1;i<line.length;i++){
  const p=line[i-1],q=line[i],a=axis==='x'?p.x:p.y,b=axis==='x'?q.x:q.y;if(a===b||!((a<=edge&&b>edge)||(b<=edge&&a>edge)))continue;
  const start=axis==='x'?p.y:p.x,end=axis==='x'?q.y:q.x,position=start+(end-start)*(edge-a)/(b-a);
  if(position<=2||position>=4094)continue;const list=out.get(height)||[];list.push(position);out.set(height,list);
 }}for(const list of out.values())list.sort((a,b)=>a-b);return out;}
const areas=[['south-tahoe',681,1566,'x'],['desolation',680,1566,'x'],['mount-rose',682,1560,'x'],['sf-coast',654,1582,'x'],['sf-hills',654,1584,'x'],['tahoe-south-edge',681,1566,'y']];
const rows=[];try{
 for(const [name,x,y,axis] of areas)for(const z of [12,13,14,15]){
  const s=2**(z-12),a=axis==='x'?[x*s+s-1,y*s+Math.floor(s/2)]:[x*s+Math.floor(s/2),y*s+s-1],b=axis==='x'?[a[0]+1,a[1]]:[a[0],a[1]+1];
  const left=await tile(z,...a),right=await tile(z,...b),edgeA=crossings(left.buffer,axis,4096),edgeB=crossings(right.buffer,axis,0),fail=[];let matches=0,max=0;
  for(const height of new Set([...edgeA.keys(),...edgeB.keys()])){const aa=edgeA.get(height)||[],bb=edgeB.get(height)||[];
   if(aa.length!==bb.length){fail.push({height,left:aa,right:bb});continue}
   for(let i=0;i<aa.length;i++){const delta=Math.abs(aa[i]-bb[i]);max=Math.max(max,delta);matches++;if(delta>2)fail.push({height,left:aa[i],right:bb[i],delta})}
  }
  rows.push({name,z,axis,a,b,matches,maxErrorTileUnits:max,failures:fail,leftMs:left.ms,rightMs:right.ms});console.log(name,z,matches,max.toFixed(4),fail.length);
 }
 const report={pairs:rows.length,matchedCrossings:rows.reduce((n,r)=>n+r.matches,0),maxErrorTileUnits:Math.max(...rows.map(r=>r.maxErrorTileUnits)),failurePairs:rows.filter(r=>r.failures.length).length,demKeys:[...demKeys].sort(),rows};fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify({...report,note:'Actual local 1024px DEMs, current bundled contour worker, z12–15 seam samples. Task timings include audit transport/decoding and are not phone benchmarks.'},null,2)+'\n');console.log(JSON.stringify({pairs:report.pairs,matchedCrossings:report.matchedCrossings,maxErrorTileUnits:report.maxErrorTileUnits,failurePairs:report.failurePairs,dems:demKeys.size}));
}finally{await worker.terminate()}
