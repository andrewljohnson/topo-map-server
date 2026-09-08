import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import {Worker} from 'node:worker_threads';import {createRequire} from 'node:module';
const req=createRequire(import.meta.url),glReq=createRequire(req.resolve('maplibre-gl'));
const {VectorTile}=await import(glReq.resolve('@mapbox/vector-tile'));const {default:Pbf}=await import(glReq.resolve('pbf'));
const source=JSON.parse(fs.readFileSync(new URL('../src/terrainWorkerSource.ts',import.meta.url),'utf8').split('export const terrainWorkerSource=')[1].trim().replace(/;$/,''));
test('offline worker contours use feet, stitch across tile edges, and survive transferring cached results',async()=>{
 const worker=new Worker(`const {parentPort}=require('node:worker_threads');globalThis.self=globalThis;globalThis.postMessage=(m,t)=>parentPort.postMessage(m,t);parentPort.on('message',data=>globalThis.onmessage({data}));${source}`,{eval:true});
 const pending=new Map();let sequence=0,demCount=0;
 worker.on('message',m=>{if(m.type==='dem'){demCount++;const [z,x,y]=m.key.split('/').map(Number),data=new Float32Array(512*512);for(let row=0;row<512;row++)for(let col=0;col<512;col++)data[row*512+col]=1000+((x-1373)*512+col)*.3+((y-3167)*512+row)*.2;worker.postMessage({type:'demResult',id:m.id,tile:{width:512,height:512,data}},[data.buffer]);}else if(m.type==='contourResult'){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error)):p.resolve(m.buffer)}});
 const tile=(x,y)=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});worker.postMessage({type:'contour',id,z:14,x,y})});
 try{
  const left=await tile(2746,6334),right=await tile(2747,6334),count=demCount,repeated=await tile(2746,6334);assert.deepEqual(Buffer.from(left),Buffer.from(repeated));assert.equal(demCount,count);
  const read=buffer=>{const layer=new VectorTile(new Pbf(new Uint8Array(buffer))).layers.contour;assert.ok(layer.length>0);return Array.from({length:layer.length},(_,i)=>layer.feature(i))};const a=read(left),b=read(right);
  for(const f of [...a,...b]){assert.equal(f.properties.ele_ft%20,0);assert.equal(f.properties.level,f.properties.ele_ft%100===0?1:0)}
  const crossings=(features,x)=>{const results=new Map();for(const f of features)for(const line of f.loadGeometry())for(let i=1;i<line.length;i++){const p=line[i-1],q=line[i];if((p.x<=x&&q.x>=x)||(p.x>=x&&q.x<=x)){if(p.x===q.x)continue;const y=p.y+(q.y-p.y)*(x-p.x)/(q.x-p.x);if(y>=0&&y<=4096)results.set(f.properties.ele_ft,y)}}return results};
  const edgeA=crossings(a,4096),edgeB=crossings(b,0);assert.ok(edgeA.size>3);for(const [height,y]of edgeA){assert.ok(edgeB.has(height));assert.ok(Math.abs(y-edgeB.get(height))<=2,'neighbor contours align within two MVT units')}
 }finally{await worker.terminate()}
});
test('1024 pixel z12 DEM generates detailed contours without requesting z13 DEM',async()=>{
 const worker=new Worker(`const {parentPort}=require('node:worker_threads');globalThis.self=globalThis;globalThis.postMessage=(m,t)=>parentPort.postMessage(m,t);parentPort.on('message',data=>globalThis.onmessage({data}));${source}`,{eval:true});
 const keys=[];let resolve,reject;
 worker.on('error',e=>reject?.(e));
 worker.on('message',m=>{if(m.type==='dem'){
  keys.push(m.key);const [z,x,y]=m.key.split('/').map(Number),data=new Float32Array(1024*1024);
  for(let row=0;row<1024;row++)for(let col=0;col<1024;col++)data[row*1024+col]=1000+((x-681)*1024+col)*.15+((y-1566)*1024+row)*.1;
  worker.postMessage({type:'demResult',id:m.id,tile:{width:1024,height:1024,data}},[data.buffer]);
 }else if(m.type==='contourResult'){m.error?reject(Error(m.error)):resolve(m.buffer)}});
 worker.postMessage({type:'configure',maxZoom:12,minZoom:12});
 try{for(const z of [12,14,15]){
  const data=await new Promise((yes,no)=>{resolve=yes;reject=no;worker.postMessage({type:'contour',id:z,z,x:681*2**(z-12),y:1566*2**(z-12)})});
  const layer=new VectorTile(new Pbf(new Uint8Array(data))).layers.contour;assert.ok(layer?.length>0);
  if(z>=14)for(let i=0;i<layer.length;i++)assert.equal(layer.feature(i).properties.ele_ft%20,0);
 }
 assert.ok(keys.length>0);assert.ok(keys.every(key=>key.startsWith('12/')),keys.join(','));
 }finally{await worker.terminate()}
});
