import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import {createStyle} from '../src/style.mjs';
const transpile=source=>ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const bridgeSource=transpile(fs.readFileSync(new URL('../src/rendererBridge.ts',import.meta.url),'utf8')).replace("'./style.mjs'",JSON.stringify(new URL('../src/style.mjs',import.meta.url).href));
const bridge=await import('data:text/javascript;base64,'+Buffer.from(bridgeSource).toString('base64'));
const shieldSource=transpile(fs.readFileSync(new URL('../src/shieldImages.ts',import.meta.url),'utf8'));
const shieldModule='data:text/javascript;base64,'+Buffer.from(shieldSource).toString('base64');
const poiSource=transpile(fs.readFileSync(new URL('../src/poiImages.ts',import.meta.url),'utf8'));
const poiModule='data:text/javascript;base64,'+Buffer.from(poiSource).toString('base64');
const amenityModule='data:text/javascript;base64,'+Buffer.from(transpile(fs.readFileSync(new URL('../src/amenityImages.ts',import.meta.url),'utf8'))).toString('base64');
const mapInfoModule='data:text/javascript;base64,'+Buffer.from(transpile(fs.readFileSync(new URL('../src/mapInfo.ts',import.meta.url),'utf8'))).toString('base64');
const extraModules=Object.fromEntries(['lakeOrientation','combinedMap','trailBadges','featureInfo','poiMatching','mapNotes','terrainRuntime','terrainWorkerSource'].map(name=>[name,'data:text/javascript;base64,'+Buffer.from(transpile(fs.readFileSync(new URL('../src/'+name+'.ts',import.meta.url),'utf8'))).toString('base64')]));
const mapSource=transpile(fs.readFileSync(new URL('../src/map.ts',import.meta.url),'utf8')).replace(/import .*? from ['"]\.\/mapAssets['"];?/,"const maplibreJs='',maplibreCss='',maplibreWorker='';").replace("'./shieldImages'",JSON.stringify(shieldModule)).replace("'./poiImages'",JSON.stringify(poiModule)).replace("'./amenityImages'",JSON.stringify(amenityModule)).replace("'./mapInfo'",JSON.stringify(mapInfoModule)).replace("'./lakeOrientation'",JSON.stringify(extraModules.lakeOrientation)).replace("'./combinedMap'",JSON.stringify(extraModules.combinedMap)).replace("'./trailBadges'",JSON.stringify(extraModules.trailBadges)).replace("'./featureInfo'",JSON.stringify(extraModules.featureInfo)).replace("'./poiMatching'",JSON.stringify(extraModules.poiMatching)).replace("'./mapNotes'",JSON.stringify(extraModules.mapNotes)).replace("'./terrainRuntime'",JSON.stringify(extraModules.terrainRuntime)).replace("'./terrainWorkerSource'",JSON.stringify(extraModules.terrainWorkerSource));
const {mapHtml}=await import('data:text/javascript;base64,'+Buffer.from(mapSource).toString('base64'));
const meta={name:'Maryland',datasetId:'test',bounds:[-79.49,37.88,-75.03,39.73],center:[-76.6122,39.2904],minZoom:6,maxZoom:14,gridZoom:12,tileUrl:'/tiles/{z}/{x}/{y}.pbf'};
test('renderer initializes from JSON even when function source is unavailable in Hermes',()=>{
 const saved=createStyle.toString;
 createStyle.toString=()=>{throw Error('Hermes function source cannot be serialized')};
 try{
  const messages=[];let options;
  const context=vm.createContext({window:{ReactNativeWebView:{postMessage:text=>messages.push(JSON.parse(text))}},URL:{createObjectURL:()=> 'blob:worker'},Blob, setTimeout,clearTimeout,
   maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},Map:class{constructor(value){options=value}addControl(){}on(){}isStyleLoaded(){return false}},NavigationControl:class{}}});
  const html=mapHtml();
  for(const [,script] of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
  assert.equal(messages[0].type,'ready');
  const payload=bridge.rendererInit(meta);
  vm.runInContext(bridge.rendererScript(payload),context);
  assert.equal(options.style.sources.osm.type,'vector');
  assert.equal(options.style.sources.osm.tiles[0],'topo://osm/{z}/{x}/{y}.pbf');
  assert.deepEqual(JSON.parse(JSON.stringify(options.center)),meta.center);
  assert.ok(!messages.some(m=>m.type==='fatal'));
 }finally{createStyle.toString=saved}
});
test('bridge reports injected initialization failures with the actual error',()=>{
 const messages=[];
 const context=vm.createContext({window:{receive(){throw Error('WebGL unavailable')},ReactNativeWebView:{postMessage:text=>messages.push(JSON.parse(text))}}});
 vm.runInContext(bridge.rendererScript(bridge.rendererInit(meta)),context);
 assert.equal(messages[0].type,'fatal');
 assert.equal(messages[0].message,'WebGL unavailable');
});
test('renderer composes independent OSM and contour vector sources only when available',()=>{
 const composed={...meta,tilesets:{osm:{...meta},contours:{...meta,datasetId:'contour-2',minZoom:11,tileUrl:'/contours/{z}/{x}/{y}.pbf'}}};
 const style=bridge.rendererInit(composed).style;
 assert.equal(style.sources.osm.tiles[0],'topo://osm/{z}/{x}/{y}.pbf');
 assert.equal(style.sources.contours.tiles[0],'topo://contours/{z}/{x}/{y}.pbf');
 assert.equal(style.sources.contours.minzoom,11);
 assert.equal(bridge.rendererInit(meta).style.sources.contours,undefined);
});
test('location marker survives map loading and only explicit locate changes camera',()=>{
 const sources=new Map(),camera=[];let loaded;
 const context=vm.createContext({window:{ReactNativeWebView:{postMessage(){}}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
  maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},NavigationControl:class{},Map:class{
   isStyleLoaded(){return false} addControl(){} on(event,handler){if(event==='load')loaded=handler}
   addSource(name,source){sources.set(name,{data:source.data,setData(data){this.data=data}})}
   getLayer(){return undefined} addLayer(){} getSource(name){return sources.get(name)} getZoom(){return 12} easeTo(options){camera.push(options)}
   getBounds(){return {getWest:()=>-122.43,getEast:()=>-122.41,getNorth:()=>37.78,getSouth:()=>37.76}}
  }}});
 for(const [,script] of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 vm.runInContext(bridge.rendererScript(bridge.rendererInit({...meta,bounds:[-180,-85,180,85]})),context);
 vm.runInContext(bridge.rendererScript({type:'location',longitude:-122.42,latitude:37.77,accuracy:20,center:true}),context);
 assert.equal(camera.length,0);loaded();assert.equal(camera.length,1);
 assert.equal(sources.get('user-location').data.features[0].geometry.coordinates[0].length,65);
 vm.runInContext(bridge.rendererScript({type:'location',longitude:-122.421,latitude:37.771,accuracy:15,center:false}),context);
 vm.runInContext(bridge.rendererScript({type:'state',mode:true,regions:{}}),context);
 assert.equal(camera.length,1,'tracking updates and download selection must not recenter');
 assert.deepEqual(JSON.parse(JSON.stringify(sources.get('user-location').data.features[1].geometry.coordinates)),[-122.421,37.771]);
});
test('boundary data survives map load without area explorer click handlers',()=>{
 const sources=new Map([['areas',{data:null,setData(data){this.data=data}}]]),camera=[];let loaded,labelClick;
 const context=vm.createContext({document:{documentElement:{style:{setProperty(){}}}},window:{ReactNativeWebView:{postMessage(){}}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
  maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},NavigationControl:class{},Map:class{
   isStyleLoaded(){return false}addControl(){}on(event,...args){if(event==='load')loaded=args[0];if(event==='click'&&args[0]==='area-labels')labelClick=args[1]}
   getLayer(name){return name==='area-labels'?{}:undefined}addSource(name,source){sources.set(name,{data:source.data,setData(data){this.data=data}})}addLayer(){}getSource(name){return sources.get(name)}getZoom(){return 12}fitBounds(bounds,options){camera.push({bounds,options})}
   getBounds(){return{getWest:()=>-122.43,getEast:()=>-122.41,getNorth:()=>37.78,getSouth:()=>37.76}}
  }}});
 for(const [,script]of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 const geojson={type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-119.5,37.7]},properties:{name:'Yosemite'}}]};
 vm.runInContext(bridge.rendererScript({type:'areas',data:geojson}),context);vm.runInContext(bridge.rendererScript(bridge.rendererInit(meta)),context);loaded();
 assert.deepEqual(JSON.parse(JSON.stringify(sources.get('areas').data)),geojson);assert.equal(camera.length,0);
 assert.equal(labelClick,undefined,'area labels do not register explore/zoom actions');
});

