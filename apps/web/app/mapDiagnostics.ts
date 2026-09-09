// Opt-in local proofing instrumentation; never enabled by the normal cloud build.
export function profileMapGraphics(){
 const calls:any={},restore:any[]=[];
 for(const constructor of [globalThis.WebGLRenderingContext,globalThis.WebGL2RenderingContext,globalThis.CanvasRenderingContext2D]){
  if(!constructor)continue;const proto=constructor.prototype as any;
  for(const name of ['compileShader','linkProgram','getShaderParameter','getProgramParameter','drawArrays','drawElements','readPixels','texImage2D','texSubImage2D','getImageData','drawImage']){
   if(!Object.hasOwn(proto,name)||typeof proto[name]!=='function')continue;const original=proto[name],key=constructor.name+'.'+name;
   proto[name]=function(...args:any[]){const start=performance.now();try{return original.apply(this,args)}finally{const ms=performance.now()-start;if(ms>10){const entry=calls[key]??={count:0,total:0,max:0};entry.count++;entry.total+=Math.round(ms);entry.max=Math.max(entry.max,Math.round(ms))}}};restore.push(()=>proto[name]=original);
  }
 }
 return {calls,dispose(){for(const fn of restore)fn()}};
}
export function installMapDiagnostics(map:any,start:number,bootstrap:any[],graphics:any){
 if(new URLSearchParams(location.search).has('collisions'))map.showCollisionBoxes=true;
 const output=document.createElement('output');output.setAttribute('aria-label','Map rendering diagnostics');
 Object.assign(output.style,{position:'absolute',top:'70px',left:'10px',right:'10px',maxHeight:'250px',overflow:'auto',background:'#fffffff2',font:'10px monospace',whiteSpace:'pre-wrap',zIndex:'50',padding:'8px',pointerEvents:'none'});map.getContainer().appendChild(output);
 const exportButton=document.createElement('button');exportButton.textContent='Save map proof';exportButton.setAttribute('aria-label','Save map proof');
 Object.assign(exportButton.style,{position:'absolute',top:'70px',right:'12px',zIndex:'60',background:'white',border:'1px solid #ddd',borderRadius:'6px',padding:'8px',font:'12px sans-serif'});map.getContainer().appendChild(exportButton);
 if(new URLSearchParams(location.search).has('proof'))output.style.display='none';
 exportButton.onclick=()=>{
  if(!map.areTilesLoaded()){exportButton.textContent='Waiting for tiles';return}
  exportButton.disabled=true;exportButton.textContent='Saving map proof';
  map.once('render',async()=>{try{
   const canvas=map.getCanvas(),copy=document.createElement('canvas'),scale=canvas.width/map.getContainer().clientWidth;copy.width=canvas.width;copy.height=canvas.height+34*scale;
   const c=copy.getContext('2d',{willReadFrequently:true})!;c.drawImage(canvas,0,0);
   c.fillStyle='#fff';c.fillRect(0,canvas.height,copy.width,34*scale);c.fillStyle='#385348';c.font=(9*scale)+'px sans-serif';c.fillText('© OpenStreetMap contributors · GeoNames (CC BY 4.0)',8*scale,canvas.height+13*scale);c.fillText('USGS · USFS · NPS · Protomaps · PCTA · Natural Earth',8*scale,canvas.height+26*scale);
   const bounds=map.getBounds(),center=map.getCenter();const view={capturedAt:new Date().toISOString(),release:new URLSearchParams(location.search).get('release'),bounds:[bounds.getWest(),bounds.getSouth(),bounds.getEast(),bounds.getNorth()],center:[center.lng,center.lat],zoom:map.getZoom(),bearing:map.getBearing(),pitch:map.getPitch(),viewport:{width:map.getContainer().clientWidth,height:map.getContainer().clientHeight}};
   const candidatePeaks=['osm__poi','recreation__recreation'].flatMap(sourceLayer=>map.querySourceFeatures('osm',{sourceLayer}).filter((f:any)=>f.geometry.type==='Point'&&bounds.contains(f.geometry.coordinates)&&(f.properties.poi_icon==='mountain'||f.properties.kind==='summit')).map((f:any)=>({sourceLayer,id:f.id,coordinates:f.geometry.coordinates,properties:f.properties})));
   const renderedPeaks=map.queryRenderedFeatures({layers:['peak-labels','ranked-peaks'].filter(id=>map.getLayer(id))}).map((f:any)=>({name:f.properties.name,layer:f.layer.id,coordinates:f.geometry.coordinates}));
   const symbolLayers=map.getStyle().layers.filter((l:any)=>l.type==='symbol').map((l:any)=>l.id);
   const renderedSymbols=map.queryRenderedFeatures({layers:symbolLayers}).map((f:any)=>({layer:f.layer.id,sourceLayer:f.sourceLayer,id:f.id,name:f.properties.name,badge:f.properties.badge,kind:f.properties.kind,geometryType:f.geometry.type,...(f.geometry.type==='Point'?{coordinates:f.geometry.coordinates}:{})}));
   const styleSha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(map.getStyle()))))).map(b=>b.toString(16).padStart(2,'0')).join('');
   const response=await fetch('/__proof',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:copy.toDataURL('image/png'),view:{...view,styleSha256,candidatePeaks,renderedPeaks,renderedSymbols},label:'z'+view.zoom.toFixed(2)+'-'+center.lat.toFixed(4)+'-'+center.lng.toFixed(4)})});
   if(!response.ok)throw Error('Local proof server required');const result=await response.json() as {saved:string};exportButton.textContent='Map proof saved';exportButton.title=result.saved;
  }catch(e){exportButton.textContent=String(e)}finally{exportButton.disabled=false}});map.triggerRepaint();
 };
 const report:any={elapsed:0,first:{},firstTiles:{},bootstrap,graphics:graphics.calls,sourceEvents:{},requests:[],errors:[],maxTimerGap:0,longTasks:[],visibilityChanges:[{state:document.visibilityState,ms:Math.round(performance.now()-start)}]};const seen=new Set<string>();
 const elapsed=()=>Math.round(performance.now()-start);
 const resources=(entries:any[])=>{for(const e of entries||[]){const key=e.name+'|'+e.startTime;if(seen.has(key))continue;seen.add(key);const url=new URL(e.name,location.href);report.requests.push({path:url.pathname,start:Math.round(e.startTime-start),duration:Math.round(e.duration),bytes:e.transferSize||0});if(report.requests.length>100)report.requests.shift();}};
 const observe=new PerformanceObserver(list=>resources(list.getEntries()));observe.observe({type:'resource',buffered:true});
 const longObserver=new PerformanceObserver(list=>{for(const e of list.getEntries())if(e.duration>100)report.longTasks.push({start:Math.round(e.startTime-start),duration:Math.round(e.duration)});report.longTasks=report.longTasks.slice(-12)});longObserver.observe({type:'longtask',buffered:true});
 const visibility=()=>report.visibilityChanges.push({state:document.visibilityState,ms:elapsed()});document.addEventListener('visibilitychange',visibility);
 const rendered=()=>{if(!report.first.render)report.first.render=elapsed()};map.on('render',rendered);
 const data=(e:any)=>{report.sourceEvents[e.sourceId]=(report.sourceEvents[e.sourceId]||0)+1;if(e.sourceDataType==='content'&&!report.first[e.sourceId])report.first[e.sourceId]=elapsed();if(e.tile&&!report.firstTiles[e.sourceId])report.firstTiles[e.sourceId]=elapsed();resources(e.resourceTiming||e.tile?.resourceTiming||[])};
 const load=()=>{report.first.load=elapsed()};const idle=()=>{if(!report.first.idle)report.first.idle=elapsed();const names=/Fontanillis|Velma|Dicks|Fallen Leaf/;report.lakeLabels={layers:map.getStyle().layers.filter((l:any)=>l.id.startsWith('lake-labels')).map((l:any)=>l.id),candidates:map.querySourceFeatures('osm',{sourceLayer:'osm__water_label'}).filter((f:any)=>names.test(f.properties.name)).map((f:any)=>({name:f.properties.name,min:f.properties.min_zoom,angle:f.properties.label_angle,fit:f.properties.label_horizontal_zoom,coordinates:f.geometry.coordinates})),rendered:map.queryRenderedFeatures({layers:map.getStyle().layers.filter((l:any)=>l.id.startsWith('lake-labels')).map((l:any)=>l.id)}).map((f:any)=>f.properties.name)}};
 const error=(e:any)=>{if(report.errors.length<8)report.errors.push(String(e.error?.message||e.error))};
 map.on('sourcedata',data);map.on('load',load);map.on('idle',idle);map.on('error',error);
 let lastTick=performance.now();
 const timer=setInterval(()=>{const now=performance.now();report.maxTimerGap=Math.max(report.maxTimerGap,Math.round(now-lastTick));lastTick=now;report.visibility=document.visibilityState;report.elapsed=elapsed();report.icons=map.__topoIconStats;report.loaded=map.loaded();report.tilesLoaded=map.areTilesLoaded();output.textContent=JSON.stringify({...report,requests:[...report.requests].sort((a:any,b:any)=>b.duration-a.duration).slice(0,10)},null,1)},1000);
 map.on('remove',()=>{clearInterval(timer);graphics.dispose();observe.disconnect();longObserver.disconnect();document.removeEventListener('visibilitychange',visibility);map.off('render',rendered);output.remove();exportButton.remove();map.off('sourcedata',data);map.off('load',load);map.off('idle',idle);map.off('error',error)});
}
