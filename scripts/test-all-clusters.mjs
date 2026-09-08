// Run audit-cluster-data.py first. Tests actual vector tiles against original member coordinates.
import fs from 'node:fs';
import {createRequire} from 'node:module';
const root=new URL('..',import.meta.url).pathname.replace(/\/$/,'');const require=createRequire(root+'/apps/mobile/package.json');const ts=require('typescript');
const {chromium}=require('/home/andrew/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
function moduleUrl(name){let code=ts.transpileModule(fs.readFileSync(root+'/apps/mobile/src/'+name+'.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;code=code.replace(/from ['"]\.\/(\w+)['"]/g,(_,n)=>'from '+JSON.stringify(moduleUrl(n)));return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64')}
const {mapHtml}=await import(moduleUrl('map'));const {createStyle}=await import((process.env.REVIEW_STYLE||root+'/apps/mobile/src/style.mjs')+'?'+Date.now());
fs.writeFileSync('/tmp/topo-review.html',mapHtml().replace('renderWorldCopies:true','fadeDuration:0,renderWorldCopies:true'));
const out=process.env.CLUSTER_AUDIT_OUTPUT||'/tmp/topo-cluster-audit';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'/home/andrew/.cache/ms-playwright/chromium-1148/chrome-linux/chrome',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-webgl']});
const page=await browser.newPage({viewport:{width:430,height:860},deviceScaleFactor:1});page.on('pageerror',e=>console.log('PAGE',e.message));page.on('console',m=>{if(m.type()==='error')console.log('ERR',m.text().slice(0,180))});
await page.route('**/amenities/**',route=>{const file='/tmp/topo-cluster-fixtures/'+new URL(route.request().url()).pathname.split('/').slice(2).join('/');return route.fulfill({status:200,contentType:'application/x-protobuf',body:fs.existsSync(file)?fs.readFileSync(file):Buffer.alloc(0)})});
await page.addInitScript(()=>{window.ReactNativeWebView={postMessage:m=>console.log(m)}});await page.goto('file:///tmp/topo-review.html');


const data=JSON.parse(fs.readFileSync('/tmp/topo-cluster-audit-data.json','utf8')),groups=data.groups;
const meta={bounds:[-180,-85,180,85],minZoom:0,maxZoom:14,center:groups[0].geometry.coordinates,initialZoom:15};
const style=createStyle(meta,'http://localhost:3001/tiles/{z}/{x}/{y}.pbf',undefined,'http://localhost:3001/amenities/{z}/{x}/{y}.pbf');
style.layers=style.layers.filter(l=>l.type==='background'||l.source==='amenities');
style.sources={amenities:style.sources.amenities};
await page.evaluate(m=>window.receive(m),{type:'init',meta,style});
const failures=[],results=[];
async function check(group,zoom,photo=false,bearing=0,pitch=0){
 await page.evaluate(({center,zoom,bearing,pitch})=>map.jumpTo({center,zoom,bearing,pitch}),{center:group.geometry.coordinates,zoom,bearing,pitch});
 await page.waitForFunction(()=>map.isStyleLoaded()&&map.areTilesLoaded(),{},{timeout:5000});
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))));
 const expectedMembers=data.features.filter(f=>f.properties.group_id===group.properties.group_id);
 const result=await page.evaluate(({gid,zoom,expectedMembers})=>{
  const rendered=map.queryRenderedFeatures(),ids=new Set(rendered.filter(f=>f.layer.id==='amenity-group-members').map(f=>f.properties.osm_id+'|'+f.properties.poi_icon));
  const expected=expectedMembers.filter(f=>{const p=map.project(f.geometry.coordinates);return p.x>40&&p.x<390&&p.y>40&&p.y<820});
  const duplicateKeys=new Set(map.querySourceFeatures('amenities',{sourceLayer:'amenities'}).filter(f=>map.__topoHiddenAmenityIds?.has(f.id)).map(f=>f.properties.osm_id+'|'+f.properties.poi_icon));
  return {deduplicated:expected.filter(f=>duplicateKeys.has(f.properties.osm_id+'|'+f.properties.poi_icon)).length,expected:expected.length,missing:zoom>=15?expected.filter(f=>!ids.has(f.properties.osm_id+'|'+f.properties.poi_icon)&&!duplicateKeys.has(f.properties.osm_id+'|'+f.properties.poi_icon)).map(f=>f.properties):[],groupVisible:rendered.some(f=>f.layer.id==='amenity-groups'&&f.properties.group_id===gid),offset:map.getLayoutProperty('amenity-group-members','icon-offset')};
 },{gid:group.properties.group_id,zoom,expectedMembers});
 if(result.missing.length||(zoom>=15&&result.groupVisible))failures.push({name:group.properties.name,zoom,...result});
 results.push({name:group.properties.name,zoom,expected:result.expected,missing:result.missing.length});
 if(photo)await page.screenshot({path:out+'/cluster-'+group.properties.name.replace(/[^a-z0-9]/gi,'-').slice(0,70)+'-z'+zoom+'.png'});
}
for(let i=0;i<groups.length;i++){
 await check(groups[i],15);
 if((i+1)%100===0)console.log(JSON.stringify({checked:i+1,total:groups.length,failures:failures.length}));
}
const special=groups.filter(g=>/Fallen Leaf|Hetch|Thunder hole|Lodgepole Campground|Seawall Campground|Watchman Campground|Housekeeping Camp|Blackwoods|Turlock Lake|Caribou Crossroads|Hicksons|Humpty|Alice.s Enchanted|Train Station Stop|Redwood Creek Picnic/i.test(g.properties.name));
for(const group of special)for(const zoom of [14.99,15.01,16,18])await check(group,zoom,true);
for(const group of special.slice(0,4))await check(group,16,false,60,45);
fs.writeFileSync(out+'/cluster-audit.json',JSON.stringify({groups:groups.length,checks:results.length,special:special.map(g=>g.properties.name),failures,results},null,2));
console.log(JSON.stringify({groups:groups.length,checks:results.length,failures:failures.slice(0,12)}));
await browser.close();
if(failures.length)process.exitCode=1;
