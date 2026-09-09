import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
const literal=fs.readFileSync(new URL('../src/poiImages.ts',import.meta.url),'utf8').replace(/^\/\/.*\n/,'').replace('export const poiImagesScript = ','');
const code=JSON.parse(literal.trim().replace(/;$/,''));
let pathDraws=0;const ctx={beginPath(){},moveTo(){},lineTo(){},quadraticCurveTo(){},closePath(){},arc(){},stroke(){},save(){},restore(){},translate(){},scale(){},fill(path){if(path){assert.ok(path.d.length>5);pathDraws++}},getImageData(){return{width:48,height:48,data:new Uint8ClampedArray(48*48*4)}}};
const scope=vm.createContext({Path2D:class{constructor(d){this.d=d}},document:{createElement:()=>({getContext:(_type,options)=>{assert.equal(options.willReadFrequently,true);return ctx}})}});vm.runInContext(code,scope);
const embedded=vm.runInContext('POI_PATHS',scope);
const requestAll=()=>{for(const frame of ['square','circle'])for(const name of Object.keys(embedded))events.styleimagemissing({id:'poi-'+frame+'-'+name})};
const events={},images=new Map();scope.installPoiImages({hasImage:id=>images.has(id),addImage:(id,image,options)=>images.set(id,{image,options}),on:(name,fn)=>events[name]=fn,isStyleLoaded:()=>false});
assert.equal(images.size,0);assert.equal(events['style.load'],undefined,'style load does not draw unused icons');events.styleimagemissing({id:'poi-square-cafe'});assert.equal(images.size,1);requestAll();assert.equal(images.size,56);assert.ok(pathDraws>=56);
for(const frame of ['square','circle'])for(const name of ['restaurant','cafe','toilet','drinking-water','parking','fuel','information','hospital','pharmacy','picnic-site','campsite','lodging','mountain','viewpoint','park','monument','museum','shop','swimming','marker']){const asset=images.get('poi-'+frame+'-'+name);assert.equal(asset.image.width,48);assert.equal(asset.image.height,48);assert.equal(asset.options.pixelRatio,2)}
const draws=pathDraws;requestAll();events.styleimagemissing({id:'poi-square-unknown'});events.styleimagemissing({id:'shield-us'});assert.equal(pathDraws,draws);images.clear();requestAll();assert.equal(images.size,56);
assert.ok(!code.includes('fetch('));assert.ok(!literal.includes('.toString('));
const assetRoot=new URL('../../../assets/maki/',import.meta.url),manifest=JSON.parse(fs.readFileSync(new URL('source.json',assetRoot),'utf8'));
assert.equal(manifest.icons.length,20);assert.equal(manifest.license,'CC0-1.0');assert.match(manifest.commit,/^[a-f0-9]{40}$/);
for(const icon of manifest.icons){const bytes=fs.readFileSync(new URL(icon.file,assetRoot));assert.equal(createHash('sha256').update(bytes).digest('hex'),icon.sha256);assert.ok(icon.source_url.includes(manifest.commit));const originals=[...bytes.toString().matchAll(/<path\b[^>]*\bd="([^"]+)"/g)].map(m=>m[1].replace(/&#x([\da-f]+);/gi,(_,h)=>String.fromCodePoint(parseInt(h,16))).replace(/&#(\d+);/g,(_,d)=>String.fromCodePoint(Number(d))).replace(/\s+/g,''));assert.deepEqual(Array.from(embedded[icon.name],d=>d.replace(/\s+/g,'')),originals);assert.ok(!/\b(?:transform|fill-rule|clip-path|stroke)=/.test(bytes.toString()))}
assert.equal(createHash('sha256').update(fs.readFileSync(new URL(manifest.license_file,assetRoot))).digest('hex'),manifest.license_sha256);
console.log('56 POI variants, canvas path drawing, style reload, missing-image handling, offline literal and pinned original/license hashes passed.');

for(const icon of ['waterfall','cascade','arch','cave','spring','rock','pass','shelter']){assert.ok(embedded[icon]);assert.notDeepEqual(Array.from(embedded[icon]),Array.from(embedded.marker));assert.ok(images.has('poi-circle-'+icon))}

const probe={hasImage:()=>true,addImage(){},on(){},isStyleLoaded:()=>false};scope.installPoiImages(probe);
assert.equal(probe.__topoPoiIcon({kind:'waterfall',name:'The Cascades',poi_image:'poi-circle-marker'}),'poi-circle-cascade');
assert.equal(probe.__topoPoiIcon({kind:'waterfall',name:'Vernal Fall'}),'poi-circle-waterfall');
assert.equal(probe.__topoPoiIcon({kind:'arch',name:'Cascade Arch'}),'poi-circle-arch');
assert.equal(probe.__topoPoiIcon({kind:'spring'}),'poi-circle-spring');
assert.equal(probe.__topoPoiIcon({kind:'drinking_water',poi_icon:'drinking-water'}),null);
assert.equal(probe.__topoPoiIcon({class:'cave_entrance'}),'poi-circle-cave');
