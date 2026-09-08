import {abortable} from './abortable.mjs';
import * as FS from 'expo-file-system/legacy';
import {cellTiles} from './tiles.mjs';
export type Tileset={datasetId:string;tileUrl:string;batchUrl?:string;batchSize?:number;format?:string;encoding?:string;tileSize?:number;halo?:number;attribution?:string;minZoom:number;maxZoom:number;bounds:[number,number,number,number]};
export type Metadata={publication?:{status:string};name:string;datasetId:string;bounds:[number,number,number,number];center:[number,number];initialZoom?:number;minZoom:number;maxZoom:number;gridZoom:number;tileUrl:string;batchUrl?:string;batchSize?:number;tilesets?:{osm:Tileset;dem?:Tileset;contours?:Tileset;amenities?:Tileset;boundaries?:Tileset;waterways?:Tileset;landcover?:Tileset;trails?:Tileset;recreation?:Tileset}};
export type Region={status:'queued'|'downloading'|'complete'|'error';done:number;total:number;bytes?:number;error?:string};
export type Regions=Record<string,Region>;
type Job={key:string;tileset:string;path:string;datasetId:string;owners:(()=>boolean)[];viewportOwners:(()=>boolean)[];promise:Promise<string>;resolve:(path:string)=>void;reject:(error:Error)=>void;started:boolean;interactive:boolean};
const base64=(bytes:Uint8Array)=>{const alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";const chunks:string[]=[];for(let start=0;start<bytes.length;start+=12288){let text="";for(let i=start;i<Math.min(start+12288,bytes.length);i+=3){const a=bytes[i],b=bytes[i+1],c=bytes[i+2];text+=alphabet[a>>2]+alphabet[((a&3)<<4)|((b||0)>>4)]+(i+1<bytes.length?alphabet[((b&15)<<2)|((c||0)>>6)]:"=")+(i+2<bytes.length?alphabet[c&63]:"=")}chunks.push(text)}return chunks.join("")};
class TileResponseError extends Error{constructor(public status:number){super('Tile server returned '+status)}}
const root=FS.documentDirectory+'topo-vectors-v2/';
export function resetDevelopmentMapCache(){const runtime=globalThis as typeof globalThis&{__topoMapCacheReset?:Promise<void>};return runtime.__topoMapCacheReset??=FS.deleteAsync(root,{idempotent:true})}
const validKey=(key:string)=>/^(?:(?:osm|dem|contours|amenities|boundaries|waterways|landcover|trails|recreation)\/)?\d+\/\d+\/\d+$/.test(key);
const composition=(meta:Metadata|null)=>meta?JSON.stringify(meta.tilesets?Object.entries(meta.tilesets).map(([name,set])=>[name,set?.datasetId]).sort():[['osm',meta.datasetId]]):'';
// Added sources and trail/recreation processing revisions retain saved regions and other binaries.
const isCompatibleUpgrade=(previous:Metadata|null,latest:Metadata)=>{
 if(!previous||previous.gridZoom!==latest.gridZoom)return false;
 const before=previous.tilesets||{osm:previous},after=latest.tilesets||{osm:latest};
 return Object.entries(before).every(([name,set])=>{
  const next=after[name as keyof typeof after];
  return (name==='contours'&&!!latest.tilesets?.dem)||!set||next?.datasetId===set.datasetId||(['recreation','trails','amenities','dem','boundaries'].includes(name)&&next&&next.minZoom<=set.minZoom&&next.maxZoom>=set.maxZoom&&next.bounds[0]<=set.bounds[0]&&next.bounds[1]<=set.bounds[1]&&next.bounds[2]>=set.bounds[2]&&next.bounds[3]>=set.bounds[3]);
 });
};
export class TileStore{
 private get cacheRoot(){return root+encodeURIComponent(this.api.replace(/\/$/,''))+'/'}
 private get statePath(){return this.cacheRoot+'state.json'}
 regions:Regions={};meta:Metadata|null=null;running=false;
 private nativePending:Record<string,{datasetId:string;keys:string[]}>={};private activeRegions=0;
 private writes=Promise.resolve();private requests=new Map<string,Job>();private workers=0;private interactiveWorkers=0;private lanes=new Map<string,number>();private scheduled=false;private progressTimer:ReturnType<typeof setTimeout>|null=null;
 private foreground=true;
 private flights=new Set<{jobs:Job[];controller:AbortController;interactive:boolean;yielded:boolean}>();
 setForeground(value:boolean){this.foreground=value;if(value){this.yieldOffline();this.kick()}else this.dispatch()}
 private yieldOffline(){for(const flight of this.flights)if(!flight.interactive&&!flight.yielded){flight.yielded=true;flight.controller.abort()}}
 private core(job:Job){return ['osm','dem','contours'].includes(job.tileset)}
 constructor(public api:string,public changed:()=>void,private options:{retryDelayMs?:number;progressMs?:number;requestTimeoutMs?:number;headers?:()=>Record<string,string>}={}){}
 private headers(url:string){return url.startsWith(this.api+'/')?(this.options.headers?.()||{}):{}}
 private notify(){if(this.progressTimer)return;this.progressTimer=setTimeout(()=>{this.progressTimer=null;this.changed()},this.options.progressMs??150)}
 private parse(key:string){const parts=key.split('/');return parts.length===4?{tileset:parts[0],key:parts.slice(1).join('/')}:{tileset:'osm',key}}
 private set(name:string):Tileset|undefined{return this.meta?.tilesets?.[name as 'osm'|'dem'|'contours'|'amenities'|'boundaries'|'waterways'|'landcover'|'trails'|'recreation']||(name==='osm'?this.meta||undefined:undefined)}
 file(key:string){const parsed=this.parse(key);const dataset=encodeURIComponent(this.set(parsed.tileset)?.datasetId||'unknown');return this.cacheRoot+(parsed.tileset==='osm'?'':parsed.tileset+'_')+dataset+'_'+parsed.key.replaceAll('/','_')+(parsed.tileset==='dem'?'.png':'.pbf')}
 regionTiles(id:string){if(!this.meta)return [];const sets=this.meta.tilesets||{osm:this.meta};return Object.entries(sets).flatMap(([name,set])=>set?cellTiles(id,{...set,gridZoom:this.meta!.gridZoom}).map(key=>name+'/'+key):[])}
 async init(){await FS.makeDirectoryAsync(this.cacheRoot,{intermediates:true});try{const data=JSON.parse(await FS.readAsStringAsync(this.statePath));if(data.api===this.api){this.meta=data.meta;this.regions=data.regions||{};this.nativePending=data.nativePending||{};for(const r of Object.values(this.regions))if(r.status==='downloading')r.status='queued';}}catch{};try{const response=await fetch(this.api+'/metadata',{headers:this.headers(this.api+'/metadata'),signal:AbortSignal.timeout(8000)});if(!response.ok)throw Error('Metadata '+response.status);const latest:Metadata=await response.json();if(!latest.datasetId)throw Error('Vector metadata needs datasetId');if(composition(latest)!==composition(this.meta)){
 const compatible=isCompatibleUpgrade(this.meta,latest);this.meta=latest;
 if(compatible){for(const [id,region] of Object.entries(this.regions)){region.status='queued';region.done=0;region.total=this.regionTiles(id).length;delete region.error;delete region.bytes}}
 else this.regions={};
 }else this.meta=latest;await this.save()}catch(e){if(!this.meta)throw e}await this.recoverNative();await this.restoreSizes();this.changed();this.kick();this.pump();}
 private async tileSize(path:string){const info=await FS.getInfoAsync(path);return info.exists?info.size:0}
 private async restoreSizes(){for(const [id,region] of Object.entries(this.regions)){if(region.bytes!==undefined)continue;const sizes=await Promise.all(this.regionTiles(id).map(key=>this.tileSize(this.file(key)).catch(()=>0)));region.bytes=sizes.reduce((sum,size)=>sum+size,0)}await this.save()}
 save(){const text=JSON.stringify({api:this.api,meta:this.meta,regions:this.regions,nativePending:this.nativePending});this.writes=this.writes.catch(()=>{}).then(async()=>{await FS.writeAsStringAsync(this.statePath+'.tmp',text);await FS.moveAsync({from:this.statePath+'.tmp',to:this.statePath})});return this.writes;}
 private alive(job:Job){return this.set(job.tileset)?.datasetId===job.datasetId&&job.owners.some(owner=>owner())}
 private finish(job:Job,error?:Error){if(this.requests.get(job.path)!==job)return;this.requests.delete(job.path);if(error)job.reject(error);else job.resolve(job.path)}
 async ensure(key:string,owner:()=>boolean=()=>true,interactive=false){if(!validKey(key)||!this.meta)throw Error('Invalid tile request');const parsed=this.parse(key),set=this.set(parsed.tileset);if(!set)throw Error('Unknown tileset');const path=this.file(key),datasetId=set.datasetId;if((await FS.getInfoAsync(path)).exists)return path;if(!owner())throw Error('Cancelled');const previous=this.requests.get(path);if(previous){previous.owners.push(owner);if(interactive){previous.viewportOwners.push(owner);previous.interactive=true;if(this.foreground)this.yieldOffline();this.kick()}return previous.promise}let resolve!:(path:string)=>void,reject!:(error:Error)=>void;const promise=new Promise<string>((yes,no)=>{resolve=yes;reject=no});const job:Job={key:parsed.key,tileset:parsed.tileset,path,datasetId,owners:[owner],viewportOwners:interactive?[owner]:[],promise,resolve,reject,started:false,interactive};this.requests.set(path,job);if(interactive&&this.foreground)this.yieldOffline();this.kick();return promise;}
 private kick(){if(this.scheduled)return;this.scheduled=true;setTimeout(()=>{this.scheduled=false;this.dispatch()},10)}
 private dispatch(){for(const job of this.requests.values())job.interactive=job.viewportOwners.some(owner=>owner());for(const job of this.requests.values())if(!job.started&&!this.alive(job))this.finish(job,Error('Cancelled'));
 // Terrain has reserved slots: cold overlay generation cannot block basemap or contours.
 for(const lane of ['terrain','dem','amenities','boundaries','waterways','landcover','trails','recreation','offline']){const interactive=lane!=='offline';
 const visible=[...this.requests.values()].filter(j=>j.interactive&&this.alive(j));
 const corePending=visible.some(j=>this.core(j));
 if(this.foreground&&(!interactive&&visible.length||interactive&&!['terrain','dem'].includes(lane)&&corePending))continue;
 const limit=!interactive&&!this.foreground&&this.meta?.batchUrl&&typeof FS.createDownloadResumable==='function'?Infinity:lane==='terrain'||lane==='dem'||!interactive?2:1;
 while((this.lanes.get(lane)||0)<limit){if(interactive&&!['terrain','dem'].includes(lane)&&[...this.flights].filter(f=>f.interactive&&!this.core(f.jobs[0])).length>=2)break;const available=[...this.requests.values()].filter(j=>!j.started&&j.interactive===interactive&&this.alive(j)&&(!interactive||(j.tileset==='osm'||j.tileset==='contours'?'terrain':j.tileset)===lane));const first=available[0];if(!first)break;const set=this.set(first.tileset);const count=!interactive&&set?.batchUrl?Math.max(1,Math.min(8,set.batchSize||8)):1;const jobs=available.filter(j=>j.tileset===first.tileset&&j.datasetId===first.datasetId).slice(0,count);for(const j of jobs)j.started=true;this.lanes.set(lane,(this.lanes.get(lane)||0)+1);if(interactive)this.interactiveWorkers++;else this.workers++;this.run(jobs,interactive).catch(()=>{}).finally(()=>{this.lanes.set(lane,(this.lanes.get(lane)||1)-1);if(interactive)this.interactiveWorkers--;else this.workers--;this.kick()})}}
 }
 cancelUnused(){for(const flight of this.flights)if(flight.interactive&&flight.jobs.every(job=>!job.viewportOwners.some(owner=>owner()))&&flight.jobs.some(job=>this.alive(job))){flight.yielded=true;flight.controller.abort()}for(const job of this.requests.values())if(!job.started&&!this.alive(job))this.finish(job,Error('Cancelled'));for(const flight of this.flights)if(flight.jobs.every(job=>!this.alive(job)))flight.controller.abort();this.kick()}
 // Only hand the entire queue to native sessions when the app leaves the foreground.
 // The OS schedules network concurrency while JS is suspended. Never use a JS timeout here.
 private async nativeBatch(url:string,jobs:Job[],signal:AbortSignal){
  const path=this.cacheRoot+'batch-'+Date.now()+'-'+Math.random().toString(36).slice(2)+'.json';
  this.nativePending[path]={datasetId:jobs[0].datasetId,keys:jobs.map(j=>j.tileset+'/'+j.key)};
  await this.save();
  const task=FS.createDownloadResumable(url,path,{sessionType:FS.FileSystemSessionType.BACKGROUND,headers:this.headers(url)});
  const cancel=()=>{void task.cancelAsync().catch(()=>{})};
  signal.addEventListener('abort',cancel,{once:true});
  try{
   if(signal.aborted)throw Error('Cancelled');
   const result=await task.downloadAsync();
   if(!result||signal.aborted)throw Error('Cancelled');
   if(result.status!==200)throw Error('Tile batch returned '+result.status);
   return JSON.parse(await FS.readAsStringAsync(path));
  }finally{
   signal.removeEventListener('abort',cancel);
   delete this.nativePending[path];
   await FS.deleteAsync(path,{idempotent:true}).catch(()=>{});
  }
 }
 private async recoverNative(){
  // A transfer may have finished while the previous JS runtime was gone. Only install
  // requested keys for the current dataset and still-selected cells; never trust the envelope.
  const wanted=new Set(Object.keys(this.regions).flatMap(id=>this.regionTiles(id)));
  for(const [path,entry] of Object.entries(this.nativePending)){
   if(!path.startsWith(this.cacheRoot+'batch-')||!path.endsWith('.json'))continue;
   try{
    const data=JSON.parse(await FS.readAsStringAsync(path));
    if(data.datasetId===entry.datasetId){
     const allowed=new Set(entry.keys);
     for(const tile of data.tiles||[]){
      const key=entry.keys[0]?.split('/')[0]+'/'+tile.key;
      if(!allowed.has(key)||!wanted.has(key)||!validKey(key)||this.set(this.parse(key).tileset)?.datasetId!==entry.datasetId||typeof tile.data!=='string')continue;
      const target=this.file(key);await FS.writeAsStringAsync(target+'.part',tile.data,{encoding:FS.EncodingType.Base64});
      await FS.moveAsync({from:target+'.part',to:target});
     }
    }
   }catch{}finally{await FS.deleteAsync(path,{idempotent:true}).catch(()=>{})}
  }
  this.nativePending={};await this.save();
 }
 private async run(jobs:Job[],interactive=false){let remaining=jobs;const set=this.set(jobs[0].tileset);const controller=new AbortController(),flight={jobs,controller,interactive,yielded:false};this.flights.add(flight);const timeout=!interactive&&typeof FS.createDownloadResumable==='function'?undefined:setTimeout(()=>controller.abort(),this.options.requestTimeoutMs??(interactive&&this.meta?.publication?20000:150000));try{for(let attempt=0;remaining.length&&attempt<3;attempt++){for(const job of remaining)if(!this.alive(job))this.finish(job,Error('Cancelled'));remaining=remaining.filter(j=>this.alive(j));if(!remaining.length)break;try{if(!interactive&&set?.batchUrl){const endpoint=set.batchUrl.startsWith('http')?set.batchUrl:this.api+set.batchUrl;const url=endpoint+(endpoint.includes('?')?'&':'?')+'datasetId='+encodeURIComponent(remaining[0].datasetId)+'&tiles='+remaining.map(j=>j.key).join(',');const data=typeof FS.createDownloadResumable==='function'?await this.nativeBatch(url,remaining,controller.signal):await (async()=>{const response=await abortable(fetch(url,{headers:this.headers(url),signal:controller.signal}),controller.signal);if(!response.ok)throw Error('Tile batch returned '+response.status);return abortable(response.json(),controller.signal)})();if(data.datasetId!==remaining[0].datasetId||data.datasetId!==this.set(remaining[0].tileset)?.datasetId)throw Error('Dataset changed during download');const tiles=new Map<string,string>((data.tiles||[]).map((t:{key:string;data:string})=>[t.key,t.data]));for(const job of remaining){if(!this.alive(job)){this.finish(job,Error('Cancelled'));continue}const binary=tiles.get(job.key);if(typeof binary!=='string')continue;await FS.writeAsStringAsync(job.path+'.part',binary,{encoding:FS.EncodingType.Base64});await FS.moveAsync({from:job.path+'.part',to:job.path});this.finish(job)}}else{const job=remaining[0];const result=await abortable(fetch(this.tileUrl(job.tileset+'/'+job.key),{headers:this.headers(this.tileUrl(job.tileset+'/'+job.key)),signal:controller.signal}),controller.signal);if(!result.ok)throw new TileResponseError(result.status);const binary=base64(new Uint8Array(await abortable(result.arrayBuffer(),controller.signal)));if(controller.signal.aborted||!this.alive(job))throw Error('Cancelled');await FS.writeAsStringAsync(job.path+'.part',binary,{encoding:FS.EncodingType.Base64});if(this.set(job.tileset)?.datasetId!==job.datasetId)throw Error('Dataset changed during download');await FS.moveAsync({from:job.path+'.part',to:job.path});this.finish(job)}
 remaining=remaining.filter(j=>this.requests.has(j.path));if(remaining.length&&attempt===2)throw Error('Some tiles could not be downloaded');
 }catch(e){if(flight.yielded)break;if(attempt===2||controller.signal.aborted||e instanceof TileResponseError&&[400,401,403,404,409,429].includes(e.status)){for(const job of remaining)this.finish(job,e instanceof Error?e:Error(String(e)));remaining=[]}}remaining=remaining.filter(j=>this.requests.has(j.path));if(remaining.length)await new Promise(r=>setTimeout(r,(this.options.retryDelayMs??500)*2**attempt))}
 }finally{clearTimeout(timeout);this.flights.delete(flight);for(const job of jobs){if(this.requests.has(job.path)&&!flight.yielded)this.finish(job,Error('Download interrupted'));await FS.deleteAsync(job.path+'.part',{idempotent:true}).catch(()=>{});if(flight.yielded&&this.requests.has(job.path))job.started=false}await this.save().catch(()=>{});this.notify()}}
 async source(key:string,owner:()=>boolean=()=>true){const path=await this.ensure(key,owner,true);return FS.readAsStringAsync(path,{encoding:FS.EncodingType.Base64})}
 tileUrl(key:string){const parsed=this.parse(key);const[z,x,y]=parsed.key.split('/');const path=(this.set(parsed.tileset)?.tileUrl||'/tiles/{z}/{x}/{y}.pbf').replace('{z}',z).replace('{x}',x).replace('{y}',y);return /^https?:/.test(path)?path:this.api+path;}
 async toggle(id:string){if(!this.meta)return;const current=this.regions[id];if(current?.status==='error'){current.status='queued';delete current.error}else if(current){delete this.regions[id]}else{const tiles=this.regionTiles(id);if(!tiles.length)return;this.regions[id]={status:'queued',done:0,total:tiles.length,bytes:0}}for(const flight of this.flights)if(flight.jobs.every(j=>!this.alive(j)))flight.controller.abort();this.changed();this.kick();await this.save();this.pump();}
 async pump(){if(!this.meta)return;
 const queued=Object.entries(this.regions).filter(([,r])=>r.status==='queued');
 await Promise.all(queued.map(async([id,region])=>{
  this.activeRegions++;this.running=true;region.status='downloading';region.done=0;region.bytes=0;this.changed();
  const owner=()=>this.regions[id]===region;
  try{await this.save();
   const results=await Promise.allSettled(this.regionTiles(id).map(async key=>{const path=await this.ensure(key,owner);const bytes=await this.tileSize(path);if(owner()){region.done++;region.bytes=(region.bytes||0)+bytes;this.notify()}}));
   if(owner()){const failed=results.find(r=>r.status==='rejected');if(failed?.status==='rejected'){region.status='error';region.error=String(failed.reason)}else region.status='complete'}
   await this.save();this.changed();
  }finally{this.activeRegions--;this.running=this.activeRegions>0}
 }));
 }
 async clear(){if(this.running||this.requests.size||this.workers||this.interactiveWorkers)throw Error('Wait for map loading and remove queued cells before clearing storage.');this.regions={};await FS.deleteAsync(this.cacheRoot,{idempotent:true});await FS.makeDirectoryAsync(this.cacheRoot,{intermediates:true});await this.save();this.changed()}
}
