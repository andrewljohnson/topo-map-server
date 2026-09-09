import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const literal=fs.readFileSync(new URL('../src/poiMatching.ts',import.meta.url),'utf8');
const code=JSON.parse(literal.slice(literal.indexOf('=')+1).trim().replace(/;$/,''));
const point=(id,properties,lon=-120,lat=39)=>({id,geometry:{type:'Point',coordinates:[lon,lat]},properties});
function setup(osm=[],recreation=[]){
 const events={},sources={amenities:osm,recreation},layers=['amenity-details','amenity-group-members','recreation-pois','recreation-poi-details'].map(id=>({id,filter:['==',['get','kind'],id.startsWith('amenity')?'amenity':'campground']}));
 const updates=[];const map={getZoom:()=>15,getStyle:()=>({sources:{amenities:{type:'vector'},recreation:{type:'vector'}},layers}),getSource:name=>sources[name],querySourceFeatures:name=>sources[name],setFilter:(id,filter)=>{layers.find(l=>l.id===id).filter=filter;updates.push({id,filter})},on:(event,fn)=>events[event]=fn,off:event=>delete events[event]};
 const context=vm.createContext({setTimeout,clearTimeout});vm.runInContext(code,context);context.installPoiMatching(map);events.idle();
 return{map,events,updates,sources,layers,hidden:id=>new Set(layers.find(l=>l.id===id).filter?.at(-1)?.[1]?.[2]?.[1]||[])};
}
const camp=(id,name='Fallen Leaf Campground',lon=-120)=>point(id,{kind:'amenity',poi_icon:'campsite',name,osm_id:'way/'+id,group_id:'way/'+id},lon);
const agency=(id,name='Fallen Leaf',kind='campground',lon=-120)=>({...point(id,{id:'nps:'+id,kind,poi_icon:'campsite',name,agency:'NPS'},lon),source:'recreation',sourceLayer:'recreation'});
test('aliases match by name, kind and distance; details survive, offline files need no replacement',()=>{
 const f=agency(2);f.properties.phone='555';
 const a=setup([camp(1)],[f]);assert.ok(a.hidden('recreation-pois').has(2));assert.equal(a.map.__topoPoiDetails.get('way/1').properties.phone,'555');
 assert.deepEqual(f.geometry.coordinates,[-120,39]);
 const count=a.updates.length;a.events.idle();assert.equal(a.updates.length,count);
 // Agency marker returns when its OSM counterpart leaves the loaded data.
 a.sources.amenities=[];a.events.idle();assert.equal(a.hidden('recreation-pois').size,0);
 a.events.remove();
});
test('nearby different facility types, generic names and campground loops stay separate',()=>{
 for(const [osm,f]of [[camp(1),agency(2,'Fallen Leaf','trailhead')],[camp(1,'Campground'),agency(2,'Campground')],[camp(1,'Fallen Leaf Loop A'),agency(2,'Fallen Leaf Loop B')],[camp(1),agency(2,'Fallen Leaf','campground',-120.01)]]){
  const a=setup([osm],[f]);assert.equal(a.hidden('recreation-pois').size,0);a.events.remove();
 }
});
test('ambiguous same-name sites do not get guessed into a match',()=>{
 const a=setup([camp(1,'Fallen Leaf Campground',-120.0002),camp(3,'Fallen Leaf Campground',-119.9998)],[agency(2)]);
 assert.equal(a.hidden('recreation-pois').size,0);a.events.remove();
});
test('shared external IDs merge source details but preserve conflicting values',()=>{
 const f=agency(1),g=agency(2,'Fallen Leaf Campground','campground',-120.005);f.properties.ridb_id=g.properties.ridb_id='232769';f.properties.water='Yes';g.properties.water='Seasonal';g.properties.phone='555';
 const a=setup([],[g,f]);assert.ok(a.hidden('recreation-pois').has(2));const merged=a.map.__topoPoiDetails.get('nps:1');
 assert.equal(merged.properties.phone,'555');assert.equal(merged.properties.water,'Yes');
 const records=JSON.parse(merged.properties.source_records);assert.equal(records.length,2);assert.ok(records.some(r=>r.details.water==='Seasonal'));assert.deepEqual(merged.geometry.coordinates,f.geometry.coordinates);a.events.remove();
});
test('duplicate OSM representations merge, nearby distinct facilities do not',()=>{
 const parent=camp(1,'Lodgepole Campground');parent.properties.osm_id=parent.properties.group_id='relation/1';
 const child=camp(2,'');child.properties.group_id='relation/1';
 const toilet=point(3,{kind:'amenity',poi_icon:'toilet',name:'',osm_id:'node/3',group_id:'relation/1'});
 const a=setup([child,toilet,parent],[]);assert.ok(a.hidden('amenity-group-members').has(2));assert.ok(!a.hidden('amenity-group-members').has(3));a.events.remove();
});
test('geometry getters remain available after merging more than two source records',()=>{
 const values=[1,2,3].map(id=>{const f=agency(id);Object.defineProperty(f,'geometry',{get:()=>({type:'Point',coordinates:[-120,39]}),enumerable:false});return f});
 const a=setup([] ,values);assert.equal(a.hidden('recreation-pois').size,2);assert.equal(a.map.__topoPoiDetails.get('nps:1').properties.source_count,3);a.events.remove();
});


