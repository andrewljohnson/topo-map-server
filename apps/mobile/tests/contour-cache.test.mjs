import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {createRequire} from 'node:module';
import {getEventListeners} from 'node:events';
// Exercise the pinned dependency patch used by the generated browser worker.
const req=createRequire(import.meta.url);
const filename=process.env.CONTOUR_CACHE_MODULE||path.join(path.dirname(req.resolve('maplibre-contour')),'index.mjs');
const source=fs.readFileSync(filename,'utf8');
const start=source.indexOf('let num = 0;'),end=source.indexOf('\nlet offscreenCanvas;',start);
const Cache=vm.runInNewContext(`function onAbort(c,f){c?.signal.addEventListener('abort',f)};${source.slice(start,end)};AsyncCache`,{AbortController,Promise,Error,Map});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}};
test('successful and rejected cache requests release their abort listeners',async()=>{
 const cache=new Cache(2),parent=new AbortController();
 for(let i=0;i<40;i++)await cache.get('good-'+i,()=>Promise.resolve(i),parent);
 assert.equal(getEventListeners(parent.signal,'abort').length,0);
 await assert.rejects(cache.get('bad',()=>Promise.reject(Error('failed')),parent),/failed/);
 assert.equal(getEventListeners(parent.signal,'abort').length,0);assert.equal(cache.items.has('bad'),false);
});
test('only the last pending consumer cancels a shared supplier',async()=>{
 const cache=new Cache(2),a=new AbortController(),b=new AbortController(),d=deferred();let shared,calls=0;
 const supplier=(key,controller)=>{calls++;shared=controller;controller.signal.addEventListener('abort',()=>d.reject(Error('cancelled')));return d.promise};
 const pa=cache.get('same',supplier,a),pb=cache.get('same',supplier,b);const results=Promise.allSettled([pa,pb]);
 a.abort();assert.equal(shared.signal.aborted,false);assert.equal(calls,1);b.abort();assert.equal(shared.signal.aborted,true);
 assert.equal((await results).every(r=>r.status==='rejected'),true);assert.equal(cache.size(),0);
 assert.equal(getEventListeners(a.signal,'abort').length,0);assert.equal(getEventListeners(b.signal,'abort').length,0);
});
test('an evicted request cannot delete a newer entry when it fails late',async()=>{
 const cache=new Cache(1),old=deferred();const stale=cache.get('same',()=>old.promise,new AbortController());const rejected=assert.rejects(stale,/old failure/);
 await cache.get('other',()=>Promise.resolve('other'),new AbortController());
 await cache.get('same',()=>Promise.resolve('new'),new AbortController());
 old.reject(Error('old failure'));await rejected;
 assert.equal(await cache.get('same',()=>assert.fail('new value evicted'),new AbortController()),'new');
});
test('an evicted request cannot delete a newer entry when it is cancelled',async()=>{
 const cache=new Cache(1),parent=new AbortController(),old=deferred();
 const stale=cache.get('same',()=>old.promise,parent);
 await cache.get('other',()=>Promise.resolve('other'),new AbortController());
 await cache.get('same',()=>Promise.resolve('new'),new AbortController());parent.abort();old.resolve('old');await stale;
 assert.equal(await cache.get('same',()=>assert.fail('new value evicted'),new AbortController()),'new');
});
test('already cancelled consumers do not start or join a request',async()=>{
 const cache=new Cache(1),parent=new AbortController();parent.abort();
 await assert.rejects(cache.get('same',()=>assert.fail('unneeded fetch'),parent),/aborted/);assert.equal(cache.size(),0);
});
