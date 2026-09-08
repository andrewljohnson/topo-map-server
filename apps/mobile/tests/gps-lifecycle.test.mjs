import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import ts from 'typescript';
const input=fs.readFileSync(new URL('../src/useUserLocation.ts',import.meta.url),'utf8');
const code=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/import .*?from 'react';/, 'const {useEffect,useRef,useState}=globalThis.__gpsReact;').replace(/import .*?from 'react-native';/, 'const {AppState}=globalThis.__gpsNative;').replace(/import \* as Location from 'expo-location';/, 'const Location=globalThis.__gpsLocation;');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('GPS starts automatically, stops in background, resumes and cleans up subscriptions',async()=>{
 const effects=[],listeners=[],watches=[],points=[],updates=[];let permissions=0;
 globalThis.__gpsReact={useRef:value=>({current:value}),useState:value=>[value,()=>{}],useEffect:fn=>effects.push(fn)};
 const AppState={currentState:'active',addEventListener:(_,fn)=>{listeners.push(fn);return {remove(){listeners.splice(listeners.indexOf(fn),1)}}}};globalThis.__gpsNative={AppState};
 globalThis.__gpsLocation={Accuracy:{High:4},getForegroundPermissionsAsync:async()=>({granted:true}),requestForegroundPermissionsAsync:async()=>{permissions++;return {granted:true}},hasServicesEnabledAsync:async()=>true,watchPositionAsync:async(options,callback)=>{const watch={options,callback,removed:false,remove(){this.removed=true}};watches.push(watch);return watch}};
 const {useUserLocation}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));useUserLocation(p=>updates.push(p),p=>points.push(p));const cleanup=effects[0]();await tick();assert.equal(watches.length,1);assert.equal(watches[0].options.accuracy,4);
 const point={timestamp:100,coords:{longitude:-120,latitude:39,accuracy:4,altitude:100}};watches[0].callback(point);assert.equal(points.length,1);assert.equal(updates[0].center,false);
 AppState.currentState='background';listeners.forEach(fn=>fn('background'));assert.equal(watches[0].removed,true);watches[0].callback(point);assert.equal(points.length,1);
 AppState.currentState='active';listeners.forEach(fn=>fn('active'));await tick();assert.equal(watches.length,2);watches[1].callback(point);assert.equal(points.length,2);cleanup();assert.equal(watches[1].removed,true);assert.equal(listeners.length,0);assert.equal(permissions,0);
});
