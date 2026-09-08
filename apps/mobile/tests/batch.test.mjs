import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import ts from 'typescript';import {cellTiles} from '../src/tiles.mjs';
const memory=new Map();let activeDisk=0,maxDisk=0;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
globalThis.__tileFS={documentDirectory:'memory://',EncodingType:{Base64:'base64'},makeDirectoryAsync:async()=>{},readAsStringAsync:async p=>{if(!memory.has(p))throw Error('missing');return memory.get(p)},writeAsStringAsync:async(p,t)=>{activeDisk++;maxDisk=Math.max(maxDisk,activeDisk);await delay(1);memory.set(p,t);activeDisk--},moveAsync:async({from,to})=>{memory.set(to,memory.get(from));memory.delete(from)},getInfoAsync:async p=>({exists:memory.has(p),size:memory.has(p)?Buffer.from(memory.get(p),'base64').length:0}),deleteAsync:async p=>{memory.delete(p)},downloadAsync:async()=>{throw Error('Expected batch API')}};
let source=ts.transpileModule(fs.readFileSync(new URL('../src/storage.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace("import * as FS from 'expo-file-system/legacy';",'const FS=globalThis.__tileFS;').replace("'./tiles.mjs'",JSON.stringify(new URL('../src/tiles.mjs',import.meta.url).href));const {TileStore}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const meta={name:'Maryland',datasetId:'md-batch',bounds:[-79.49,37.88,-75.03,39.73],center:[-76.6122,39.2904],gridZoom:12,minZoom:6,maxZoom:14,tileUrl:'/tiles/{z}/{x}/{y}.pbf',batchUrl:'/tile-batch',batchSize:8};const cell='1176/1561',keys=cellTiles(cell,meta);
function network({partial=false}={}){let active=0,max=0,aborted=0;const calls=[],counts=new Map();globalThis.fetch=async(url,options)=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>meta};const requested=new URL(url).searchParams.get('tiles').split(',');calls.push(requested);active++;max=Math.max(max,active);try{await new Promise((resolve,reject)=>{const timer=setTimeout(resolve,25);options.signal.addEventListener('abort',()=>{aborted++;clearTimeout(timer);reject(Error('aborted'))},{once:true})});const tiles=[];for(const key of requested){counts.set(key,(counts.get(key)||0)+1);if(partial&&key===keys[0]&&counts.get(key)===1)continue;tiles.push({key,data:'dmVjdG9y'})}return{ok:true,json:async()=>({datasetId:meta.datasetId,tiles,errors:[]})}}finally{active--}};return{calls,counts,get max(){return max},get aborted(){return aborted}}}
async function idle(store){for(let i=0;i<1000&&(store.running||store.requests.size||store.workers||store.interactiveWorkers);i++)await delay(5);assert.equal(store.running,false);assert.equal(store.requests.size,0);assert.equal(store.workers,0);assert.equal(store.interactiveWorkers,0)}
test('27 tiles use four batches, max two network requests; cache reuse and interactive dedup',async()=>{memory.clear();const net=network();const store=new TileStore('http://batch1',()=>{},{retryDelayMs:1,progressMs:1});await store.init();await store.toggle(cell);await idle(store);const interactive=store.source(keys[0]);assert.equal(await interactive,'dmVjdG9y');assert.equal(keys.length,27);assert.equal(net.calls.length,4);assert.equal(net.max,2);assert.ok(net.calls.every(c=>c.length<=8));assert.ok([...net.counts.values()].every(n=>n===1));assert.equal(store.regions[cell].done,27);await store.toggle(cell);await store.toggle(cell);await idle(store);assert.equal(net.calls.length,4);assert.ok(maxDisk<=3,'at most two tile writers plus serialized metadata writer');});
test('partial batch successes persist and only omitted tile retries',async()=>{memory.clear();const net=network({partial:true});const store=new TileStore('http://batch2',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);assert.equal(store.regions[cell].status,'complete');assert.equal(net.counts.get(keys[0]),2);assert.ok(keys.slice(1).every(k=>net.counts.get(k)===1));});
test('cancelling stops scheduled chunks and aborts requests; saved queue resumes',async()=>{memory.clear();const net=network();const store=new TileStore('http://batch3',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await delay(15);await store.toggle(cell);await idle(store);assert.equal(store.regions[cell],undefined);assert.ok(net.calls.length<=2);assert.ok(net.aborted>0);memory.set('memory://topo-vectors-v2/http%3A%2F%2Fbatch3/state.json',JSON.stringify({api:'http://batch3',meta,regions:{[cell]:{status:'downloading',done:5,total:27}}}));const resumed=new TileStore('http://batch3',()=>{},{retryDelayMs:1});await resumed.init();await idle(resumed);assert.equal(resumed.regions[cell].status,'complete');assert.equal(resumed.regions[cell].done,27);});
test('older server fallback downloads at most two individual tiles concurrently',async()=>{memory.clear();let active=0,max=0,count=0;globalThis.fetch=async(url)=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>({...meta,batchUrl:undefined})};active++;max=Math.max(max,active);count++;await delay(5);active--;return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('vector').buffer}};const store=new TileStore('http://legacy',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);assert.equal(store.regions[cell].status,'complete');assert.equal(count,27);assert.equal(max,2)});

