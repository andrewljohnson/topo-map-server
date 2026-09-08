import fs from 'node:fs';import {createRequire} from 'node:module';
const root=new URL('../',import.meta.url).pathname,require=createRequire(root+'apps/web/package.json');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/home/andrew/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=process.env.PROOF_OUTPUT||root+'docs/qa/cartography';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/home/andrew/.cache/ms-playwright/chromium-1148/chrome-linux/chrome',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-webgl']});const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],rows=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://localhost:3000');await page.waitForFunction(()=>window.__topoMap,{},{timeout:30000});
for(const [name,center,zoom]of [['overview',[-119.55,37.85],7],['yosemite',[-119.605,37.74],13],['campground',[-120.052,38.925],17]]){
 await page.evaluate(({center,zoom})=>window.__topoMap.jumpTo({center,zoom}),{center,zoom});await page.waitForFunction(()=>{const map=window.__topoMap;return map.getStyle()&&Object.keys(map.getStyle().sources).every(id=>map.isSourceLoaded(id))},{},{timeout:180000});await page.waitForTimeout(1200);
 const state=await page.evaluate(()=>{const map=window.__topoMap;return {terrain:map.__topoTerrainStats,layers:map.getStyle().layers.length,contours:map.queryRenderedFeatures().filter(f=>f.source==='contours').length}});rows.push({name,zoom,...state});console.log(JSON.stringify(rows.at(-1)));await page.screenshot({path:out+'/web-'+name+'.png'});
}
await page.getByRole('button',{name:'Map legend and attribution',exact:true}).click();const legend=await page.locator('.topo-info-sheet').innerText();if(!legend.includes('Shaded relief')||!legend.includes('Mapzen/AWS'))throw Error('Terrain legend or attribution missing');await page.screenshot({path:out+'/web-legend.png'});
fs.writeFileSync(out+'/web-proof.json',JSON.stringify({rows,errors},null,2));await browser.close();if(errors.length)throw Error(errors.join('\n'));
