const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
const routes={'tiles':'osm','dem':'dem','amenities':'amenities','boundaries':'boundaries','waterways':'waterways','landcover':'landcover','trails':'trails','recreation':'recreation'};
const batches={'tile-batch':'osm','dem-batch':'dem','amenity-batch':'amenities','boundary-batch':'boundaries','waterway-batch':'waterways','landcover-batch':'landcover','trails-batch':'trails','recreation-batch':'recreation'};
const digest=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
const same=(a,b)=>{if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0};
export class Usage {
 constructor(state,env){this.state=state;this.env=env}
 async fetch(request){
  const input=await request.json();
  return this.state.storage.transaction(async tx=>{
   if(input.pending)return json({jobs:await tx.get('pending')||[]});
   if(input.enqueue||input.ack){
    let jobs=await tx.get('pending')||[];
    if(input.ack)jobs=jobs.filter(j=>!input.ack.includes(j.id));
    if(input.enqueue&&!jobs.some(j=>j.id===input.enqueue.id)&&jobs.length<256)jobs.push(input.enqueue);
    await tx.put('pending',jobs);return json({ok:true});
   }
   const now=new Date(),month=now.toISOString().slice(0,7),minute=Math.floor(now.getTime()/60000);
   let v=await tx.get('usage')||{};
   if(v.month!==month)v={month,requests:0,bytes:0,minute,rate:0};
   if(v.minute!==minute){v.minute=minute;v.rate=0}
   if(input.status)return json({...v,limits:{bytes:Number(this.env.DOWNLOAD_BYTES),requests:Number(this.env.REQUEST_LIMIT)}});
   const requests=input.requests||0,bytes=input.bytes||0;
   if(!Number.isSafeInteger(requests)||!Number.isSafeInteger(bytes)||requests<0||bytes<0)return json({error:'Invalid reservation'},400);
   if(this.env.ACCESS_DISABLED==='1'||v.requests+requests>Number(this.env.REQUEST_LIMIT)||v.bytes+bytes>Number(this.env.DOWNLOAD_BYTES)||v.rate+requests>1200)return json({error:'Map allowance reached. Downloads are paused.'},429);
   v.requests+=requests;v.bytes+=bytes;v.rate+=requests;await tx.put('usage',v);return json({ok:true});
  });
 }
}
async function meter(env,values){return env.USAGE.get(env.USAGE.idFromName('owner')).fetch('https://quota/',{method:'POST',body:JSON.stringify(values)})}
async function object(env,key,ctx,ttl=86400){
 const url='https://tile-cache.invalid/'+key,cache=globalThis.caches?.default;
 const cached=cache?await cache.match(url):null;
 if(cached)return cached.status===404?null:cached;
 const item=await env.TILES.get(key);
 if(!item){if(cache)ctx.waitUntil(cache.put(url,new Response(null,{status:404,headers:{'Cache-Control':'public,max-age=30'}})));return null}
 const response=new Response(item.body,{headers:{'Content-Type':item.httpMetadata?.contentType||'application/octet-stream','Content-Length':String(item.size),'Cache-Control':'public,max-age='+ttl,'ETag':item.httpEtag}});
 if(cache)ctx.waitUntil(cache.put(url,response.clone()));return response;
}
function valid(spec,z,x,y){return spec&&Number.isInteger(z)&&z>=spec.minZoom&&z<=spec.maxZoom&&Number.isInteger(x)&&Number.isInteger(y)&&x>=0&&y>=0&&x<2**z&&y<2**z}
export async function api(request,env,ctx){
 const url=new URL(request.url),path=url.pathname.slice(1);
 if(path==='operator/jobs'){
  const auth=request.headers.get('Authorization')||'';
  if(auth.length>512||!auth.startsWith('Bearer ')||!same(await digest(auth.slice(7)),env.PUBLISH_SHA256))return json({error:'Operator key required'},401);
  if(request.method==='GET')return meter(env,{pending:true});
  if(request.method==='POST'){
   if(Number(request.headers.get('Content-Length')||0)>16384)return json({error:'Too large'},413);
   const body=await request.text();if(body.length>16384)return json({error:'Too large'},413);
   const value=JSON.parse(body);if(!Array.isArray(value.ack)||value.ack.length>256)return json({error:'Invalid acknowledgment'},400);
   return meter(env,{ack:value.ack});
  }
  return json({error:'Method not allowed'},405);
 }
 if(request.method==='OPTIONS')return new Response(null,{status:204});
 if(!['GET','HEAD'].includes(request.method))return json({error:'Method not allowed'},405);
 const auth=request.headers.get('Authorization')||'';
 if(auth.length>512||!auth.startsWith('Bearer ')||!env.ACCESS_SHA256||!same(await digest(auth.slice(7)),env.ACCESS_SHA256))return json({error:'Map access key required'},401);
 let allowed=await meter(env,{requests:1,bytes:1});if(!allowed.ok)return allowed;
 if(path==='usage')return meter(env,{status:true});
 const manifest=await object(env,'publication/metadata.json',ctx,30);
 if(!manifest)return json({error:'Map publication is preparing'},503);
 const info=await manifest.json();
 let result;
 if(path==='metadata')result=json(info);
 else if(path==='publication'){
  result=await object(env,'publication/status.json',ctx,30)||json({status:'preparing'});
 }else{
  const batch=batches[path];let source,z,x,y,keys;
  if(batch){source=batch;keys=(url.searchParams.get('tiles')||'').split(',');if(keys.length<1||keys.length>8||keys.some(k=>!/^\d+\/\d+\/\d+$/.test(k)))return json({error:'Use 1–8 valid tile keys'},400)}
  else{const match=path.match(/^(tiles|dem|amenities|boundaries|waterways|landcover|trails|recreation)\/(\d+)\/(\d+)\/(\d+)\.(pbf|png)$/);if(!match)return json({error:'Not found'},404);source=routes[match[1]];keys=[match.slice(2,5).join('/')];if(match[5]!== (source==='dem'?'png':'pbf'))return json({error:'Wrong tile format'},400)}
  const spec=info.tilesets[source];
  if(!spec)return json({error:'Unknown tileset'},404);
  if(url.searchParams.has('datasetId')&&url.searchParams.get('datasetId')!==spec.datasetId)return json({error:'Dataset changed; refresh metadata'},409);
  for(const key of keys){[z,x,y]=key.split('/').map(Number);if(!valid(spec,z,x,y))return json({error:'Outside tileset coverage'},400)}
  const tiles=[],errors=[];
  // Bound object reads and response memory even for hostile authenticated batches.
  for(const key of keys){
   const response=await object(env,'tiles/v1/'+spec.datasetId+'/'+key+(source==='dem'?'.png':'.pbf'),ctx);
   if(!response){
    await meter(env,{enqueue:{id:spec.datasetId+'/'+key+'/'+source,source,key,datasetId:spec.datasetId}});
    errors.push({key,error:'Detail is not published yet'});continue
   }
   if(Number(response.headers.get('Content-Length'))>4000000)return json({error:'Tile exceeds delivery limit'},413);
   if(!batch){result=response;break}
   const bytes=new Uint8Array(await response.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
   tiles.push({key,data:btoa(binary)});
  }
  if(batch)result=json({datasetId:spec.datasetId,tiles,errors});
  else if(!result)result=json({error:'Detail is not published yet; overview remains available'},404);
 }
 const body=await result.arrayBuffer();allowed=await meter(env,{bytes:body.byteLength+1024});if(!allowed.ok)return allowed;
 return new Response(request.method==='HEAD'?null:body,{status:result.status,headers:result.headers});
}
export default {async fetch(request,env,ctx){
 const path=new URL(request.url).pathname;
 if(!/^\/(operator|metadata|usage|publication|tiles|dem|amenities|boundaries|waterways|landcover|trails|recreation|tile-batch|dem-batch|amenity-batch|boundary-batch|waterway-batch|landcover-batch|trails-batch|recreation-batch)(\/|$)/.test(path))return env.ASSETS.fetch(request);
 let response;try{response=await api(request,env,ctx)}catch{response=json({error:'Map delivery temporarily unavailable'},503)}
 response=new Response(response.body,response);response.headers.set('Cache-Control','private, no-store');response.headers.set('Access-Control-Allow-Origin','*');response.headers.set('Access-Control-Allow-Headers','Authorization, Content-Type');response.headers.set('Access-Control-Allow-Methods','GET, HEAD, OPTIONS');response.headers.set('X-Content-Type-Options','nosniff');if(response.status===429)response.headers.set('Retry-After','60');return response;
}};