test('nationwide amenity tiles cross the JSON bridge and refresh through the offline protocol',()=>{
 const composed={...meta,tilesets:{osm:{...meta},amenities:{...meta,datasetId:'amenities-v1',minZoom:10,tileUrl:'/amenities/{z}/{x}/{y}.pbf'}}};
 const payload=JSON.parse(JSON.stringify(bridge.rendererInit(composed)));
 assert.equal(payload.style.sources.amenities.type,'vector');assert.equal(payload.style.sources.amenities.tiles[0],'topo://amenities/{z}/{x}/{y}.pbf');assert.equal(payload.style.sources.amenities.minzoom,10);
 const refreshed=[];const context=vm.createContext({window:{ReactNativeWebView:{postMessage(){}}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
  maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},Map:class{addControl(){}on(){}isStyleLoaded(){return false}getSource(name){return{setTiles:tiles=>refreshed.push({name,tiles})}}},NavigationControl:class{}}});
 for(const [,script]of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 vm.runInContext(bridge.rendererScript(payload),context);vm.runInContext(bridge.rendererScript({type:'refresh'}),context);
 assert.ok(refreshed.some(({name,tiles})=>name==='amenities'&&tiles[0]==='topo://amenities/{z}/{x}/{y}.pbf'));
});

test('detailed boundary tiles cross the JSON bridge and refresh through the offline protocol',()=>{
 const composed={...meta,tilesets:{osm:{...meta},boundaries:{...meta,datasetId:'boundaries-v1',minZoom:8,tileUrl:'/boundaries/{z}/{x}/{y}.pbf'}}};
 const payload=JSON.parse(JSON.stringify(bridge.rendererInit(composed)));
 assert.equal(payload.style.sources.boundaries.type,'vector');assert.equal(payload.style.sources.boundaries.tiles[0],'topo://boundaries/{z}/{x}/{y}.pbf');assert.equal(payload.style.sources.boundaries.minzoom,8);
 const refreshed=[];const context=vm.createContext({window:{ReactNativeWebView:{postMessage(){}}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
  maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},Map:class{addControl(){}on(){}isStyleLoaded(){return false}getSource(name){return{setTiles:tiles=>refreshed.push({name,tiles})}}},NavigationControl:class{}}});
 for(const [,script]of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 vm.runInContext(bridge.rendererScript(payload),context);vm.runInContext(bridge.rendererScript({type:'refresh'}),context);
 assert.ok(refreshed.some(({name,tiles})=>name==='boundaries'&&tiles[0]==='topo://boundaries/{z}/{x}/{y}.pbf'));
});

