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
 const output=document.createElement('output');output.setAttribute('aria-label','Map rendering diagnostics');
 Object.assign(output.style,{position:'absolute',top:'70px',left:'10px',right:'10px',maxHeight:'250px',overflow:'auto',background:'#fffffff2',font:'10px monospace',whiteSpace:'pre-wrap',zIndex:'50',padding:'8px',pointerEvents:'none'});map.getContainer().appendChild(output);
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
 map.on('remove',()=>{clearInterval(timer);graphics.dispose();observe.disconnect();longObserver.disconnect();document.removeEventListener('visibilitychange',visibility);map.off('render',rendered);output.remove();map.off('sourcedata',data);map.off('load',load);map.off('idle',idle);map.off('error',error)});
}
