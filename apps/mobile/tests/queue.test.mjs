import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const memory=new Map();let downloads=0,fail=false,cancelHook;
globalThis.__tileFS={documentDirectory:'memory://',EncodingType:{Base64:'base64'},makeDirectoryAsync:async()=>{},readAsStringAsync:async p=>{if(!memory.has(p))throw Error('missing');return memory.get(p)},writeAsStringAsync:async(p,t)=>memory.set(p,t),moveAsync:async({from,to})=>{memory.set(to,memory.get(from));memory.delete(from)},getInfoAsync:async p=>({exists:memory.has(p),size:memory.has(p)?Buffer.from(memory.get(p),'base64').length:0}),deleteAsync:async p=>{for(const key of memory.keys())if(key.startsWith(p))memory.delete(key)},downloadAsync:async(url,p)=>{downloads++;if(cancelHook){const hook=cancelHook;cancelHook=null;await hook()}if(fail)return {status:503};memory.set(p,'cGJm' );return{status:200}}};
let source=ts.transpileModule(fs.readFileSync(new URL('../src/storage.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace("import * as FS from 'expo-file-system/legacy';",'const FS=globalThis.__tileFS;').replace("'./tiles.mjs'",JSON.stringify(new URL('../src/tiles.mjs',import.meta.url).href));
const {TileStore,resetDevelopmentMapCache}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const meta={name:'test',bounds:[-79.49,37.88,-75.03,39.73],datasetId:'maryland-test',center:[-76.6122,39.2904],gridZoom:12,minZoom:12,maxZoom:12,tileUrl:'/tiles/{z}/{x}/{y}.pbf'};
let currentMeta=meta;
globalThis.fetch=async(url,{signal}={})=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>currentMeta};downloads++;if(cancelHook){const hook=cancelHook;cancelHook=null;await hook()}if(signal?.aborted)throw Error('aborted');if(fail)return{ok:false,status:503};return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('pbf').buffer}};
async function idle(store){for(let i=0;i<100&&store.running;i++)await new Promise(r=>setTimeout(r,1));assert.equal(store.running,false)}
test('queue caches a region, reuses files, persists state, and cancels mid-download',async()=>{
 const store=new TileStore('http://local',()=>{});await store.init();await store.toggle('1176/1561');await idle(store);assert.equal(store.regions['1176/1561'].status,'complete');assert.equal(downloads,1);assert.equal(store.regions['1176/1561'].bytes,3);assert.equal(await store.source('12/1176/1561'),'cGJm');
 await store.toggle('1176/1561');assert.equal(store.regions['1176/1561'],undefined);await store.toggle('1176/1561');await idle(store);assert.equal(downloads,1);
 delete store.regions['1176/1561'].bytes;await store.save();
 const restored=new TileStore('http://local',()=>{});await restored.init();assert.equal(restored.regions['1176/1561'].status,'complete');assert.equal(restored.regions['1176/1561'].bytes,3);assert.equal(downloads,1);
 cancelHook=()=>store.toggle('1175/1561');await store.toggle('1175/1561');await idle(store);assert.equal(store.regions['1175/1561'],undefined);assert.equal(memory.has(store.file('12/1175/1561')),false);
});

test('dataset replacement at same API isolates binary cache and clears saved selections',async()=>{
 const store=new TileStore('http://local',()=>{});await store.init();await store.toggle('1176/1561');await idle(store);const oldFile=store.file('12/1176/1561');assert.ok(memory.has(oldFile));const before=downloads;
 currentMeta={...meta,datasetId:'maryland-new-extract'};
 const replaced=new TileStore('http://local',()=>{});await replaced.init();assert.deepEqual(replaced.regions,{});assert.notEqual(replaced.file('12/1176/1561'),oldFile);assert.equal(await replaced.source('12/1176/1561'),'cGJm');assert.equal(downloads,before+1);assert.ok(memory.has(oldFile));
});

test('Expo reload clears all map servers and legacy tiles, preserves notes and GPS, and skips Fast Refresh',async()=>{delete globalThis.__topoMapCacheReset;memory.set('memory://topo-vectors-v2/old.pbf','old');memory.set('memory://topo-vectors-v2/cloud/dem.png','dem');memory.set('memory://map-notes.json','notes');memory.set('memory://gps-track.jsonl','gps');await resetDevelopmentMapCache();assert.ok(![...memory.keys()].some(p=>p.startsWith('memory://topo-vectors-v2/')));assert.equal(memory.get('memory://map-notes.json'),'notes');assert.equal(memory.get('memory://gps-track.jsonl'),'gps');memory.set('memory://topo-vectors-v2/new.pbf','new');await resetDevelopmentMapCache();assert.equal(memory.get('memory://topo-vectors-v2/new.pbf'),'new');delete globalThis.__topoMapCacheReset;});
