import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createStyle} from '../src/style.mjs';
const require=createRequire(import.meta.url);
const {featureFilter,expression}=createRequire(require.resolve('maplibre-gl'))('@maplibre/maplibre-gl-style-spec');
const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'topo://osm/{z}/{x}/{y}.pbf');
const layer=style.layers.find(l=>l.id==='lake-labels');
const visible=(zoom,properties)=>featureFilter(layer.filter).filter({zoom},{type:1,properties});
const compiled=expression.createExpression(layer.layout['text-rotate']);assert.equal(compiled.result,'success');
const rotation=(zoom,properties)=>compiled.value.evaluate({zoom},{type:1,properties});
test('Fallen Leaf keeps its angled interval then becomes horizontal without duplicate labels',()=>{
 const lake={name:'Fallen Leaf Lake',min_zoom:13,label_horizontal_zoom:13,label_angle:-69.9};
 assert.equal(visible(11,lake),false);assert.equal(visible(12,lake),true);assert.equal(visible(13,lake),true);
 assert.equal(rotation(12,lake),-69.9);assert.equal(rotation(12.99,lake),-69.9);assert.equal(rotation(13,lake),0);
 assert.equal(layer.layout['text-max-width'],1000);assert.equal(style.layers.filter(l=>l['source-layer']==='water_label').length,1);
});
test('Tahoe remains horizontal when its name already fits',()=>{
 const lake={name:'Lake Tahoe',min_zoom:10,label_horizontal_zoom:8.4,label_angle:-85.1};
 assert.equal(visible(9,lake),true);assert.equal(rotation(9,lake),0);
});
test('angled and horizontal lakes share importance ordering',()=>{
 const priority=expression.createExpression(layer.layout['symbol-sort-key']);assert.equal(priority.result,'success');
 const rank=p=>priority.value.evaluate({zoom:12},{type:1,properties:p});
 assert.ok(rank({min_zoom:12,label_horizontal_zoom:17.4})<rank({min_zoom:13,label_horizontal_zoom:0}));
 for(const angle of [-85,-45,0,70])assert.equal(rotation(14.2,{label_angle:angle,label_horizontal_zoom:14.2}),0);
});
test('minor lakes use smaller medium-scale text and limited placement alternatives',()=>{
 const size=expression.createExpression(layer.layout['text-size']);assert.equal(size.result,'success');
 const at=(zoom,min_zoom)=>size.value.evaluate({zoom},{type:1,properties:{min_zoom}});
 assert.ok(at(12,13)<at(12,8));assert.ok(at(14,13)>at(12,13));
 assert.deepEqual(layer.layout['text-variable-anchor'],['center','top','bottom']);
 assert.equal(layer.layout['text-allow-overlap'],false);
});
test('major lakes have stronger type without changing small lake density or fitting too early',()=>{
 const size=expression.createExpression(layer.layout['text-size']);assert.equal(size.result,'success');const at=(zoom,p)=>size.value.evaluate({zoom},{type:1,properties:p});
 const tahoe={min_zoom:10,label_horizontal_zoom:8.4,label_angle:-85.1};assert.equal(at(10,tahoe),18);assert.equal(rotation(9,tahoe),0);
 const narrow={min_zoom:10,label_horizontal_zoom:10,label_angle:45};assert.equal(rotation(10,narrow),45);assert.equal(rotation(11,narrow),0,'larger font eventually fits');
 const minor={min_zoom:13,label_horizontal_zoom:17.4};assert.equal(at(12,minor),12);assert.ok(at(12,tahoe)>at(12,minor));
});
