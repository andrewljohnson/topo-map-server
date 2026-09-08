import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const memory=new Map(),tasks=[];
const meta={name:'test',datasetId:'background-v1',bounds:[-180,-85,180,85],center:[0,0],gridZoom:12,minZoom:6,maxZoom:14,tileUrl:'/tiles/{z}/{x}/{y}.pbf',batchUrl:'/tile-batch',batchSize:8};
globalThis.__tileFS={documentDirectory:'memory://',EncodingType:{Base64:'base64'},FileSystemSessionType:{BACKGROUND:0},
 makeDirectoryAsync:async()=>{},getInfoAsync:async p=>({exists:memory.has(p),size:3}),
 readAsStringAsync:async p=>{if(!memory.has(p))throw Error('missing');return memory.get(p)},
 writeAsStringAsync:async(p,s)=>memory.set(p,s),moveAsync:async({from,to})=>{memory.set(to,memory.get(from));memory.delete(from)},deleteAsync:async p=>memory.delete(p),
 createDownloadResumable(url,path,options){
  assert.equal(options.sessionType,0);
  let done,fail;const promise=new Promise((a,b)=>{done=a;fail=b});
  const query=new URL(url).searchParams;
  const keys=query.get('tiles').split(',');assert.ok(keys.length<=8);
  const task={keys,path,cancelled:false,finish(){memory.set(path,JSON.stringify({datasetId:query.get('datasetId'),tiles:keys.map(key=>({key,data:'cGJm'}))}));done({status:200})}};
  tasks.push(task);return{downloadAsync:()=>promise,cancelAsync:async()=>{task.cancelled=true;fail(Error('Cancelled'))}};
 }
};
globalThis.fetch=async url=>{assert.ok(url.endsWith('/metadata'),'offline transfers must not use fetch');return{ok:true,json:async()=>meta}};
const source=ts.transpileModule(fs.readFileSync(new URL('../src/storage.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace("'./abortable.mjs'",JSON.stringify(new URL('../src/abortable.mjs',import.meta.url).href)).replace("import * as FS from 'expo-file-system/legacy';",'const FS=globalThis.__tileFS;').replace("'./tiles.mjs'",JSON.stringify(new URL('../src/tiles.mjs',import.meta.url).href));
const {TileStore}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const wait=async predicate=>{for(let i=0;i<300&&!predicate();i++)await new Promise(r=>setTimeout(r,5));assert.ok(predicate())};
test('all selected regions reach native queue before any completion; suspend-time JS timeout cannot cancel them',async()=>{
 const store=new TileStore('http://native',()=>{},{requestTimeoutMs:1});store.setForeground(false);await store.init();
 await store.toggle('1176/1561');await store.toggle('1178/1561');
 const expected=new Set([...store.regionTiles('1176/1561'),...store.regionTiles('1178/1561')]).size;
 await wait(()=>tasks.reduce((n,t)=>n+t.keys.length,0)===expected);
 assert.ok(tasks.length>2);assert.ok(tasks.every(t=>!t.cancelled));
 const journal=JSON.parse(memory.get('memory://topo-vectors-v2/http%3A%2F%2Fnative/state.json')).nativePending;
 assert.equal(Object.keys(journal).length,tasks.length,'persisted before native starts');
 for(const task of tasks)task.finish();
 await wait(()=>!store.running);
 assert.ok(Object.values(store.regions).every(r=>r.status==='complete'&&r.done===r.total));
 assert.equal(Object.keys(store.nativePending).length,0);
});
test('removing a region cancels its native transfers and does not install tiles',async()=>{
 memory.clear();tasks.length=0;const store=new TileStore('http://cancel-native',()=>{});store.setForeground(false);await store.init();await store.toggle('1176/1561');await wait(()=>tasks.length===4);await store.toggle('1176/1561');await wait(()=>!store.running);assert.ok(tasks.every(t=>t.cancelled));assert.deepEqual(store.regions,{});assert.ok(![...memory.keys()].some(k=>k.endsWith('.pbf')));
});
test('relaunch imports completed native envelopes, rejects stale datasets and unrequested tiles',async()=>{
 memory.clear();tasks.length=0;
 const path='memory://topo-vectors-v2/http%3A%2F%2Frecover/batch-recovery.json',key='osm/12/1176/1561';
 memory.set(path,JSON.stringify({datasetId:meta.datasetId,tiles:[{key:'12/1176/1561',data:'cGJm'},{key:'12/1/1',data:'YmFk'}]}));
 memory.set('memory://topo-vectors-v2/http%3A%2F%2Frecover/state.json',JSON.stringify({api:'http://recover',meta,regions:{'1176/1561':{status:'downloading',done:0,total:27}},nativePending:{[path]:{datasetId:meta.datasetId,keys:[key]}}}));
 const store=new TileStore('http://recover',()=>{});store.setForeground(false);await store.init();assert.ok(memory.has(store.file(key)));assert.ok(!memory.has(store.file('osm/12/1/1')));
 await wait(()=>tasks.reduce((n,t)=>n+t.keys.length,0)===26);
 for(const task of tasks)task.finish();await wait(()=>!store.running);assert.equal(store.regions['1176/1561'].status,'complete');
});

test('foreground bounds native batches and promotes a visible tile out of a stalled batch',async()=>{
 memory.clear();tasks.length=0;const store=new TileStore('http://foreground',()=>{});await store.init();await store.toggle('1176/1561');await wait(()=>tasks.length===2);
 await new Promise(r=>setTimeout(r,30));assert.equal(tasks.length,2,'foreground never hands an unlimited queue to native');
 const key=tasks[0].keys[0];let requested=false;globalThis.fetch=async url=>{requested=true;assert.ok(url.includes('/tiles/'));return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('visible').buffer}};
 const content=await store.source('osm/'+key);assert.equal(Buffer.from(content,'base64').toString(),'visible');assert.ok(requested);assert.ok(tasks.slice(0,2).every(t=>t.cancelled));
 assert.notEqual(store.regions['1176/1561'].status,'error','yielding preserves the selected download');
 store.setForeground(false);await wait(()=>tasks.filter(t=>!t.cancelled).reduce((n,t)=>n+t.keys.length,0)===26);
 for(const task of tasks.filter(t=>!t.cancelled))task.finish();await wait(()=>!store.running);assert.equal(store.regions['1176/1561'].status,'complete');
});