test('fresh viewport tiles use two direct slots while offline batches are blocked',async()=>{
 memory.clear();let offline=0,direct=0,maxDirect=0,maxTotal=0;const releases=[];
 globalThis.fetch=async(url)=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>meta};if(!url.includes('tile-batch')){direct++;maxDirect=Math.max(maxDirect,direct);maxTotal=Math.max(maxTotal,offline+direct);await delay(10);direct--;return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('vector').buffer}}offline++;maxTotal=Math.max(maxTotal,offline+direct);const requested=new URL(url).searchParams.get('tiles').split(',');await new Promise(resolve=>releases.push(resolve));offline--;return{ok:true,json:async()=>({datasetId:meta.datasetId,tiles:requested.map(key=>({key,data:'dmVjdG9y'}))})}};
 globalThis.__tileFS.downloadAsync=async(url,path)=>{direct++;maxDirect=Math.max(maxDirect,direct);maxTotal=Math.max(maxTotal,offline+direct);await delay(10);memory.set(path,'dmVjdG9y');direct--;return{status:200}};
 const store=new TileStore('http://priority',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await delay(20);assert.equal(offline,2);
 const results=await Promise.all(['14/4800/6200','14/4801/6200','14/4802/6200'].map(key=>store.source(key)));
 assert.deepEqual(results,['dmVjdG9y','dmVjdG9y','dmVjdG9y']);assert.equal(offline,2,'offline requests remain blocked when interactive work completes');assert.equal(maxDirect,2);assert.equal(maxTotal,4);
 // Cancel the region and release mocked batches so the test leaves no work behind.
 await store.toggle(cell);for(const release of releases)release();await idle(store);
});
test('composed downloads group separate tilesets, work offline, and retain OSM cache when only contours change',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},contours:{...meta,datasetId:'contours-v1',minZoom:11,tileUrl:'/contours/{z}/{x}/{y}.pbf?datasetId=contours-v1',batchUrl:'/contour-batch'}}};
 const calls=[];globalThis.fetch=async(url)=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};const parsed=new URL(url),name=parsed.pathname==='/contour-batch'?'contours':'osm',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');assert.equal(parsed.searchParams.get('datasetId'),set.datasetId);calls.push({name,keys:requested});return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:name==='osm'?'b3Nt':'Y29udG91cnM='}))})}};
 const store=new TileStore('http://composition',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);
 assert.equal(store.regions[cell].total,49);assert.equal(store.regions[cell].done,49);assert.equal(store.regions[cell].status,'complete');assert.equal(calls.filter(c=>c.name==='osm').length,4);assert.equal(calls.filter(c=>c.name==='contours').length,3);assert.ok(calls.filter(c=>c.name==='contours').flatMap(c=>c.keys).every(k=>Number(k.split('/')[0])>=11));
 const shared=keys.find(k=>k.startsWith('12/'));assert.notEqual(store.file('osm/'+shared),store.file('contours/'+shared));assert.equal(await store.source('osm/'+shared),'b3Nt');assert.equal(await store.source('contours/'+shared),'Y29udG91cnM=');
 const osmPath=store.file('osm/'+shared),oldContourPath=store.file('contours/'+shared),before=calls.length;current={...current,tilesets:{...current.tilesets,contours:{...current.tilesets.contours,datasetId:'contours-v2',tileUrl:'/contours/{z}/{x}/{y}.pbf?datasetId=contours-v2'}}};
 const updated=new TileStore('http://composition',()=>{},{retryDelayMs:1});await updated.init();assert.deepEqual(updated.regions,{});assert.equal(updated.file('osm/'+shared),osmPath);assert.notEqual(updated.file('contours/'+shared),oldContourPath);await updated.toggle(cell);await idle(updated);assert.equal(updated.regions[cell].status,'complete');assert.ok(calls.slice(before).every(c=>c.name==='contours'));assert.equal(calls.length-before,3);
 globalThis.fetch=async()=>{throw Error('offline')};globalThis.__tileFS.downloadAsync=async()=>{throw Error('offline')};const offline=new TileStore('http://composition',()=>{});await offline.init();assert.equal(offline.regions[cell].status,'complete');assert.equal(await offline.source('osm/'+shared),'b3Nt');assert.equal(await offline.source('contours/'+shared),'Y29udG91cnM=');
});