test('agency remains visible until a single-icon OSM cluster becomes eligible',()=>{
 const osm=camp(1),f=agency(2);
 const group=point(3,{kind:'group',group_id:'way/1',osm_id:'way/1',name:'Fallen Leaf Campground',grid_image:'amenity-grid:campsite',min_zoom:13});
 const a=setup([osm,group],[f]);a.map.getZoom=()=>12;a.events.idle();assert.equal(a.hidden('recreation-pois').size,0);
 a.map.getZoom=()=>13;a.events.idle();assert.ok(a.hidden('recreation-pois').has(2));a.events.remove();
});


test('GNIS matches loaded OSM peaks including colliding tile-local feature IDs',()=>{
 const f=agency(3,'Mount Example','summit');f.properties.agency='USGS GNIS';f.properties.gnis_id='100';f.properties.min_zoom=13;
 const a=setup([],[f]);const realGet=a.map.getStyle;
 a.map.getStyle=()=>({...realGet(),sources:{...realGet().sources,osm:{type:'vector'}}});
 const peak=point(1,{class:'peak',name:'Mt. Example',poi_icon:'mountain',min_zoom:13});
 a.sources.osm=[point(1,{class:'peak',name:'Another Peak',poi_icon:'mountain'},-121),peak];
 a.events.idle();assert.ok(a.hidden('recreation-pois').has(3));assert.ok([...a.map.__topoPoiDetails.keys()].some(k=>k.startsWith('base:')));
 a.map.getZoom=()=>11;a.events.idle();assert.equal(a.hidden('recreation-pois').size,0);
 a.sources.osm=[];a.map.getZoom=()=>15;a.events.idle();assert.equal(a.hidden('recreation-pois').size,0);a.events.remove();
});
test('OSM saddles match passes but do not collapse nearby summits',()=>{
 const f=agency(3,'Example Pass','pass');f.properties.agency='USGS GNIS';
 const a=setup([],[f]);const realGet=a.map.getStyle;a.map.getStyle=()=>({...realGet(),sources:{...realGet().sources,osm:{type:'vector'}}});
 a.sources.osm=[point(1,{class:'saddle',name:'Example Pass',poi_icon:'mountain'})];a.events.idle();assert.ok(a.hidden('recreation-pois').has(3));
 a.sources.osm[0].properties.class='peak';a.events.idle();assert.equal(a.hidden('recreation-pois').size,0);a.events.remove();
});
test('distinct official GNIS IDs remain separate even with the same nearby name',()=>{
 const f=agency(3,'Example Peak','summit'),g=agency(4,'Example Peak','summit');f.properties.gnis_id='1';g.properties.gnis_id='2';
 const a=setup([],[f,g]);assert.equal(a.hidden('recreation-pois').size,0);a.events.remove();
});


