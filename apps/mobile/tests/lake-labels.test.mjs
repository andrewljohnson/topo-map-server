import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createStyle} from '../src/style.mjs';
const require=createRequire(import.meta.url);
const {featureFilter}=createRequire(require.resolve('maplibre-gl'))('@maplibre/maplibre-gl-style-spec');
const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'topo://osm/{z}/{x}/{y}.pbf');
const angled=style.layers.find(l=>l.id==='lake-labels'),horizontal=style.layers.find(l=>l.id==='lake-labels-horizontal');
const visible=(layer,zoom,properties)=>featureFilter(layer.filter).filter({zoom},{type:1,properties});
test('Fallen Leaf has an angled interval before switching to a single horizontal label',()=>{
 const lake={name:'Fallen Leaf Lake',min_zoom:13,label_horizontal_zoom:13,label_angle:-69.9};
 assert.equal(visible(angled,12,lake),true);assert.equal(visible(horizontal,12,lake),false);
 assert.equal(visible(angled,13,lake),false);assert.equal(visible(horizontal,13,lake),true);
 assert.equal(angled.layout['text-max-width'],1000);
});
test('Tahoe remains horizontal when its name already fits',()=>{
 const lake={name:'Lake Tahoe',min_zoom:10,label_horizontal_zoom:8.4,label_angle:-85.1};
 assert.equal(visible(angled,9,lake),false);assert.equal(visible(horizontal,9,lake),true);
});