test('fresh metadata replaces cached overview configuration without moving the camera',()=>{
 const options=[];let removed=0;
 const context=vm.createContext({window:{ReactNativeWebView:{postMessage(){}}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
 maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},NavigationControl:class{},Map:class{
 constructor(value){options.push(value)}addControl(){}on(){}isStyleLoaded(){return false}
 getCenter(){return {lng:-120.1,lat:38.9}}getZoom(){return 14.5}getBearing(){return 12}getPitch(){return 25}remove(){removed++}
 }}});
 for(const [,script]of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 vm.runInContext(bridge.rendererScript(bridge.rendererInit(meta)),context);
 const fresh={...meta,tilesets:{osm:{...meta},boundaries:{...meta,datasetId:'boundaries-v1',minZoom:8,tileUrl:'/boundaries/{z}/{x}/{y}.pbf'}}};
 vm.runInContext(bridge.rendererScript(bridge.rendererInit(fresh)),context);
 assert.equal(removed,1);assert.equal(options.length,2);assert.equal(options[1].zoom,14.5);assert.equal(options[1].center.lng,-120.1);assert.equal(options[1].bearing,12);assert.equal(options[1].pitch,25);
 assert.equal(options[1].style.sources.boundaries.type,'vector');
 vm.runInContext(bridge.rendererScript(bridge.rendererInit(fresh)),context);
 assert.equal(options.length,2,'ordinary download state sync must not recreate or move the map');
 const revised=bridge.rendererInit(fresh);revised.style.layers=revised.style.layers.filter(l=>l.id!=='amenity-groups');
 vm.runInContext(bridge.rendererScript(revised),context);
 assert.equal(options.length,3,'style changes must apply even when tile datasets are unchanged');
 assert.equal(options[2].zoom,14.5);assert.equal(options[2].center.lng,-120.1);assert.equal(options[2].bearing,12);assert.equal(options[2].pitch,25);
 assert.ok(!options[2].style.layers.some(l=>l.id==='amenity-groups'));
 vm.runInContext(bridge.rendererScript(revised),context);
 assert.equal(options.length,3,'identical style sync must preserve the map');

});