test('an ambiguous imported landmark stays separate even when only one nearby candidate is loaded',()=>{
 const f=agency(3,'Example Peak','summit'),g=agency(4,'Example Peak','summit');f.properties.agency='USGS GNIS';f.properties.gnis_id='1';g.properties.agency='GeoNames';g.properties.match_ambiguous=true;
 const a=setup([],[f,g]);assert.equal(a.hidden('recreation-pois').size,0);a.events.remove();
});


test('landform anchor offsets match without loosening springs or different summit IDs',()=>{
 const f=agency(3,'Cadillac Mountain','summit'),g=agency(4,'Cadillac Mountain','summit',-120.003);f.properties.agency='USGS GNIS';g.properties.agency='GeoNames';
 const a=setup([],[f,g]);assert.equal(a.hidden('recreation-pois').size,1);a.events.remove();
 f.properties.kind=g.properties.kind='spring';const b=setup([],[f,g]);assert.equal(b.hidden('recreation-pois').size,0);b.events.remove();
});


test('regional peak survives until the detailed OSM layer is eligible',()=>{
 const f=agency(3,'Mount Example','summit');f.properties.label_minzoom=7;f.properties.label_rank=0;
 const a=setup([],[f]);a.layers.push({id:'ranked-peaks',filter:['==',['get','kind'],'summit']},{id:'peak-labels',minzoom:14});
 const original=a.map.getStyle;a.map.getStyle=()=>({...original(),sources:{...original().sources,osm:{type:'vector'}}});
 a.sources.osm=[point(1,{class:'peak',name:'Mount Example',poi_icon:'mountain',min_zoom:11})];
 a.map.getZoom=()=>12;a.events.idle();assert.equal(a.hidden('ranked-peaks').size,0);
 a.map.getZoom=()=>14;a.events.idle();assert.ok(a.hidden('ranked-peaks').has(3));a.events.remove();
});
test('ranked campground gates its cluster but never loses close-zoom members',()=>{
 const f=agency(2);Object.assign(f.properties,{label_minzoom:12,label_rank:7,rank_family:'destination'});
 const group=point(3,{kind:'group',group_id:'way/1',name:'Fallen Leaf Campground',grid_image:'amenity-grid:campsite,toilet',min_zoom:10});
 const a=setup([camp(1),group],[f]);a.layers.push({id:'amenity-groups',filter:['==',['get','kind'],'group']});
 a.map.getZoom=()=>11;a.events.idle();assert.ok(a.hidden('amenity-groups').has(3));assert.equal(a.hidden('recreation-pois').size,0);
 a.map.getZoom=()=>12;a.events.idle();assert.equal(a.hidden('amenity-groups').size,0);assert.ok(a.hidden('recreation-pois').has(2));
 a.map.getZoom=()=>16;a.events.idle();assert.equal(a.hidden('amenity-group-members').size,0);a.events.remove();
});
test('date-line neighbors match from either longitude direction',()=>{
 for(const [left,right] of [[179.999,-179.999],[-179.999,179.999]]){
  const f=agency(2,'Example Peak','summit',left),g=agency(3,'Example Peak','summit',right);
  const a=setup([],[f,g]);assert.equal(a.hidden('recreation-pois').size,1);a.events.remove();
 }
});