test('adding nationwide amenities upgrades saved regions with only new tiles and works offline',async()=>{
 memory.clear();const calls=[];let current={...meta,tilesets:{osm:{...meta},contours:{...meta,datasetId:'contours-v1',minZoom:11,tileUrl:'/contours/{z}/{x}/{y}.pbf',batchUrl:'/contour-batch'}}};
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=({'/tile-batch':'osm','/contour-batch':'contours','/amenity-batch':'amenities'})[parsed.pathname],set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');
  calls.push({name,keys:requested});assert.equal(parsed.searchParams.get('datasetId'),set.datasetId);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(name).toString('base64')}))})};
 };
 const store=new TileStore('http://additive',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);
 const previousBytes=store.regions[cell].bytes,before=calls.length,shared=keys.find(k=>k.startsWith('12/')),osmPath=store.file('osm/'+shared),contourPath=store.file('contours/'+shared);
 current={...current,tilesets:{...current.tilesets,amenities:{...meta,datasetId:'amenities-v1',minZoom:10,tileUrl:'/amenities/{z}/{x}/{y}.pbf',batchUrl:'/amenity-batch'}}};
 const upgraded=new TileStore('http://additive',()=>{},{retryDelayMs:1});await upgraded.init();assert.ok(upgraded.regions[cell],'saved selection survives source addition');await idle(upgraded);
 assert.equal(upgraded.regions[cell].status,'complete');assert.equal(upgraded.regions[cell].total,72);assert.equal(upgraded.regions[cell].done,72);assert.equal(upgraded.regions[cell].bytes,previousBytes+23*9);
 assert.equal(upgraded.file('osm/'+shared),osmPath);assert.equal(upgraded.file('contours/'+shared),contourPath);assert.notEqual(upgraded.file('amenities/'+shared),contourPath);
 assert.equal(calls.length-before,3);assert.ok(calls.slice(before).every(c=>c.name==='amenities'&&c.keys.length<=8));
 globalThis.fetch=async()=>{throw Error('offline')};globalThis.__tileFS.downloadAsync=async()=>{throw Error('offline')};
 const offline=new TileStore('http://additive',()=>{});await offline.init();assert.equal(offline.regions[cell].status,'complete');
 for(const name of ['osm','contours','amenities'])assert.equal(Buffer.from(await offline.source(name+'/'+shared),'base64').toString(),name);
});
test('amenity batch failures leave a retryable error while preserving cached basemap',async()=>{
 memory.clear();const current={...meta,minZoom:12,maxZoom:12,tilesets:{osm:{...meta,minZoom:12,maxZoom:12},amenities:{...meta,datasetId:'amenities-fail',minZoom:12,maxZoom:12,tileUrl:'/amenities/{z}/{x}/{y}.pbf',batchUrl:'/amenity-batch'}}};
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  if(url.includes('/amenity-batch'))return{ok:false,status:503};
  return{ok:true,json:async()=>({datasetId:meta.datasetId,tiles:[{key:'12/'+cell,data:'b3Nt'}]})};
 };
 const store=new TileStore('http://amenity-error',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);
 assert.equal(store.regions[cell].status,'error');assert.match(store.regions[cell].error,/503/);assert.equal(store.regions[cell].done,1);assert.equal(await store.source('osm/12/'+cell),'b3Nt');
});

