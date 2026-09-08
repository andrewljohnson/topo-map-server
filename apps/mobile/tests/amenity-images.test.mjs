import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
test('amenity grid is a single offline image with three columns and correct rows',()=>{
 const literal=fs.readFileSync(new URL('../src/amenityImages.ts',import.meta.url),'utf8');
 const code=JSON.parse(literal.slice(literal.indexOf('=')+1).trim().replace(/;$/,''));
 const events={},images=new Map(),draws=[];
 const ctx={putImageData(){},drawImage(...args){draws.push(args.slice(1))},getImageData(x,y,width,height){return {width,height}}};
 const context=vm.createContext({Uint8ClampedArray,ImageData:class{},document:{createElement:()=>({getContext:()=>ctx})}});
 vm.runInContext(code,context);
 context.installAmenityImages({hasImage:id=>images.has(id),getImage:()=>({data:{width:48,height:48,data:new Uint8ClampedArray(48*48*4)}}),addImage:(id,image,options)=>images.set(id,{image,options}),on:(event,fn)=>events[event]=fn});
 const id='amenity-grid:campsite,drinking-water,toilet,parking';events.styleimagemissing({id});
 assert.equal(images.get(id).image.width,132);assert.equal(images.get(id).image.height,88);assert.equal(images.get(id).options.pixelRatio,2);assert.equal(draws.length,4);
 events.styleimagemissing({id});events.styleimagemissing({id:'shield-us'});assert.equal(draws.length,4);
 assert.ok(!code.includes('fetch('));assert.ok(!code.includes('exports.'));
});

test('nationwide style composes vector amenities with the same offline grid layout',async()=>{
 const {createStyle}=await import('../src/style.mjs');
 const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'topo://osm/{z}/{x}/{y}.pbf',undefined,'topo://amenities/{z}/{x}/{y}.pbf');
 assert.equal(style.sources.amenities.type,'vector');
 const groups=style.layers.find(l=>l.id==='amenity-groups');
 const details=style.layers.find(l=>l.id==='amenity-details');
 assert.equal(groups['source-layer'],'amenities');assert.equal(details['source-layer'],'amenities');
 assert.equal(groups.maxzoom,15);assert.equal(details.minzoom,14);
 assert.equal(groups.layout['icon-allow-overlap'],false);
});

test('cluster members survive source maxzoom and hand off at zoom 15',async()=>{
 const {createStyle}=await import('../src/style.mjs');
 const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'topo://osm/{z}/{x}/{y}.pbf',undefined,'topo://amenities/{z}/{x}/{y}.pbf');
 const groups=style.layers.find(l=>l.id==='amenity-groups');
 const members=style.layers.find(l=>l.id==='amenity-group-members');
 const details=style.layers.find(l=>l.id==='amenity-details');
 assert.ok(members.minzoom>style.sources.amenities.maxzoom);
 assert.equal(groups.maxzoom,members.minzoom,'no gap between clusters and individual locations');
 assert.equal(members['source-layer'],'amenities');
 for(const layer of [members,details])assert.ok(!JSON.stringify(layer.filter).includes('["zoom"]'),'member selection must not depend on capped source tile zoom');
 assert.deepEqual(members.filter,['all',['==',['get','kind'],'amenity'],['!=',['coalesce',['get','group_id'],''],'']]);
 assert.deepEqual(details.filter,['all',['==',['get','kind'],'amenity'],['==',['coalesce',['get','group_id'],''],'']]);
});

test('coincident members get stable separate icon offsets without moving feature coordinates',async()=>{
 const literal=fs.readFileSync(new URL('../src/amenityImages.ts',import.meta.url),'utf8');
 const code=JSON.parse(literal.slice(literal.indexOf('=')+1).trim().replace(/;$/,''));
 const events={},updates=[];let zoom=15;
 const member=(id,point,group_id='camp')=>({id,geometry:{coordinates:point},properties:{kind:'amenity',group_id}});
 let features=[member(2,[-120,39]),member(1,[-120,39]),member(2,[-120,39]),member(3,[-120.01,39])];
 const original=JSON.stringify(features);
 const context=vm.createContext({setTimeout,clearTimeout});
 vm.runInContext(code,context);
 context.installAmenityImages({on:(name,fn)=>events[name]=fn,off:name=>delete events[name],getLayer:()=>true,getZoom:()=>zoom,project:([x,y])=>({x:x*100000,y:y*100000}),getStyle:()=>({sources:{amenities:{type:'vector'}}}),querySourceFeatures:()=>features,setLayoutProperty:(...args)=>updates.push(JSON.parse(JSON.stringify(args)))});
 events.idle();
 assert.equal(JSON.stringify(features),original,'locations remain unchanged');
 assert.deepEqual(updates[0],['amenity-group-members','icon-offset',['match',['id'],2,['literal',[0,-28]],['literal',[0,0]]]]);
 events.idle();assert.equal(updates.length,1,'no repeated style work at idle');
 events['style.load']();events.idle();assert.equal(updates.length,2,'reapply after style replacement');
 features=[member(3,[-120.01,39])];events.idle();assert.deepEqual(updates[2].at(-1),[0,0],'clear offsets after leaving coincident points');
 zoom=14;features=[member(1,[0,0]),member(2,[0,0])];events.idle();assert.equal(updates.length,3,'overview cluster placement is unaffected');
 zoom=15;events.sourcedata({sourceId:'amenities'});await new Promise(resolve=>setTimeout(resolve,70));assert.equal(updates.length,4,'update when amenities arrive without waiting for other map layers to become idle');
 events.remove();assert.equal(events.idle,undefined);assert.equal(events.sourcedata,undefined);
});


test('detail symbols retain site service grids and lakes compose glow beneath shoreline',async()=>{
 const {createStyle}=await import('../src/style.mjs');const style=createStyle({bounds:[-180,-85,180,85],minZoom:0,maxZoom:14},'topo://osm/{z}/{x}/{y}.pbf',undefined,'topo://amenities/{z}/{x}/{y}.pbf');
 for(const id of ['amenity-details','amenity-group-members'])assert.deepEqual(style.layers.find(l=>l.id===id).layout['icon-image'].slice(0,2),['coalesce',['get','grid_image']]);
 const index=id=>style.layers.findIndex(l=>l.id===id);assert.ok(index('water')<index('lake-shore-glow'));assert.ok(index('lake-shore-glow')<index('shorelines'));
});