test('Sentinel nearby named toilets share one symbol then reveal original locations without repeated labels',()=>{
 const f=agency(1,'Sentinel Vault Toilet','restroom',-119.6045964892899),g=agency(2,'Sentinel Vault Toilet','restroom',-119.60555058546193);
 f.geometry.coordinates[1]=37.734398846399046;g.geometry.coordinates[1]=37.73454089634393;
 f.properties.unit=g.properties.unit='Yosemite National Park';f.properties.min_zoom=g.properties.min_zoom=15;
 const coords=JSON.stringify([f.geometry,g.geometry]);const a=setup([],[g,f]);
 assert.ok(a.hidden('recreation-poi-details').has(2));assert.equal(a.hidden('recreation-poi-details').size,1);
 const p=a.map.__topoPoiDetails.get('nps:1').properties;
 assert.equal(p.display_group_count,2);assert.equal(JSON.parse(p.source_records).length,2);
 const layouts=[];a.map.setLayoutProperty=(id,name,value)=>layouts.push({id,name,value});a.map.getZoom=()=>17;a.events.idle();
 assert.equal(a.hidden('recreation-poi-details').size,0);
 const text=layouts.find(l=>l.name==='text-field').value;assert.equal(text[0],'case');assert.equal(text[1][2][1][0],2);assert.equal(text[2],'');
 assert.equal(JSON.stringify([f.geometry,g.geometry]),coords);
 a.map.getZoom=()=>16;a.events.idle();assert.ok(a.hidden('recreation-poi-details').has(2));a.events.remove();
});
test('nearby generic facilities, different names, areas, and distant locations are not grouped',()=>{
 for(const variant of ['generic','name','area','distance','kind']){
  const f=agency(1,'Sentinel Vault Toilet','restroom'),g=agency(2,'Sentinel Vault Toilet','restroom',-120.001);
  f.properties.unit=g.properties.unit='Yosemite';
  if(variant==='generic')f.properties.name=g.properties.name='Vault Toilet';
  if(variant==='name')g.properties.name='Sentinel East Toilet';
  if(variant==='area')g.properties.unit='Other park';
  if(variant==='distance')g.geometry.coordinates[0]=-120.01;
  if(variant==='kind')g.properties.kind='drinking_water';
  const a=setup([],[f,g]);assert.equal(a.hidden('recreation-poi-details').size,0,variant);a.events.remove();
 }
});

test('matching index includes external IDs gained by a canonical merged record',()=>{
 const first=agency(1,'Shared Camp');first.properties.agency='NPS';first.properties.ridb_id='123';
 const second=agency(2,'Shared Camp');second.properties.agency='USFS';second.properties.ridb_id='123';second.properties.geonames_id='456';
 const third=agency(3,'Different published name');third.properties.agency='GeoNames';third.properties.geonames_id='456';
 const a=setup([],[third,second,first]);assert.equal(a.hidden('recreation-pois').size,2);assert.equal(a.map.__topoPoiDetails.get('nps:1').properties.source_count,3);a.events.remove();
});
test('candidate index preserves summit-rock cross-kind matches and conflicting source IDs',()=>{
 const first=agency(1,'Granite Example','summit');first.properties.gnis_id='100';
 const second=agency(2,'Granite Example','rock');second.properties.gnis_id='100';
 const conflict=agency(3,'Granite Example','rock');conflict.properties.gnis_id='200';
 const a=setup([],[first,second,conflict]);assert.ok(a.hidden('recreation-pois').has(2));assert.ok(!a.hidden('recreation-pois').has(3));a.events.remove();
});

test('agency information stays visible until its standalone OSM replacement is eligible',()=>{
 for(const minimum of [15,17]){
  const sign=point(1,{kind:'amenity',poi_icon:'information',name:'Forest Kiosk',osm_id:'node/1',group_id:'',...(minimum===17?{detail_minzoom:17}:{})});
  const a=setup([sign],[agency(2,'Forest Kiosk','information')]);
  a.map.getZoom=()=>minimum-.01;a.events.idle();assert.equal(a.hidden('recreation-pois').size,0);
  a.map.getZoom=()=>minimum;a.events.idle();assert.ok(a.hidden('recreation-pois').has(2));a.events.remove();
 }
});

test('one coherent style snapshot serves the entire POI matching refresh',()=>{
 const a=setup([camp(1)],[agency(2)]),getStyle=a.map.getStyle;let reads=0;
 a.map.getStyle=()=>{reads++;return getStyle()};a.events.idle();assert.equal(reads,1);assert.ok(a.hidden('recreation-pois').has(2));a.events.remove();
});