test('adding detailed boundaries upgrades saved regions with only new tiles and works offline',async()=>{
 memory.clear();const calls=[];let current={...meta,tilesets:{osm:{...meta},contours:{...meta,datasetId:'contours-v1',minZoom:11,tileUrl:'/contours/{z}/{x}/{y}.pbf',batchUrl:'/contour-batch'},amenities:{...meta,datasetId:'amenities-v1',minZoom:10,tileUrl:'/amenities/{z}/{x}/{y}.pbf',batchUrl:'/amenity-batch'}}};
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=({'/tile-batch':'osm','/contour-batch':'contours','/amenity-batch':'amenities','/boundary-batch':'boundaries'})[parsed.pathname],set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');
  calls.push({name,keys:requested});assert.equal(parsed.searchParams.get('datasetId'),set.datasetId);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(name).toString('base64')}))})};
 };
 const store=new TileStore('http://boundary-additive',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);
 const previousBytes=store.regions[cell].bytes,before=calls.length,shared=keys.find(k=>k.startsWith('12/')),osmPath=store.file('osm/'+shared),contourPath=store.file('contours/'+shared);
 current={...current,tilesets:{...current.tilesets,boundaries:{...meta,datasetId:'boundaries-v1',minZoom:8,tileUrl:'/boundaries/{z}/{x}/{y}.pbf',batchUrl:'/boundary-batch'}}};
 const upgraded=new TileStore('http://boundary-additive',()=>{},{retryDelayMs:1});await upgraded.init();assert.ok(upgraded.regions[cell],'saved selection survives source addition');await idle(upgraded);
 assert.equal(upgraded.regions[cell].status,'complete');assert.equal(upgraded.regions[cell].total,97);assert.equal(upgraded.regions[cell].done,97);assert.equal(upgraded.regions[cell].bytes,previousBytes+25*10);
 assert.equal(upgraded.file('osm/'+shared),osmPath);assert.equal(upgraded.file('contours/'+shared),contourPath);assert.notEqual(upgraded.file('boundaries/'+shared),contourPath);
 assert.equal(calls.length-before,4);assert.ok(calls.slice(before).every(c=>c.name==='boundaries'&&c.keys.length<=8));
 globalThis.fetch=async()=>{throw Error('offline')};globalThis.__tileFS.downloadAsync=async()=>{throw Error('offline')};
 const offline=new TileStore('http://boundary-additive',()=>{});await offline.init();assert.equal(offline.regions[cell].status,'complete');
 for(const name of ['osm','contours','amenities','boundaries'])assert.equal(Buffer.from(await offline.source(name+'/'+shared),'base64').toString(),name);
});

