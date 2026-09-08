import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import ts from 'typescript';
const code=ts.transpileModule(fs.readFileSync(new URL('../src/gpsRecording.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {GPSRecording,TrackAccumulator}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const point=(i,extra={})=>({x:-120+i*.0001,y:39,z:100+i,time:100000+i*10000,accuracy:3,altitudeAccuracy:4,speed:1,heading:90,...extra});
function setup(){let text='',writes=0,fail=false;const recording=new GPSRecording({read:async()=>text,append:value=>{if(fail)throw Error('disk');text+=value;writes++},reset:()=>{if(fail)throw Error('disk');text=''}});return {recording,get text(){return text},get writes(){return writes},set text(v){text=v},set fail(v){fail=v}}}
test('50-point append batches, raw coordinates, replay equality and reset',async()=>{
 const t=setup(),r=t.recording;await r.recalculate();for(let i=0;i<49;i++)r.add(point(i));assert.equal(t.writes,0);assert.equal(r.buffer.length,49);r.add(point(49));assert.equal(t.writes,1);assert.equal(r.buffer.length,0);assert.equal(t.text.trim().split('\n').length,50);
 const raw=JSON.parse(t.text.split('\n')[0]);assert.equal(raw.x,-120);assert.equal(raw.z,100);assert.equal(raw.time,100000);assert.equal(raw.accuracy,3);
 assert.ok(r.stats.distance>400&&r.stats.distance<440);assert.equal(r.stats.movingTime,490);assert.equal(r.stats.elevationGain,45);
 for(let i=50;i<57;i++)r.add(point(i));const expected={...r.stats};await r.recalculate();assert.equal(t.writes,2);assert.deepEqual(r.stats,expected);
 r.reset();assert.equal(t.text,'');assert.equal(r.stats.points,0);assert.equal(r.buffer.length,0);await r.recalculate();assert.equal(r.stats.distance,0);
});
test('background and restart gaps never connect tracks',async()=>{
 const t=setup(),r=t.recording;await r.recalculate();r.add(point(0));r.add(point(1));const distance=r.stats.distance;r.breakSegment();assert.equal(t.writes,1);r.add(point(20));assert.equal(r.stats.distance,distance);r.flush();const restarted=new GPSRecording({read:async()=>t.text,append:()=>{},reset:()=>{}});await restarted.recalculate();restarted.add(point(21));assert.equal(restarted.stats.distance,distance);
});
test('stationary jitter, bad accuracy, missing altitude and GPS jumps do not inflate stats',()=>{
 const a=new TrackAccumulator();for(let i=0;i<20;i++)a.add({...point(i),x:-120+(i%2)*.000001,z:100+(i%2)*2,segment:0});assert.equal(a.stats.distance,0);assert.equal(a.stats.elevationGain,0);
 a.add({...point(20),accuracy:200,segment:0});a.add({...point(21),z:null,segment:0});a.add({...point(22),x:0,segment:0});assert.equal(a.stats.distance,0);assert.equal(a.stats.elevationGain,0);assert.equal(a.stats.points,23);
});
test('disk failure retains the buffer and unsuccessful reset preserves stats',async()=>{
 const t=setup(),r=t.recording;await r.recalculate();t.fail=true;for(let i=0;i<50;i++)r.add(point(i));assert.equal(r.buffer.length,50);assert.ok(r.error);r.reset();assert.equal(r.stats.points,50);t.fail=false;r.flush();assert.equal(r.buffer.length,0);assert.equal(t.text.trim().split('\n').length,50);
});
test('corrupt and repeated records are skipped and reset supersedes an in-flight rebuild',async()=>{
 const t=setup(),r=t.recording;const p={...point(0),segment:0};t.text=JSON.stringify(p)+'\n'+JSON.stringify(p)+'\n{broken\n';await r.recalculate();assert.equal(r.stats.points,1);assert.match(r.error,/unreadable/);
 let release;const slow=new GPSRecording({read:()=>new Promise(resolve=>release=resolve),append:()=>{},reset:()=>{}});const init=slow.recalculate();slow.add(point(1));slow.reset();release(JSON.stringify(p));await init;assert.equal(slow.stats.points,0);
});

test('points arriving during file replay retain foreground segment breaks and flush on background',async()=>{
 let release,text='';const r=new GPSRecording({read:()=>new Promise(resolve=>release=resolve),append:value=>text+=value,reset:()=>{text=''}});const task=r.recalculate();r.add(point(0));r.breakSegment();r.add(point(1));release('');await task;assert.equal(r.stats.points,2);assert.equal(r.stats.distance,0);assert.equal(r.buffer.length,0);const records=text.trim().split('\n').map(JSON.parse);assert.notEqual(records[0].segment,records[1].segment);
});

test('manual replay keeps the current foreground segment and ongoing statistics continuous',async()=>{
 const a=setup(),b=setup();await a.recording.recalculate();await b.recording.recalculate();for(let i=0;i<20;i++){a.recording.add(point(i));b.recording.add(point(i))}await a.recording.recalculate();for(let i=20;i<30;i++){a.recording.add(point(i));b.recording.add(point(i))}assert.deepEqual(a.recording.stats,b.recording.stats);
});

test('delayed fixes captured before reset cannot repopulate the current recording',async()=>{const t=setup(),r=t.recording;await r.recalculate();const old=point(0,{time:Date.now()-10000});r.add(old);r.reset();r.add(old);assert.equal(r.stats.points,0);r.add(point(1,{time:Date.now()+1000}));assert.equal(r.stats.points,1)});
