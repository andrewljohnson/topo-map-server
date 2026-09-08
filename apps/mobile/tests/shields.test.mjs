import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const literal=fs.readFileSync(new URL('../src/shieldImages.ts',import.meta.url),'utf8').replace(/^\/\/.*\n/,'').replace('export const shieldImagesScript = ','');
const code=JSON.parse(literal.trim().replace(/;$/,''));
const draws=[];let current=[];
const context={beginPath(){},moveTo(){},quadraticCurveTo(){},lineTo(){},bezierCurveTo(){},closePath(){},fill(){current.push(this.fillStyle)},stroke(){current.push(this.strokeStyle)},save(){},clip(){},fillRect(){current.push(this.fillStyle)},restore(){},getImageData(){draws.push(current);current=[];return{width:64,height:64,data:new Uint8ClampedArray(64*64*4)}}};
const scope=vm.createContext({document:{createElement:()=>({getContext:()=>context})}});vm.runInContext(code,scope);
const images=new Map(),events={};const map={hasImage:id=>images.has(id),addImage:(id,image,options)=>images.set(id,{image,options}),on:(event,cb)=>events[event]=cb,isStyleLoaded:()=>false};
scope.installShieldImages(map);assert.equal(images.size,0);events.styleimagemissing({id:'shield-interstate'});assert.equal(images.size,1);events['style.load']();assert.equal(images.size,5);events.styleimagemissing({id:'unrelated'});events['style.load']();assert.equal(images.size,5);assert.equal(draws.length,5);
for(const [id,{image,options}]of images){assert.equal(image.data.length,16384);assert.equal(options.pixelRatio,4);assert.equal(options.content.length,4);assert.ok(options.stretchX[0][0]>=options.content[0]);assert.ok(options.stretchX[0][1]<=options.content[2]);}
assert.ok(draws[0].includes('#b9433b'));assert.ok(draws[0].includes('#285588'));assert.ok(draws[3].includes('#f3d474'));
images.clear();events['style.load']();assert.equal(images.size,5,'style reload regenerates assets');
assert.ok(!literal.includes('.toString('));
console.log('Shield IDs, dimensions, stretches, colors, synchronous missing-image registration, style reload, and Hermes-safe literal passed.');
