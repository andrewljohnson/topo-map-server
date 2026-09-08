import fs from 'node:fs';
import {createRequire} from 'node:module';
const root=new URL('../',import.meta.url).pathname.replace(/\/$/,'');const require=createRequire(root+'/apps/mobile/package.json');const ts=require('typescript');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/home/andrew/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
function moduleUrl(name){let code=ts.transpileModule(fs.readFileSync(root+'/apps/mobile/src/'+name+'.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;code=code.replace(/from ['"]\.\/(\w+)['"]/g,(_,n)=>'from '+JSON.stringify(moduleUrl(n)));return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64')}
const {mapHtml}=await import(moduleUrl('map'));const {createStyle}=await import((process.env.REVIEW_STYLE||root+'/apps/mobile/src/style.mjs')+'?'+Date.now());
fs.writeFileSync('/tmp/topo-review.html',mapHtml());
const out=process.env.PROOF_OUTPUT||root+'/docs/qa/cartography';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/home/andrew/.cache/ms-playwright/chromium-1148/chrome-linux/chrome',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-webgl']});
const page=await browser.newPage({viewport:{width:430,height:860},deviceScaleFactor:1});page.on('pageerror',e=>console.log('PAGE',e.message));page.on('console',m=>{if(m.type()==='error')console.log('ERR',m.text().slice(0,180))});
// Match native source lanes so slow optional sources cannot occupy every slot.
const transport=new Map(),networkAbort=new AbortController();
async function limitedFetch(url,options={}){const lane=new URL(url).pathname.split('/')[1],limit=['tiles','dem'].includes(lane)?2:1;let gate=transport.get(lane);if(!gate){gate={active:0,waiting:[]};transport.set(lane,gate)}if(gate.active>=limit)await new Promise(resolve=>gate.waiting.push(resolve));gate.active++;try{return await fetch(url,{...options,signal:AbortSignal.any([networkAbort.signal,...(options.signal?[options.signal]:[])])})}finally{gate.active--;gate.waiting.shift()?.()}}
await page.route('http://localhost:3001/**',async route=>{try{const response=await limitedFetch(route.request().url(),{signal:AbortSignal.timeout(180000)});await route.fulfill({status:response.status,headers:{'content-type':response.headers.get('content-type')||'application/octet-stream','access-control-allow-origin':'*'},body:Buffer.from(await response.arrayBuffer())})}catch{await route.abort().catch(()=>{})}});
const tileMemory=new Map(),requests=[],failures=[];let offline=false;
await page.exposeFunction('nativeMessage',async text=>{const m=JSON.parse(text);if(m.type==='mapError'){failures.push(m.message);console.log('MAPERROR',m.message);return}if(m.type!=='tile')return;requests.push(m.key);try{let bytes=tileMemory.get(m.key);if(!bytes){if(offline)throw Error('Not saved: '+m.key);const [name,z,x,y]=m.key.split('/'),spec=meta.tilesets[name];const path=spec.tileUrl.replace('{z}',z).replace('{x}',x).replace('{y}',y);const res=await limitedFetch('http://localhost:3001'+path,{signal:AbortSignal.timeout(180000)});if(!res.ok)throw Error(res.status+' '+m.key);bytes=Buffer.from(await res.arrayBuffer()).toString('base64');tileMemory.set(m.key,bytes)}await page.evaluate(m=>window.receive(m),{type:'tile',id:m.id,src:bytes})}catch(e){failures.push(String(e));await page.evaluate(m=>window.receive(m),{type:'tile',id:m.id,error:String(e)}).catch(()=>{})}});
await page.addInitScript(()=>{window.ReactNativeWebView={postMessage:m=>window.nativeMessage(m)}});await page.goto('file:///tmp/topo-review.html');


const meta=await (await limitedFetch('http://localhost:3001/metadata')).json();
const url=name=>'http://localhost:3001/'+name+'/{z}/{x}/{y}.pbf';
const style=createStyle(meta,url('tiles'),'topocontour://{z}/{x}/{y}',url('amenities'),url('boundaries'),url('waterways'),url('landcover'),url('trails'),url('recreation'));
await page.evaluate(m=>window.receive(m),{type:'init',meta,style});
const areas=await (await limitedFetch('http://localhost:3001/areas.geojson')).json();await page.evaluate(m=>window.receive(m),{type:'areas',data:areas});
await page.evaluate(m=>window.receive(m),{type:'safeArea',insets:{top:59,bottom:34,left:0,right:0}});
const prefix=process.env.DENSITY_PASS||'cartography-final';const rows=[];
let shot=0;for(const [name,center,zooms] of JSON.parse(process.env.PROOF_SCENES||"[[\"yosemite\", [-119.605, 37.74], [7, 10, 13, 15, 13, 10]], [\"fallen-leaf\", [-120.052, 38.925], [12, 14, 15, 17, 14]], [\"desolation\", [-120.16, 38.935], [11, 14, 11]], [\"boundary-waters\", [-90.95, 48.12], [9, 12, 15]], [\"zion\", [-112.98, 37.3], [8, 11, 14]], [\"bar-harbor\", [-68.205, 44.385], [10, 13, 16]]]")){
 for(const zoom of (process.env.DENSITY_REVERSE?[...zooms,...zooms.slice(0,-1).reverse()]:zooms)){
  const failureStart=failures.length,start=Date.now();
  await page.evaluate(({center,zoom})=>map.jumpTo({center,zoom}),{center,zoom});
  const loaded=await page.waitForFunction(()=>map.getStyle()&&['osm','dem','contours','amenities','recreation','trails','landcover','waterways','boundaries'].every(id=>map.isSourceLoaded(id)),{},{timeout:Number(process.env.PROOF_TIMEOUT_MS||180000)}).then(()=>true).catch(()=>false);
  await page.waitForTimeout(600);
  const state=await page.evaluate(()=>{const fs=map.queryRenderedFeatures();const symbols=fs.filter(f=>f.layer.type==='symbol');const ids=new Map();for(const f of symbols)ids.set(f.layer.id,(ids.get(f.layer.id)||0)+1);return {terrain:map.__topoTerrainStats,contours:fs.filter(f=>f.source==='contours').length,sourceLoaded:Object.fromEntries(Object.keys(map.getStyle().sources).map(k=>[k,map.isSourceLoaded(k)])),layers:Object.fromEntries(ids),peaks:symbols.filter(f=>f.layer.id==='peak-labels'||f.properties.kind==='summit').map(f=>f.properties.name),destinations:symbols.filter(f=>f.layer.id==='amenity-groups'||f.layer.id.startsWith('recreation')).map(f=>f.properties.name),areaLabels:symbols.filter(f=>f.layer.id==='area-labels').map(f=>({name:f.properties.name,coordinates:f.geometry.coordinates})),matches:map.__topoPoiMatchStats}});
  rows.push({name,zoom,settled:loaded,loadMs:Date.now()-start,errors:failures.slice(failureStart),...state});console.log(JSON.stringify(rows.at(-1)));
  await page.screenshot({path:out+'/density-'+prefix+'-'+(++shot)+'-'+name+'-z'+zoom+'.png'});
 }
}
fs.writeFileSync(out+'/density-'+prefix+'.json',JSON.stringify(rows,null,2));fs.writeFileSync(out+'/'+prefix+'-network.json',JSON.stringify({requests,failures,cacheSize:tileMemory.size},null,2));networkAbort.abort();await browser.close();
