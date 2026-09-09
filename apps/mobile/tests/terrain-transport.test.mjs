import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const source=ts.transpileModule(fs.readFileSync(new URL('../src/terrainRuntime.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
test('worker receives an owned DEM buffer while GPU and cached consumers retain intact bytes',async()=>{
 let worker,loads=0;const protocols={},sent=[];
 const context=vm.createContext({exports:{},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Blob,AbortController,Worker:class{
  constructor(){worker=this}terminate(){}postMessage(message,transfer=[]){sent.push(structuredClone(message,{transfer}))}
 }});
 vm.runInContext(source,context);vm.runInContext(context.exports.terrainRuntimeScript,context);
 const original=new Uint8Array([137,80,78,71,13,10,26,10]).buffer;
 const terrain=context.installDeviceTerrain({addProtocol(name,fn){protocols[name]=fn},removeProtocol(){}},{sources:{},layers:[]},{maxZoom:12,minZoom:12},async()=>{loads++;return original},'');
 try{
  await worker.onmessage({data:{type:'dem',id:1,key:'12/681/1566',decodeInWorker:true}});
  const first=sent.find(m=>m.type==='demResult');assert.deepEqual([...new Uint8Array(first.buffer)],[137,80,78,71,13,10,26,10]);
  const gpu=await protocols.topodem({url:'topodem://12/681/1566'},new AbortController());
  assert.equal(original.byteLength,8);assert.equal(gpu.data.byteLength,8);assert.equal(loads,1);
  await worker.onmessage({data:{type:'dem',id:2,key:'12/681/1566',decodeInWorker:true}});
  assert.equal(sent.filter(m=>m.type==='demResult')[1].buffer.byteLength,8);assert.equal(loads,1);
 }finally{terrain.dispose()}
});
test('DEM setup preserves the canonical land-cover fade',async()=>{
 const {createStyle}=await import('../src/style.mjs');
 const context=vm.createContext({exports:{},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Blob,AbortController,Worker:class{postMessage(){}terminate(){}}});
 vm.runInContext(source,context);vm.runInContext(context.exports.terrainRuntimeScript,context);
 const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'base',undefined,undefined,undefined,undefined,'cover');
 const before=structuredClone(style.layers.find(l=>l.id==='nlcd-forest').paint['fill-opacity']);
 const runtime=context.installDeviceTerrain({addProtocol(){},removeProtocol(){}},style,{maxZoom:12,minZoom:12},async()=>new ArrayBuffer(0),'');
 try{assert.deepEqual(style.layers.find(l=>l.id==='nlcd-forest').paint['fill-opacity'],before);assert.ok(before.at(-1)<.15)}finally{runtime.dispose()}
});
test('bridge decks stay above water and surface roads with regional DEM sources',async()=>{
 const {createStyle}=await import('../src/style.mjs');
 for(const regions of [undefined,[[-123,37,-122,38],[-121,38,-120,40]]]){
  const context=vm.createContext({exports:{},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Blob,AbortController,Worker:class{postMessage(){}terminate(){}}});vm.runInContext(source,context);vm.runInContext(context.exports.terrainRuntimeScript,context);
  const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:12,combined:true,overviewMaxZoom:3},'base');
  const runtime=context.installDeviceTerrain({addProtocol(){},removeProtocol(){}},style,{maxZoom:12,minZoom:12,renderBounds:regions},async()=>new ArrayBuffer(0),'');
  try{const index=id=>style.layers.findIndex(l=>l.id===id);assert.ok(index('roads-highway-bridge')>index('water'),'highway bridge must not disappear beneath water fill');assert.ok(index('roads-highway-bridge')>index('roads-highway'),'elevated deck must cross above surface roads');assert.ok(index('roads-highway-casing-bridge')<index('roads-highway-bridge'),'casing stays below deck');assert.ok(index('roads-highway-bridge')<index('road-labels'),'road names stay above decks')}finally{runtime.dispose()}
 }
});

