import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createStyle} from '../src/style.mjs';
const require=createRequire(new URL('../../web/package.json',import.meta.url));
const spec=createRequire(require.resolve('maplibre-gl'))('@maplibre/maplibre-gl-style-spec');
const meta={bounds:[-180,-85,180,85],minZoom:0,maxZoom:12,combined:true,overviewMaxZoom:3};
const url='https://example.com/{z}/{x}/{y}.pbf';
const style=createStyle(meta,url);

test('complete shared style validates against the installed MapLibre specification',()=>{
 for(const m of [meta,{...meta,combined:false,maxZoom:14}]){
  const result=createStyle(m,url,url,url,url,url,url,url,url);
  assert.deepEqual(spec.validateStyleMin(result).map(e=>e.message),[]);
 }
});

test('secondary amenity handoff works while overzooming the same native z12 tile',()=>{
 const visible=(id,zoom,properties)=>{
  const layer=style.layers.find(l=>l.id===id);
  return zoom>=(layer.minzoom||0)&&zoom<(layer.maxzoom||24)&&spec.featureFilter(layer.filter).filter({zoom:12},{type:1,properties});
 };
 for(const icon of ['shop','restaurant','cafe','information']){
  const feature={kind:'amenity',poi_icon:icon,group_id:''};
  assert.equal(visible('amenity-details',14,feature),false);
  assert.equal(visible('amenity-secondary-details',14,feature),false);
  assert.equal(visible('amenity-secondary-details',15,feature),true);
  assert.equal(visible('amenity-group-members',15,{...feature,group_id:'camp'}),true);
 }
 assert.equal(visible('amenity-details',14,{kind:'amenity',poi_icon:'toilet',group_id:''}),true);
});

test('local walkways recede at resort scale while named and signed hikes retain emphasis',()=>{
 const layer=style.layers.find(l=>l.id==='trails-path');
 const value=(key,properties,zoom=15.18)=>{
  const parsed=spec.expression.createExpression(layer.paint[key]);
  assert.equal(parsed.result,'success');return parsed.value.evaluate({zoom},{type:2,properties});
 };
 const rural={class:'path'},local={class:'footway',path_context:'developed'};
 assert.ok(value('line-width',local)<value('line-width',rural));
 assert.ok(value('line-opacity',local)<.6);
 assert.equal(value('line-opacity',local,18),value('line-opacity',rural,18));
 for(const protectedRoute of [{name:'Yosemite Falls Trail'},{route_ref:'PCT'},{ref:'17E05'}]){
  assert.equal(value('line-width',{...local,...protectedRoute}),value('line-width',rural));
  assert.equal(value('line-opacity',{...local,...protectedRoute}),value('line-opacity',rural));
 }
});
