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
