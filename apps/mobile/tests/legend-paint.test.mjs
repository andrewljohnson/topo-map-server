import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';import ts from 'typescript';import {createRequire} from 'node:module';import {createStyle} from '../src/style.mjs';
const require=createRequire(import.meta.url),{expression}=createRequire(require.resolve('maplibre-gl'))('@maplibre/maplibre-gl-style-spec');const context=vm.createContext({exports:{}});
vm.runInContext(ts.transpileModule(fs.readFileSync(new URL('../src/mapInfo.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,context);vm.runInContext(context.exports.mapInfoScript,context);
const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:12,combined:true,overviewMaxZoom:3},'base');
test('legend paints match MapLibre across zooms, road classes, surfaces and urban context',()=>{
 const seen=new Set();let comparisons=0;
 for(const layer of style.layers.filter(l=>['line','fill'].includes(l.type)))for(const [key,value]of Object.entries(layer.paint||{})){
  if(!/^(line-(width|opacity|color|dasharray)|fill-(color|opacity))$/.test(key))continue;const signature=JSON.stringify(value);if(seen.has(signature))continue;seen.add(signature);
  const expr=Array.isArray(value)&&typeof value[0]==='string'?expression.createExpression(value):null;if(expr)assert.equal(expr.result,'success',layer.id+'/'+key);
  for(const zoom of [5,10,12,12.5,13,14,16,18])for(const klass of ['motorway','primary','secondary','tertiary','residential','service','parking_aisle','track','footway','cycleway','river','stream','park','forest'])for(const tunnel of [false,true]){
   const p={class:klass,kind:'forest',is_tunnel:tunnel,surface:tunnel?'gravel':'asphalt',path_context:tunnel?'urban':'rural',route_ref:tunnel?'PCT':''};const actual=context.legendPaint(value,p,zoom),expected=expr?expr.value.evaluate({zoom},{type:2,properties:p}):value;
   if(typeof expected==='number')assert.ok(Number.isFinite(actual)&&Math.abs(actual-expected)<1e-8,`${layer.id}/${key}/${klass}/${zoom}: ${actual} vs ${expected}`);else assert.equal(JSON.stringify(actual),JSON.stringify(expected),`${layer.id}/${key}`);comparisons++;
  }
 }
 assert.ok(comparisons>5000);
});
test('feature-dependent local-road casing remains wider than its fill',()=>{
 for(const klass of ['residential','service','parking_aisle'])for(const zoom of [12,14,16,18]){
  const width=id=>context.legendPaint(style.layers.find(l=>l.id===id).paint['line-width'],{class:klass},zoom);
  assert.ok(width('roads-local-casing')>width('roads-local'));assert.ok(width('roads-local')>0);
 }
 assert.equal(context.legendPaint(['unimplemented-operator',1]),undefined,'unknown expressions never produce a false numeric width');
});
