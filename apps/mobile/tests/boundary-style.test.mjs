import test from 'node:test';
import assert from 'node:assert/strict';
import {createStyle} from '../src/style.mjs';
test('detailed boundary lines replace overview outlines without removing searchable labels',()=>{
 const meta={bounds:[-180,-85,180,85],minZoom:0,maxZoom:14};
 const style=createStyle(meta,'osm',undefined,undefined,'boundaries');
 for(const kind of ['park','forest','wilderness']){
  const overview=style.layers.find(layer=>layer.id===kind+'-boundaries');
  const detail=style.layers.find(layer=>layer.id==='detailed-'+kind+'-boundaries');
  assert.equal(overview.maxzoom,8);assert.equal(detail.minzoom,8);assert.equal(detail.maxzoom,undefined);
  assert.equal(detail.source,'boundaries');assert.equal(detail['source-layer'],'areas');
  assert.deepEqual(detail.filter,['all',['==',['geometry-type'],'LineString'],['==',['get','kind'],kind]]);
 }
 assert.equal(style.layers.find(layer=>layer.id==='area-labels').source,'areas');
 assert.equal(style.layers.find(layer=>layer.id==='area-fill').maxzoom,8);
 assert.equal(style.layers.find(layer=>layer.id==='detailed-area-fill').minzoom,8);
 assert.equal(createStyle(meta,'osm').layers.find(layer=>layer.id==='park-boundaries').maxzoom,undefined);
});


test('area labels stay centered on their geometry anchors when composed with recreation',async()=>{
 const {createStyle}=await import('../src/style.mjs');
 const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'/tiles/{z}/{x}/{y}',undefined,undefined,undefined,undefined,undefined,undefined,'/recreation/{z}/{x}/{y}');
 const label=style.layers.find(l=>l.id==='area-labels');
 assert.deepEqual(label.layout['text-variable-anchor'],['center']);
 assert.equal(label.layout['text-radial-offset'],0);
 assert.ok(style.layers.indexOf(label)>style.layers.findIndex(l=>l.id==='ranked-peaks'),'park name wins placement rather than shifting away from its center');
});