test('stalled overlays cannot consume terrain slots and viewport cancellation aborts their network requests',async()=>{
 memory.clear();let alive=true,aborted=0;const started=[];
 const current={...meta,tilesets:Object.fromEntries(['osm','contours','amenities','boundaries'].map(name=>[name,{...meta,datasetId:name,tileUrl:`/${name}/{z}/{x}/{y}.pbf` }]))};
 globalThis.fetch=async(url,{signal}={})=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};started.push(url);if(/amenities|boundaries/.test(url))return new Promise((resolve,reject)=>{signal.addEventListener('abort',()=>{aborted++;reject(Error('aborted'))},{once:true})});return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('vector').buffer}};
 const store=new TileStore('http://overlay-stall',()=>{});await store.init();
 const overlays=['amenities','boundaries'].map(name=>store.source(name+'/14/4800/6200',()=>alive).catch(e=>e.message));await delay(20);
 assert.equal(started.length,2);assert.deepEqual(await Promise.all(['osm','contours'].map(name=>store.source(name+'/14/4800/6200'))),['dmVjdG9y','dmVjdG9y']);
 alive=false;store.cancelUnused();assert.deepEqual(await Promise.all(overlays),['aborted','aborted']);await idle(store);assert.equal(aborted,2);
});

test('direct request timeout aborts the transport and releases slots for later tiles',async()=>{
 memory.clear();let aborted=0;
 globalThis.fetch=async(url,{signal}={})=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>meta};if(url.includes('/4800/'))return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>{aborted++;reject(Error('aborted'))},{once:true}));return{ok:true,arrayBuffer:async()=>new Uint8Array([0,255,127,2]).buffer}};
 const store=new TileStore('http://timeout',()=>{},{requestTimeoutMs:30});await store.init();
 const stuck=store.source('14/4800/6200').catch(e=>e.message);assert.equal(await stuck,'aborted');assert.equal(aborted,1);assert.equal(await store.source('14/4801/6200'),Buffer.from([0,255,127,2]).toString('base64'));await idle(store);
});

test('viewport promotes a queued offline tile and keeps shared owners alive',async()=>{
 memory.clear();let direct=0;const releases=[];
 globalThis.fetch=async(url,{signal}={})=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>meta};if(!url.includes('tile-batch')){direct++;return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('vector').buffer}}const requested=new URL(url).searchParams.get('tiles').split(',');await new Promise(resolve=>releases.push(resolve));return{ok:true,json:async()=>({datasetId:meta.datasetId,tiles:requested.map(key=>({key,data:'dmVjdG9y'}))})}};
 const store=new TileStore('http://promotion',()=>{});await store.init();await store.toggle(cell);await delay(20);assert.equal(releases.length,2);
 assert.equal(await store.source(keys.at(-1)),'dmVjdG9y');assert.equal(direct,1,'queued offline tile uses reserved viewport lane');await store.toggle(cell);for(const release of releases)release();await idle(store);
});

test('stream tiles use their own bounded lane and remain available offline',async()=>{
 memory.clear();let calls=0;const current={...meta,tilesets:{osm:{...meta},waterways:{...meta,datasetId:'streams-v1',tileUrl:'/waterways/{z}/{x}/{y}.pbf'}}};
 globalThis.fetch=async url=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};calls++;assert.ok(url.includes('/waterways/'));return{ok:true,arrayBuffer:async()=>new TextEncoder().encode('stream flags').buffer}};
 const store=new TileStore('http://streams',()=>{});await store.init();assert.equal(await store.source('waterways/14/4800/6200'),Buffer.from('stream flags').toString('base64'));await idle(store);
 globalThis.fetch=async()=>{throw Error('offline')};assert.equal(await store.source('waterways/14/4800/6200'),Buffer.from('stream flags').toString('base64'));assert.equal(calls,1);
});

test('new base sources upgrade existing saved maps in batches and work offline',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':parsed.pathname.slice(1,-6);
  const requested=parsed.searchParams.get('tiles').split(','),set=current.tilesets[name];
  assert.ok(set);assert.ok(requested.length<=8);calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(name).toString('base64')}))})};
 };
 const store=new TileStore('http://new-base',()=>{});await store.init();await store.toggle(cell);await idle(store);
 const before=calls.length;
 for(const [name,minZoom]of [['landcover',6],['trails',5],['recreation',10]])current.tilesets[name]={...meta,datasetId:name+'-v1',minZoom,tileUrl:'/'+name+'/{z}/{x}/{y}.pbf',batchUrl:'/'+name+'-batch'};
 const upgraded=new TileStore('http://new-base',()=>{});await upgraded.init();await idle(upgraded);
 assert.equal(upgraded.regions[cell].status,'complete');assert.ok(!calls.slice(before).includes('osm'));
 globalThis.fetch=async()=>{throw Error('offline')};
 const shared=keys.find(k=>k.startsWith('12/'));
 for(const name of ['landcover','trails','recreation'])assert.equal(await upgraded.source(name+'/'+shared),Buffer.from(name).toString('base64'));
});

