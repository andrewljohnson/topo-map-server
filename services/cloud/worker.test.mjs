import {test} from 'node:test';import assert from 'node:assert/strict';import worker,{Usage} from './worker.mjs';
const token='unit-test-only',hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token))),b=>b.toString(16).padStart(2,'0')).join('');
function setup(){
 const values=new Map();let serial=Promise.resolve();const storage={get:async k=>structuredClone(values.get(k)),put:async(k,v)=>values.set(k,structuredClone(v)),transaction(fn){const p=serial.then(()=>fn(this));serial=p.catch(()=>{});return p}};
 const env={ACCESS_SHA256:hash,DOWNLOAD_BYTES:'1000000',REQUEST_LIMIT:'1000',ASSETS:{fetch:()=>new Response('website')}};
 const quota=new Usage({storage},env);env.USAGE={idFromName:()=>'',get:()=>({fetch:(url,init)=>quota.fetch(new Request(url,init))})};let reads=0;
 const meta={tilesets:{osm:{datasetId:'test',minZoom:0,maxZoom:14},dem:{datasetId:'dem',minZoom:3,maxZoom:13}}};
 const objects=new Map([['publication/metadata.json',JSON.stringify(meta)],['tiles/v1/test/0/0/0.pbf','vector-test']]);
 env.TILES={get:async key=>{reads++;const text=objects.get(key);return text===undefined?null:{body:text,size:text.length,httpMetadata:{contentType:'application/octet-stream'},httpEtag:'test'}}};
 const run=(path,auth=token)=>worker.fetch(new Request('https://map.test'+path,{headers:auth?{Authorization:'Bearer '+auth}:{}}),env,{waitUntil(){}});
 return {env,run,quota,objects,reads:()=>reads};
}
test('unauthorized requests never read R2; static site remains public',async()=>{const s=setup();assert.equal((await s.run('/metadata','wrong')).status,401);assert.equal(s.reads(),0);assert.equal(await (await s.run('/',null)).text(),'website')});
test('normal and batched delivery preserve bytes and enforce manifest',async()=>{const s=setup();const r=await s.run('/tiles/0/0/0.pbf?datasetId=test');assert.equal(await r.text(),'vector-test');assert.equal(r.headers.get('Cache-Control'),'private, no-store');const b=await(await s.run('/tile-batch?tiles=0/0/0')).json();assert.equal(atob(b.tiles[0].data),'vector-test');assert.equal((await s.run('/tiles/0/0/0.pbf?datasetId=stale')).status,409);assert.equal((await s.run('/tiles/0/9/0.pbf')).status,400)});
test('byte and request limits persist across requests and auth revocation is immediate',async()=>{const s=setup();s.env.DOWNLOAD_BYTES='5';assert.equal((await s.run('/metadata')).status,429);s.env.ACCESS_SHA256='revoked';assert.equal((await s.run('/tiles/0/0/0.pbf')).status,401)});
test('concurrent reservations cannot exceed quota',async()=>{const s=setup();s.env.DOWNLOAD_BYTES='10';const r=await Promise.all(Array.from({length:30},()=>s.quota.fetch(new Request('https://quota/',{method:'POST',body:JSON.stringify({bytes:1})}))));assert.equal(r.filter(x=>x.ok).length,10)});
test('bounded batches and missing details are explicit',async()=>{const s=setup();assert.equal((await s.run('/tile-batch?tiles='+Array(9).fill('0/0/0').join(','))).status,400);assert.equal((await s.run('/tiles/2/0/0.pbf')).status,404)});

test('missing requests deduplicate and operator queue cannot be read with a client key',async()=>{const s=setup();await s.run('/tiles/2/0/0.pbf');await s.run('/tiles/2/0/0.pbf');const pending=await(await s.quota.fetch(new Request('https://quota/',{method:'POST',body:JSON.stringify({pending:true})}))).json();assert.equal(pending.jobs.length,1);assert.equal((await s.run('/operator/jobs')).status,401)});

test('public map allows anonymous metadata and tiles but keeps quotas and operator auth',async()=>{const s=setup();s.env.PUBLIC_MAP='1';assert.equal((await(await s.run('/metadata',null)).json()).publicAccess,true);assert.equal(await(await s.run('/tiles/0/0/0.pbf',null)).text(),'vector-test');assert.equal((await s.run('/operator/jobs',null)).status,401);s.env.REQUEST_LIMIT='2';assert.equal((await s.run('/metadata',null)).status,429)});

import {gzipSync} from 'node:zlib';
test('pinned combined release keeps gzip HTTP bytes, decodes batches and respects exact coverage',async()=>{
 const s=setup();s.env.DOWNLOAD_BYTES='100000000';
 const meta={combined:true,tilesets:{osm:{datasetId:'pilot-base',minZoom:0,maxZoom:12,coverage:{'12':[[681,1566,681,1566]]}}}};
 const compressed=gzipSync(Buffer.from('combined-test'));
 s.env.TILES.get=async key=>{
  if(key==='publication/releases/pilot/metadata.json'){const text=JSON.stringify(meta);return {body:text,size:text.length,httpMetadata:{contentType:'application/json'}}}
  if(key==='tiles/v1/pilot-base/12/681/1566.pbf')return {body:compressed,size:compressed.length,httpMetadata:{contentType:'application/vnd.mapbox-vector-tile',contentEncoding:'gzip'}};
  return null;
 };
 assert.equal((await(await s.run('/releases/pilot/metadata')).json()).combined,true);
 const tile=await s.run('/releases/pilot/tiles/12/681/1566.pbf');assert.equal(tile.headers.get('Content-Encoding'),'gzip');assert.deepEqual(Buffer.from(await tile.arrayBuffer()),compressed);
 const batch=await(await s.run('/releases/pilot/tile-batch?tiles=12/681/1566,12/682/1566')).json();assert.equal(atob(batch.tiles[0].data),'combined-test');assert.equal(batch.tiles[1].data,'');assert.deepEqual(batch.errors,[]);
 assert.equal((await s.run('/releases/pilot/tiles/12/681/1566.pbf?datasetId=stale')).status,409);
 const pending=await(await s.quota.fetch(new Request('https://quota/',{method:'POST',body:JSON.stringify({pending:true})}))).json();assert.equal(pending.jobs.length,0);
});