test('panning away cancels the native tile request as well as the renderer promise',async()=>{
 const messages=[];let protocol;
 const context=vm.createContext({window:{ReactNativeWebView:{postMessage:s=>messages.push(JSON.parse(s))}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
 maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(name,handler){protocol=handler}}});
 for(const [,script]of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 const controller=new AbortController();const pending=protocol({url:'topo://contours/14/2728/6331.pbf'},controller);
 controller.abort();await assert.rejects(pending,/Cancelled/);
 const requested=messages.find(m=>m.type==='tile');assert.ok(requested);
 assert.ok(messages.some(m=>m.type==='tileCancel'&&m.id===requested.id));
});

test('download entry reveals the grid once and later state updates preserve manual zoom',()=>{
 const camera=[];let zoom=5,wide=true;
 const context=vm.createContext({window:{ReactNativeWebView:{postMessage(){}}},URL:{createObjectURL:()=> 'blob:worker'},Blob,setTimeout,clearTimeout,
 maplibregl:{setWorkerUrl(){},setWorkerCount(){},addProtocol(){},NavigationControl:class{},Map:class{
 addControl(){}on(){}isStyleLoaded(){return false}getSource(){return undefined}
 getZoom(){return zoom}easeTo(options){camera.push(options);zoom=options.zoom}
 getBounds(){return wide?{getWest:()=>-125,getEast:()=>-70,getNorth:()=>49,getSouth:()=>25}:{getWest:()=>-120.1,getEast:()=>-120,getNorth:()=>39,getSouth:()=>38.9}}
 }}});
 for(const [,script]of mapHtml().matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script,context);
 vm.runInContext(bridge.rendererScript(bridge.rendererInit({...meta,bounds:[-180,-85,180,85]})),context);
 const state=mode=>vm.runInContext(bridge.rendererScript({type:'state',mode,regions:{}}),context);
 state(true);assert.equal(camera.length,1);assert.ok(camera[0].zoom>5);assert.equal(camera[0].center,undefined,'keep the current map center');
 zoom=4;state(true);state(true);assert.equal(camera.length,1,'manual zoom and queue updates never autozoom');
 state(false);assert.equal(camera.length,1,'leaving download mode never autozooms');
 wide=false;zoom=14;state(true);assert.equal(camera.length,1,'an already visible grid needs no camera change');
});

test('new sources compose beneath water and minor recreation survives overzoom',()=>{
 const tilesets=Object.fromEntries(['osm','landcover','trails','recreation'].map(name=>[name,{...meta,datasetId:name+'-1',tileUrl:'/'+name+'/{z}/{x}/{y}.pbf'}]));
 const style=bridge.rendererInit({...meta,tilesets}).style;
 for(const name of ['landcover','trails','recreation'])assert.equal(style.sources[name].tiles[0],'topo://'+name+'/{z}/{x}/{y}.pbf');
 assert.equal(new Set(style.layers.map(l=>l.id)).size,style.layers.length);
 assert.ok(style.layers.findIndex(l=>l.id==='nlcd-forest')<style.layers.findIndex(l=>l.id==='water'));
 const detail=style.layers.find(l=>l.id==='recreation-poi-details');assert.equal(detail.minzoom,15);assert.ok(!JSON.stringify(detail.filter).includes('"zoom"'));
 assert.equal(style.layers.find(l=>l.id==='long-trail-badges').layout['icon-image'][1],'badge');
});