test('recreation matching revision refreshes that source while preserving selected maps and terrain',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},recreation:{...meta,datasetId:'rec-v1',batchUrl:'/recreation-batch',tileUrl:'/recreation/{z}/{x}/{y}.pbf'}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':'recreation',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(set.datasetId).toString('base64')}))})};
 };
 const initial=new TileStore('http://revision',()=>{});await initial.init();await initial.toggle(cell);await idle(initial);
 const before=calls.length;current={...current,tilesets:{...current.tilesets,recreation:{...current.tilesets.recreation,datasetId:'rec-v2'}}};
 const next=new TileStore('http://revision',()=>{});await next.init();await idle(next);
 assert.equal(next.regions[cell].status,'complete');assert.ok(calls.slice(before).every(name=>name==='recreation'));
 const shared=keys.find(k=>k.startsWith('12/'));globalThis.fetch=async()=>{throw Error('offline')};
 assert.equal(await next.source('osm/'+shared),Buffer.from(meta.datasetId).toString('base64'));assert.equal(await next.source('recreation/'+shared),Buffer.from('rec-v2').toString('base64'));
});

test('trails matching revision refreshes that source while preserving selected maps and terrain',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},trails:{...meta,datasetId:'trail-v1',batchUrl:'/trails-batch',tileUrl:'/trails/{z}/{x}/{y}.pbf'}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':'trails',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(set.datasetId).toString('base64')}))})};
 };
 const initial=new TileStore('http://revision',()=>{});await initial.init();await initial.toggle(cell);await idle(initial);
 const before=calls.length;current={...current,tilesets:{...current.tilesets,trails:{...current.tilesets.trails,datasetId:'trail-v2'}}};
 const next=new TileStore('http://revision',()=>{});await next.init();await idle(next);
 assert.equal(next.regions[cell].status,'complete');assert.ok(calls.slice(before).every(name=>name==='trails'));
 const shared=keys.find(k=>k.startsWith('12/'));globalThis.fetch=async()=>{throw Error('offline')};
 assert.equal(await next.source('osm/'+shared),Buffer.from(meta.datasetId).toString('base64'));assert.equal(await next.source('trails/'+shared),Buffer.from('trail-v2').toString('base64'));
});

test('expanded recreation coverage retains saved maps while updating only that source',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},recreation:{...meta,datasetId:'rec-v1',batchUrl:'/recreation-batch',tileUrl:'/recreation/{z}/{x}/{y}.pbf'}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':'recreation',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(set.datasetId).toString('base64')}))})};
 };
 const initial=new TileStore('http://revision',()=>{});await initial.init();await initial.toggle(cell);await idle(initial);
 const before=calls.length;current={...current,tilesets:{...current.tilesets,recreation:{...current.tilesets.recreation,datasetId:'rec-v2',bounds:[-180,18,180,72]}}};
 const next=new TileStore('http://revision',()=>{});await next.init();await idle(next);
 assert.equal(next.regions[cell].status,'complete');assert.ok(calls.slice(before).every(name=>name==='recreation'));
 const shared=keys.find(k=>k.startsWith('12/'));globalThis.fetch=async()=>{throw Error('offline')};
 assert.equal(await next.source('osm/'+shared),Buffer.from(meta.datasetId).toString('base64'));assert.equal(await next.source('recreation/'+shared),Buffer.from('rec-v2').toString('base64'));
});

