/** Raw DEM transport is shared by GPU relief and a local contour worker. */
export function installDeviceTerrain(gl:any,style:any,spec:any,load:(key:string,c:AbortController)=>Promise<ArrayBuffer>,workerSource:string){
 if(!spec)return null;
 const blob=URL.createObjectURL(new Blob([workerSource],{type:'text/javascript'})),worker=new Worker(blob);URL.revokeObjectURL(blob);
 const cache=new Map<string,any>(),requests=new Map<number,any>(),demRequests=new Map<number,AbortController>();let sequence=0,disposed=false;
 worker.postMessage({type:'configure',maxZoom:spec.maxZoom??13,minZoom:spec.minZoom??3});
 const stats={generated:0,cancelled:0,failed:0,demRequests:0,demBytes:0,totalMs:0,maxMs:0,worker:true};
 function raw(key:string,signal:AbortSignal):Promise<ArrayBuffer>{
  if(signal.aborted)return Promise.reject(Error('Cancelled'));
  let entry=cache.get(key);
  if(!entry){const controller=new AbortController();entry={controller,refs:0,done:false};const own=entry;entry.promise=load(key,controller).then(data=>{own.done=true;stats.demRequests++;stats.demBytes+=data.byteLength;return data},e=>{if(cache.get(key)===own)cache.delete(key);throw e});cache.set(key,entry)}
  cache.delete(key);cache.set(key,entry);for(const [k,e] of cache){if(cache.size<=24)break;if(e.done)cache.delete(k)}
  entry.refs++;return new Promise((resolve,reject)=>{let ended=false;const finish=(error?:any,data?:ArrayBuffer)=>{if(ended)return;ended=true;signal.removeEventListener('abort',cancel);entry.refs--;if(!entry.done&&!entry.refs){entry.controller.abort();if(cache.get(key)===entry)cache.delete(key)}error?reject(error):resolve(data!.slice(0))};const cancel=()=>finish(Error('Cancelled'));signal.addEventListener('abort',cancel,{once:true});entry.promise.then((data:ArrayBuffer)=>finish(undefined,data),finish)});
 }
 async function decode(data:ArrayBuffer){
  const blob=new Blob([data],{type:'image/png'});let image:any;
  if(typeof createImageBitmap==='function')image=await createImageBitmap(blob);
  else{const url=URL.createObjectURL(blob);try{image=await new Promise<HTMLImageElement>((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('DEM image could not decode'));im.src=url})}finally{URL.revokeObjectURL(url)}}
  const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;const context=canvas.getContext('2d',{willReadFrequently:true});if(!context)throw Error('DEM decoder unavailable');context.drawImage(image,0,0);image.close?.();const rgba=context.getImageData(0,0,canvas.width,canvas.height).data,values=new Float32Array(canvas.width*canvas.height);
  for(let i=0;i<values.length;i++)values[i]=rgba[i*4]*256+rgba[i*4+1]+rgba[i*4+2]/256-32768;
  return {width:canvas.width,height:canvas.height,data:values};
 }
 worker.onmessage=async(event:any)=>{const m=event.data;if(disposed)return;
  if(m.type==='cancelDem'){demRequests.get(m.id)?.abort();return}
  if(m.type==='dem'){const controller=new AbortController();demRequests.set(m.id,controller);try{const tile=await decode(await raw(m.key,controller.signal));if(!controller.signal.aborted&&!disposed)worker.postMessage({type:'demResult',id:m.id,tile},[tile.data.buffer])}catch(e){if(!disposed)worker.postMessage({type:'demResult',id:m.id,error:String(e)})}finally{demRequests.delete(m.id)}return}
  const p=requests.get(m.id);if(!p)return;requests.delete(m.id);p.signal.removeEventListener('abort',p.cancel);if(m.error){stats.failed++;p.reject(Error(m.error))}else{stats.generated++;stats.totalMs+=m.ms;stats.maxMs=Math.max(stats.maxMs,m.ms);p.resolve({data:m.buffer})}
 };
 worker.onerror=()=>{for(const p of requests.values()){p.signal.removeEventListener('abort',p.cancel);p.reject(Error('Terrain worker failed'))}for(const c of demRequests.values())c.abort();requests.clear();stats.failed++};
 const key=(url:string)=>url.split('://')[1].split('?')[0].replace(/\.(png|pbf)$/,'');
 gl.addProtocol('topodem',(p:any,c:AbortController)=>raw(key(p.url),c.signal).then(data=>({data})));
 gl.addProtocol('topocontour',(p:any,c:AbortController)=>new Promise((resolve,reject)=>{if(c.signal.aborted){reject(Error('Cancelled'));return}const id=++sequence,[z,x,y]=key(p.url).split('/').map(Number);const cancel=()=>{requests.delete(id);worker.postMessage({type:'cancel',id});stats.cancelled++;reject(Error('Cancelled'))};requests.set(id,{resolve,reject,signal:c.signal,cancel});c.signal.addEventListener('abort',cancel,{once:true});worker.postMessage({type:'contour',id,z,x,y})}));
 style.sources.dem={type:'raster-dem',tiles:['topodem://{z}/{x}/{y}'],encoding:'terrarium',tileSize:spec.tileSize??512,minzoom:spec.minZoom??3,maxzoom:spec.maxZoom??13,bounds:spec.bounds,attribution:spec.attribution};
 style.sources.contours={type:'vector',tiles:['topocontour://{z}/{x}/{y}'],minzoom:Math.max(11,spec.minZoom??3),maxzoom:15,bounds:spec.bounds};
 const insert=style.layers.findIndex((l:any)=>l.id==='contours'||l.id==='waterways-perennial');
 style.layers.splice(insert,0,{id:'terrain-tint',type:'color-relief',source:'dem',minzoom:3,paint:{'color-relief-opacity':['interpolate',['linear'],['zoom'],3,.16,8,.12,13,.06],'color-relief-color':['interpolate',['linear'],['elevation'],-100,'#f4eedc',0,'#f4eedc',800,'#e8e2c9',1800,'#ded3bf',3000,'#e9e4df',4500,'#f7f6f3']}},{id:'terrain-shading',type:'hillshade',source:'dem',minzoom:3,paint:{'hillshade-method':'igor','hillshade-illumination-direction':315,'hillshade-illumination-anchor':'map','hillshade-exaggeration':['interpolate',['linear'],['zoom'],3,.3,8,.38,12,.3,16,.23],'hillshade-shadow-color':'#6f776b','hillshade-highlight-color':'#fffdf5','hillshade-accent-color':'#777d6e'}});
 for(const layer of style.layers){if(layer.source!=='contours')continue;layer.filter=[layer.id==='contours'?'==':'>=',['get','level'],layer.id==='contours'?0:1];
  if(layer.id==='contours'){layer.minzoom=12;layer.paint['line-opacity']=['interpolate',['linear'],['zoom'],12,.2,14,.3,18,.42];layer.paint['line-width']=['interpolate',['linear'],['zoom'],12,.35,16,.6,18,.75]}
  if(layer.id==='contour-index'){layer.paint['line-width']=['interpolate',['linear'],['zoom'],11,.55,14,.75,18,1];layer.paint['line-opacity']=.55}
  if(layer.id==='contour-labels'){layer.layout['symbol-spacing']=420;layer.layout['text-size']=10;layer.paint['text-halo-width']=1;layer.paint['text-halo-color']='#f5f1e5'}
 }
 if(spec.renderBounds?.length){
  const originals=style.layers.filter((l:any)=>['dem','contours'].includes(l.source));
  for(const source of ['dem','contours']){
   const template=style.sources[source];delete style.sources[source];
   for(let i=0;i<spec.renderBounds.length;i++)style.sources[source+'-region-'+i]={...template,bounds:spec.renderBounds[i]};
  }
  style.layers=style.layers.flatMap((l:any)=>originals.includes(l)?spec.renderBounds.map((bounds:any,i:number)=>({...l,id:l.id+'-region-'+i,source:l.source+'-region-'+i})):l);
 }
 // Keep geographic information prominent over supporting terrain and land cover.
 const textures:Record<string,{color:string;kind:string}>={'cover-wetland':{color:'#538c872d',kind:'wetland'},'cover-sand':{color:'#ab87452b',kind:'dots'},'cover-scrub':{color:'#79885822',kind:'dots'}};
 for(const layer of [...style.layers]){
  if(layer.type==='symbol'&&layer.paint?.['text-halo-width']){layer.paint['text-halo-width']=Math.min(Number(layer.paint['text-halo-width'])||1.3,1.3);layer.paint['text-halo-blur']=.35;}
  if(layer.id.startsWith('nlcd-')&&layer.type==='fill')layer.paint['fill-opacity']=['interpolate',['linear'],['zoom'],6,.65,10,.9,14,.8,17,.4,18,.3];
  if(layer.id.startsWith('waterways-')&&layer.type==='line')layer.paint['line-width']=['interpolate',['linear'],['zoom'],6,.4,12,['match',['get','class'],'river',1.6,.9],16,['match',['get','class'],'river',3,1.6],18,['match',['get','class'],'river',4,2.2]];
  if(layer.id==='buildings')layer.paint['fill-opacity']=['interpolate',['linear'],['zoom'],13,.55,16,.85];
  const texture=layer.id.includes('wetland')?'cover-wetland':layer.id==='landcover-sand'?'cover-sand':layer.id==='nlcd-scrub'?'cover-scrub':null;
  if(texture&&layer.type==='fill')style.layers.splice(style.layers.indexOf(layer)+1,0,{...layer,id:layer.id+'-texture',minzoom:12,paint:{'fill-pattern':texture,'fill-opacity':['interpolate',['linear'],['zoom'],12,0,14,.65,17,.8]}});
 }
 // Bridge decks are drawn above intersecting surface roads/trails. Retain each
 // original class's casing/fill pair, and don't alter its physical geometry.
 const bridges=[];
 for(const layer of style.layers){
  if(layer.type!=='line'||!['road','network','osm__road','trails__network'].includes(layer['source-layer'])||!layer.id.startsWith('roads-'))continue;
  const bridge=JSON.parse(JSON.stringify(layer));bridge.id+='-bridge';bridge.filter=['all',layer.filter,['==',['get','is_bridge'],true]];
  layer.filter=['all',layer.filter,['!=',['get','is_bridge'],true]];bridges.push(bridge);
 }
 const symbolStart=style.layers.findIndex((l:any)=>l.type==='symbol'&&l.source!=='contours');style.layers.splice(symbolStart<0?style.layers.length:symbolStart,0,...bridges);
 function attach(map:any){
  const add=()=>{for(const [id,texture] of Object.entries(textures)){
   const canvas=document.createElement('canvas');canvas.width=canvas.height=32;const c=canvas.getContext('2d')!;c.strokeStyle=c.fillStyle=texture.color;c.lineWidth=1;
   if(texture.kind==='wetland'){for(const [x,y]of [[8,9],[24,25]]){c.beginPath();c.moveTo(x-4,y);c.lineTo(x+4,y);c.moveTo(x,y);c.lineTo(x,y-4);c.stroke();}}
   else{for(const [x,y]of [[5,7],[23,13],[13,26]]){c.beginPath();c.arc(x,y,.8,0,Math.PI*2);c.fill();}}
   if(!map.hasImage(id))map.addImage(id,c.getImageData(0,0,32,32),{pixelRatio:1});
  }};map.on('style.load',add);map.on('styleimagemissing',(e:any)=>{if(textures[e.id])add()});if(map.isStyleLoaded())add();
 }

 return {stats,attach,dispose(){disposed=true;for(const p of requests.values()){p.signal.removeEventListener('abort',p.cancel);p.reject(Error('Map closed'))}for(const c of demRequests.values())c.abort();for(const e of cache.values())e.controller.abort();worker.terminate();requests.clear();demRequests.clear();cache.clear();gl.removeProtocol('topodem');gl.removeProtocol('topocontour')}};
}
