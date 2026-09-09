/** Reproducible long-pan memory probe; no source/network/user data access. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Worker} from 'node:worker_threads';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const args=process.argv.slice(2),option=name=>args[args.indexOf(name)+1];
if(!args.includes('--output'))throw Error('Use node --expose-gc ... --output report.json [--worker-source generated.ts].');
const source=JSON.parse(fs.readFileSync(args.includes('--worker-source')?option('--worker-source'):root+'/apps/mobile/src/terrainWorkerSource.ts','utf8').split('export const terrainWorkerSource=')[1].trim().replace(/;$/,''));
const worker=new Worker(`const {parentPort}=require('node:worker_threads');globalThis.self=globalThis;globalThis.postMessage=(m,t)=>parentPort.postMessage(m,t);parentPort.on('message',data=>{if(data.type==='memory'){globalThis.gc?.();parentPort.postMessage({type:'memory',id:data.id,gc:typeof globalThis.gc==='function',memory:process.memoryUsage()});return;}globalThis.onmessage({data})});${source}`,{eval:true});
const pending=new Map();let sequence=0,requests=0;
worker.on('error',e=>{for(const p of pending.values())p.reject(e)});
worker.on('message',m=>{
 if(m.type==='dem'){
  requests++;const data=new Float32Array(1024*1024);data.fill(1000);
  worker.postMessage({type:'demResult',id:m.id,tile:{width:1024,height:1024,data}},[data.buffer]);
 }else if(m.type==='contourResult'||m.type==='memory'){
  const p=pending.get(m.id);if(!p)return;pending.delete(m.id);m.error?p.reject(Error(m.error)):p.resolve(m);
 }
});
const send=m=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});worker.postMessage({...m,id})});
worker.postMessage({type:'configure',maxZoom:12,minZoom:12});
const samples=[];
try{
 samples.push({jobs:0,...await send({type:'memory'})});
 for(let i=0;i<48;i++){
  await send({type:'contour',z:12,x:600+i*3,y:1500});
  if((i+1)%8===0){const row={jobs:i+1,requests,...await send({type:'memory'})};samples.push(row);console.log(JSON.stringify(row));}
 }
 fs.writeFileSync(option('--output'),JSON.stringify({note:'Synthetic flat 1024px DEMs through actual bundled contour worker; transferred arrays; Node GC memory, not a phone measurement.',samples},null,2)+'\n');
}finally{await worker.terminate()}