test('expanded recreation zoom range retains saved maps while updating only that source',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},recreation:{...meta,datasetId:'rec-v1',minZoom:10,batchUrl:'/recreation-batch',tileUrl:'/recreation/{z}/{x}/{y}.pbf'}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':'recreation',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(set.datasetId).toString('base64')}))})};
 };
 const initial=new TileStore('http://revision',()=>{});await initial.init();await initial.toggle(cell);await idle(initial);
 const before=calls.length;current={...current,tilesets:{...current.tilesets,recreation:{...current.tilesets.recreation,datasetId:'rec-v2',minZoom:6}}};
 const next=new TileStore('http://revision',()=>{});await next.init();await idle(next);
 assert.equal(next.regions[cell].status,'complete');assert.ok(calls.slice(before).every(name=>name==='recreation'));
 const shared=keys.find(k=>k.startsWith('12/'));globalThis.fetch=async()=>{throw Error('offline')};
 assert.equal(await next.source('osm/'+shared),Buffer.from(meta.datasetId).toString('base64'));assert.equal(await next.source('recreation/'+shared),Buffer.from('rec-v2').toString('base64'));
});

test('expanded amenities coverage retains saved maps while updating only that source',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},amenities:{...meta,datasetId:'rec-v1',batchUrl:'/amenities-batch',tileUrl:'/amenities/{z}/{x}/{y}.pbf'}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':'amenities',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(set.datasetId).toString('base64')}))})};
 };
 const initial=new TileStore('http://revision',()=>{});await initial.init();await initial.toggle(cell);await idle(initial);
 const before=calls.length;current={...current,tilesets:{...current.tilesets,amenities:{...current.tilesets.amenities,datasetId:'rec-v2',bounds:[-180,18,180,72]}}};
 const next=new TileStore('http://revision',()=>{});await next.init();await idle(next);
 assert.equal(next.regions[cell].status,'complete');assert.ok(calls.slice(before).every(name=>name==='amenities'));
 const shared=keys.find(k=>k.startsWith('12/'));globalThis.fetch=async()=>{throw Error('offline')};
 assert.equal(await next.source('osm/'+shared),Buffer.from(meta.datasetId).toString('base64'));assert.equal(await next.source('amenities/'+shared),Buffer.from('rec-v2').toString('base64'));
});

test('raw DEM replaces contour downloads, preserves saved maps, and stores its full seam halo offline',async()=>{
 memory.clear();let current={...meta,minZoom:12,maxZoom:12,tilesets:{osm:{...meta,minZoom:12,maxZoom:12},contours:{...meta,datasetId:'old-contours',minZoom:12,maxZoom:12,batchUrl:'/contour-batch'}}};const calls=[];
 globalThis.fetch=async url=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':parsed.pathname==='/dem-batch'?'dem':'contours',set=current.tilesets[name],keys=parsed.searchParams.get('tiles').split(',');calls.push({name,keys});return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:keys.map(key=>({key,data:Buffer.from(name+' '+key).toString('base64')}))})}};
 const store=new TileStore('http://dem-upgrade',()=>{},{retryDelayMs:1});await store.init();await store.toggle(cell);await idle(store);const oldPath=store.file('osm/12/'+cell),before=calls.length;
 current={...current,tilesets:{osm:current.tilesets.osm,dem:{...meta,datasetId:'raw-dem',minZoom:11,maxZoom:13,bounds:[-180,-85,180,85],tileUrl:'/dem/{z}/{x}/{y}.png',batchUrl:'/dem-batch',format:'png',halo:1}}};
 const upgraded=new TileStore('http://dem-upgrade',()=>{},{retryDelayMs:1});await upgraded.init();await idle(upgraded);assert.equal(upgraded.regions[cell].status,'complete');assert.equal(upgraded.file('osm/12/'+cell),oldPath);assert.ok(calls.slice(before).every(c=>c.name==='dem'&&c.keys.length<=8));assert.equal(upgraded.regionTiles(cell).filter(k=>k.startsWith('dem/')).length,34);assert.ok(upgraded.file('dem/12/'+cell).endsWith('.png'));assert.ok(!upgraded.regionTiles(cell).some(k=>k.startsWith('contours/')));
 globalThis.fetch=async()=>{throw Error('offline')};const offline=new TileStore('http://dem-upgrade',()=>{});await offline.init();for(const key of offline.regionTiles(cell))assert.ok(await offline.source(key));
});

