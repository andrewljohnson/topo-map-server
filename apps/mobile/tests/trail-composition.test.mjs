import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
import {createStyle} from '../src/style.mjs';
const meta={bounds:[-180,-85,180,85],minZoom:0,maxZoom:14};
test('all clients render the conflated detail network, with distinct long-distance styles across the detail handoff',async()=>{
 const factories=[createStyle];
 for(const file of ['../src/vectorStyle.ts','../../web/app/vectorStyle.ts']){
  const code=ts.transpileModule(fs.readFileSync(new URL(file,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
  factories.push((await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).createStyle);
 }
 for(const make of factories){
  const style=make(meta,'osm',undefined,undefined,undefined,undefined,undefined,'trails');
  assert.ok(!style.layers.some(l=>l.source==='trails'&&l['source-layer']==='trails'),'no ordinary agency trail linework or labels');
  const osm=style.layers.find(l=>l.id==='trails-path'),route=style.layers.find(l=>l.id==='long-trail-pct-overview'),halo=style.layers.find(l=>l.id==='long-trail-pct-halo-overview');
  assert.equal(osm.source,'trails');assert.equal(osm['source-layer'],'network');assert.equal(osm.minzoom,13);assert.equal(route.maxzoom,osm.minzoom);assert.equal(halo.maxzoom,osm.minzoom);
  for(const layer of style.layers.filter(l=>l.source==='osm'&&l['source-layer']==='road'))assert.equal(layer.maxzoom,13,'OSM overview copies stop before merged detail');
  assert.ok(style.layers.some(l=>l.source==='trails'&&l['source-layer']==='network'&&l.id==='road-labels'));
  const badges=style.layers.find(l=>l.id==='long-trail-badges');assert.equal(badges.maxzoom,undefined);assert.ok(badges.minzoom<13);
  const pct=style.layers.find(l=>l.id==='long-trail-pct'),trt=style.layers.find(l=>l.id==='long-trail-trt');
  assert.notEqual(pct.paint['line-color'],trt.paint['line-color']);assert.notDeepEqual(pct.paint['line-dasharray'],trt.paint['line-dasharray']);
  for(const name of ['pct','trt','other']){const detail=style.layers.find(l=>l.id==='long-trail-'+name);assert.equal(detail['source-layer'],'network');assert.equal(detail.minzoom,13);assert.equal(detail.maxzoom,undefined);assert.equal(style.layers.find(l=>l.id===detail.id+'-overview').maxzoom,13);}
  assert.ok(JSON.stringify(osm.filter).includes('route_ref'),'ordinary trail strokes exclude designated routes');
  assert.ok(style.layers.some(l=>l.id==='official-roads-center'),'MVUM roads remain');
  assert.ok(style.layers.some(l=>l.id==='trail-labels'&&l.source==='trails'),'merged trail names remain');
 }
});
