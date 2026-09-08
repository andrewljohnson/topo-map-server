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
const httpMemory=new Map();
await page.route('http://localhost:3001/**',async route=>{const url=route.request().url();try{let result=httpMemory.get(url);if(!result){if(offline)throw Error('Offline HTTP miss '+url);const response=await fetch(url,{signal:AbortSignal.timeout(180000)});result={status:response.status,headers:{'content-type':response.headers.get('content-type')||'application/octet-stream','access-control-allow-origin':'*'},body:Buffer.from(await response.arrayBuffer())};if(response.ok)httpMemory.set(url,result)}await route.fulfill(result)}catch(e){failures.push(String(e));await route.abort().catch(()=>{})}});
const tileMemory=new Map(),requests=[],failures=[];let offline=false;
await page.exposeFunction('nativeMessage',async text=>{const m=JSON.parse(text);if(m.type==='mapError'){failures.push(m.message);console.log('MAPERROR',m.message);return}if(m.type!=='tile')return;requests.push(m.key);try{let bytes=tileMemory.get(m.key);if(!bytes){if(offline)throw Error('Not saved: '+m.key);const [name,z,x,y]=m.key.split('/'),spec=meta.tilesets[name];const path=spec.tileUrl.replace('{z}',z).replace('{x}',x).replace('{y}',y);const res=await fetch('http://localhost:3001'+path,{signal:AbortSignal.timeout(180000)});if(!res.ok)throw Error(res.status+' '+m.key);bytes=Buffer.from(await res.arrayBuffer()).toString('base64');tileMemory.set(m.key,bytes)}await page.evaluate(m=>window.receive(m),{type:'tile',id:m.id,src:bytes})}catch(e){failures.push(String(e));await page.evaluate(m=>window.receive(m),{type:'tile',id:m.id,error:String(e)}).catch(()=>{})}});
await page.addInitScript(()=>{window.ReactNativeWebView={postMessage:m=>window.nativeMessage(m)}});await page.goto('file:///tmp/topo-review.html');


const meta=await (await fetch('http://localhost:3001/metadata')).json();
const url=name=>'http://localhost:3001/'+name+'/{z}/{x}/{y}.pbf';
meta.center=[-119.605,37.74];meta.initialZoom=15;
const style=createStyle(meta,url('tiles'),'topocontour://{z}/{x}/{y}',url('amenities'),url('boundaries'),url('waterways'),url('landcover'),url('trails'),url('recreation'));
await page.evaluate(m=>window.receive(m),{type:'init',meta,style});
const areas=await (await fetch('http://localhost:3001/areas.geojson')).json();await page.evaluate(m=>window.receive(m),{type:'areas',data:areas});
await page.evaluate(m=>window.receive(m),{type:'safeArea',insets:{top:59,bottom:34,left:0,right:0}});

const states=[];
for(const phase of ['online','online-landscape','offline','offline-landscape']){
 if(phase.startsWith('offline')){offline=true;requests.length=0;failures.length=0;await page.reload();await page.evaluate(m=>window.receive(m),{type:'init',meta,style});await page.evaluate(m=>window.receive(m),{type:'areas',data:areas});await page.evaluate(m=>window.receive(m),{type:'safeArea',insets:{top:59,bottom:34,left:0,right:0}});}
 const landscape=phase.endsWith('landscape');await page.setViewportSize(landscape?{width:860,height:430}:{width:430,height:860});await page.evaluate(m=>window.receive(m),{type:'safeArea',insets:landscape?{top:0,bottom:21,left:59,right:59}:{top:59,bottom:34,left:0,right:0}});await page.evaluate(landscape=>{map.resize();map.jumpTo({bearing:landscape?35:0,pitch:landscape?40:0})},landscape);
 await page.waitForFunction(()=>map.getStyle()&&Object.keys(map.getStyle().sources).every(id=>map.isSourceLoaded(id)),{},{timeout:180000});await page.waitForTimeout(1200);
 const state=await page.evaluate(()=>({terrain:map.__topoTerrainStats,contours:map.queryRenderedFeatures().filter(f=>f.source==='contours').length,sources:Object.fromEntries(Object.keys(map.getStyle().sources).map(id=>[id,map.isSourceLoaded(id)]))}));
 states.push({phase,...state});console.log(JSON.stringify(states.at(-1)));await page.screenshot({path:out+'/terrain-'+phase+'.png'});
 if(!state.terrain.generated||!state.contours||state.terrain.failed)throw Error('Terrain did not regenerate '+phase);
}
if(failures.length)throw Error(failures.join('\n'));
if(requests.some(k=>k.startsWith('contours/')))throw Error('Downloaded contour geometry');
fs.writeFileSync(out+'/terrain-offline-proof.json',JSON.stringify({states,offlineRequested:requests,rawTilesSaved:tileMemory.size,httpResponsesSaved:httpMemory.size,failures},null,2));await browser.close();