test('boundaries matching revision refreshes that source while preserving selected maps and terrain',async()=>{
 memory.clear();let current={...meta,tilesets:{osm:{...meta},boundaries:{...meta,datasetId:'boundary-v1',batchUrl:'/boundary-batch',tileUrl:'/boundaries/{z}/{x}/{y}.pbf'}}};const calls=[];
 globalThis.fetch=async url=>{
  if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};
  const parsed=new URL(url),name=parsed.pathname==='/tile-batch'?'osm':'boundaries',set=current.tilesets[name],requested=parsed.searchParams.get('tiles').split(',');calls.push(name);
  return{ok:true,json:async()=>({datasetId:set.datasetId,tiles:requested.map(key=>({key,data:Buffer.from(set.datasetId).toString('base64')}))})};
 };
 const initial=new TileStore('http://revision',()=>{});await initial.init();await initial.toggle(cell);await idle(initial);
 const before=calls.length;current={...current,tilesets:{...current.tilesets,boundaries:{...current.tilesets.boundaries,datasetId:'boundary-v2'}}};
 const next=new TileStore('http://revision',()=>{});await next.init();await idle(next);
 assert.equal(next.regions[cell].status,'complete');assert.ok(calls.slice(before).every(name=>name==='boundaries'));
 const shared=keys.find(k=>k.startsWith('12/'));globalThis.fetch=async()=>{throw Error('offline')};
 assert.equal(await next.source('osm/'+shared),Buffer.from(meta.datasetId).toString('base64'));assert.equal(await next.source('boundaries/'+shared),Buffer.from('boundary-v2').toString('base64'));
});

test('DEM and basemap start before overlays while visible terrain is pending',async()=>{
 memory.clear();const names=['osm','dem','amenities','boundaries','landcover'];const current={...meta,tilesets:Object.fromEntries(names.map(name=>[name,{...meta,datasetId:name,tileUrl:'/'+name+'/{z}/{x}/{y}.pbf'}]))};const calls=[],release=[];
 globalThis.fetch=async(url,options)=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>current};const name=new URL(url).pathname.split('/')[1];calls.push(name);await new Promise(resolve=>release.push(resolve));return{ok:true,arrayBuffer:async()=>new TextEncoder().encode(name).buffer}};
 const store=new TileStore('http://priority',()=>{});await store.init();const jobs=['amenities','landcover','boundaries','dem','osm'].map(name=>store.source(name+'/12/'+cell));
 await delay(35);assert.deepEqual(new Set(calls),new Set(['osm','dem']));release.splice(0).forEach(done=>done());await delay(35);assert.equal(calls.length,4,'only two overlay transfers at once');release.splice(0).forEach(done=>done());await delay(35);release.splice(0).forEach(done=>done());await Promise.all(jobs);await idle(store);
});

test('servers with matching dataset IDs cannot reuse each other’s cached tiles',async()=>{memory.clear();const local=new TileStore('http://local',()=>{}),cloud=new TileStore('https://cloud',()=>{});local.meta=meta;cloud.meta=meta;memory.set(local.file(keys[0]),'bG9jYWw=');assert.notEqual(local.file(keys[0]),cloud.file(keys[0]));assert.equal(memory.has(cloud.file(keys[0])),false);});

test('unpublished visible tile fails once and releases its slot for published detail',async()=>{memory.clear();const calls=[];globalThis.fetch=async url=>{if(url.endsWith('/metadata'))return{ok:true,json:async()=>meta};calls.push(url);return url.includes('/12/1/1.')?{ok:false,status:404}:{ok:true,arrayBuffer:async()=>new TextEncoder().encode('detail').buffer}};const store=new TileStore('https://missing',()=>{},{retryDelayMs:1});await store.init();await assert.rejects(store.source('12/1/1'),/404/);assert.equal(calls.length,1);assert.equal(await store.source('12/2/2'),'ZGV0YWls');});