function workerHarness(load=async()=>new ArrayBuffer(8),failReplay=false){
 const workers=[],protocols={};
 const context=vm.createContext({exports:{},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Blob,AbortController,Worker:class{
  constructor(){this.messages=[];this.terminated=false;workers.push(this)}terminate(){this.terminated=true}postMessage(m){if(failReplay&&workers.indexOf(this)===1&&m.type==='contour')throw Error('Worker send failed');this.messages.push(m)}
 }});vm.runInContext(source,context);vm.runInContext(context.exports.terrainRuntimeScript,context);
 const runtime=context.installDeviceTerrain({addProtocol(k,f){protocols[k]=f},removeProtocol(){}},{sources:{},layers:[]},{minZoom:12,maxZoom:12},load,'worker');
 return {workers,protocols,runtime};
}
test('a terrain worker crash recovers pending contours once and ignores the retired worker',async()=>{
 const {workers,protocols,runtime}=workerHarness();
 try{
  const pending=protocols.topocontour({url:'topocontour://14/2724/6264'},new AbortController());
  // Attach a rejection handler immediately; the pre-fix implementation rejects here.
  const outcome=pending.then(r=>({result:r}),e=>({error:e}));
  const first=workers[0],job=first.messages.find(m=>m.type==='contour');let handled=false;first.onerror({message:'worker crash',preventDefault(){handled=true}});assert.equal(handled,true);
  assert.equal(workers.length,2,'one replacement worker should start');assert.equal(first.terminated,true);
  const replacement=workers[1];assert.equal(replacement.messages[0].type,'configure');assert.equal(replacement.messages[0].maxZoom,12);
  assert.ok(replacement.messages.some(m=>m.type==='contour'&&m.id===job.id));
  await first.onmessage({data:{type:'contourResult',id:job.id,buffer:new Uint8Array([1]).buffer,ms:1}});
  await replacement.onmessage({data:{type:'contourResult',id:job.id,buffer:new Uint8Array([2]).buffer,ms:1}});
  const result=await outcome;assert.equal(result.error,undefined);assert.deepEqual([...new Uint8Array(result.result.data)],[2]);
 }finally{runtime.dispose()}
});
test('terrain recovery is bounded and failed or cancelled jobs never hang or restart again',async()=>{
 const {workers,protocols,runtime}=workerHarness();
 try{
  const cancelled=new AbortController();const cancelledJob=protocols.topocontour({url:'topocontour://14/2724/6264'},cancelled);const cancelOutcome=assert.rejects(cancelledJob,/Cancelled/);cancelled.abort();await cancelOutcome;
  workers[0].onerror({message:'first crash'});assert.equal(workers.length,2);assert.equal(workers[1].messages.filter(m=>m.type==='contour').length,0);
  const pending=protocols.topocontour({url:'topocontour://14/2725/6264'},new AbortController());const rejected=assert.rejects(pending,/Terrain worker/);
  workers[1].onerror({message:'second crash'});await rejected;assert.equal(workers.length,2);
  const next=protocols.topocontour({url:'topocontour://14/2726/6264'},new AbortController());await assert.rejects(next,/Terrain worker/);assert.equal(workers.length,2);
 }finally{runtime.dispose()}
});

test('a replacement worker that cannot accept replay fails closed without stranding later requests',async()=>{
 const {workers,protocols,runtime}=workerHarness(undefined,true);
 try{
  const pending=protocols.topocontour({url:'topocontour://14/2724/6264'},new AbortController());const rejected=assert.rejects(pending,/Terrain worker/);
  workers[0].onerror({message:'crash'});await rejected;assert.equal(workers[1].terminated,true);assert.equal(runtime.stats.worker,false);
  await assert.rejects(protocols.topocontour({url:'topocontour://14/2725/6264'},new AbortController()),/Terrain worker/);
 }finally{runtime.dispose()}
});
test('a retired worker cannot deliver DEM bytes to the replacement reusing its request ID',async()=>{
 let finishOld;const {workers,runtime}=workerHarness(key=>key==='12/1/1'?new Promise(resolve=>{finishOld=resolve}):Promise.resolve(new Uint8Array([2]).buffer));
 try{
  const old=workers[0],inFlight=old.onmessage({data:{type:'dem',id:1,key:'12/1/1',decodeInWorker:true}});
  old.onerror({message:'crash'});const current=workers[1];
  await current.onmessage({data:{type:'dem',id:1,key:'12/2/2',decodeInWorker:true}});
  finishOld(new Uint8Array([1]).buffer);await inFlight;
  const replies=current.messages.filter(m=>m.type==='demResult');assert.equal(replies.length,1);assert.deepEqual([...new Uint8Array(replies[0].buffer)],[2]);
  assert.equal(old.messages.filter(m=>m.type==='demResult').length,0);
 }finally{runtime.dispose()}
});
