export type GPSPoint={x:number;y:number;z:number|null;time:number;accuracy:number|null;altitudeAccuracy:number|null;speed:number|null;heading:number|null;mocked?:boolean;segment:number};
export type TrackStats={distance:number;movingTime:number;elevationGain:number;points:number};
export const emptyStats=():TrackStats=>({distance:0,movingTime:0,elevationGain:0,points:0});
export function validPoint(p:any):p is GPSPoint{return p&&Number.isFinite(p.x)&&Math.abs(p.x)<=180&&Number.isFinite(p.y)&&Math.abs(p.y)<=90&&(p.z===null||Number.isFinite(p.z))&&Number.isFinite(p.time)&&p.time>0&&Number.isInteger(p.segment)}
export function distance(a:GPSPoint,b:GPSPoint){const rad=Math.PI/180,dy=(b.y-a.y)*rad,dx=(b.x-a.x)*rad,h=Math.sin(dy/2)**2+Math.cos(a.y*rad)*Math.cos(b.y*rad)*Math.sin(dx/2)**2;return 6371008.8*2*Math.asin(Math.sqrt(Math.min(1,h)))}
export class TrackAccumulator{
 stats=emptyStats();last:GPSPoint|null=null;anchor:GPSPoint|null=null;elevation:number|null=null;
 add(p:GPSPoint){
  if(!validPoint(p)||this.last&&p.time<=this.last.time)return false;
  const prior=this.last;this.last=p;this.stats.points++;
  if(!prior||prior.segment!==p.segment||p.time-prior.time>30000){this.anchor=null;this.elevation=null}
  if(p.accuracy===null||p.accuracy>50||p.accuracy<0){this.anchor=null;this.elevation=null;return true}
  const altitude=p.z!==null&&p.altitudeAccuracy!==null&&p.altitudeAccuracy>=0&&p.altitudeAccuracy<=15;
  if(!this.anchor){this.anchor=p;this.elevation=altitude?p.z:null;return true}
  const dt=(p.time-this.anchor.time)/1000,metres=distance(this.anchor,p),speed=metres/dt;
  if(dt>30||speed>12){this.anchor=p;this.elevation=altitude?p.z:null;return true}
  // An accuracy-aware deadband suppresses stationary wander. All raw fixes stay in the log.
  if(metres<Math.max(3,((this.anchor.accuracy||0)+(p.accuracy||0))/2)||speed<.5)return true;
  this.stats.distance+=metres;this.stats.movingTime+=dt;this.anchor=p;
  if(altitude){if(this.elevation===null)this.elevation=p.z;else if(Math.abs(p.z!-this.elevation)>=5){this.stats.elevationGain+=Math.max(0,p.z!-this.elevation);this.elevation=p.z}}
  else this.elevation=null;
  return true;
 }
}
export type TrackFile={read:()=>Promise<string>;append:(text:string)=>void;reset:()=>void};
export class GPSRecording{
 accumulator=new TrackAccumulator();buffer:GPSPoint[]=[];pending:GPSPoint[]=[];ready=false;error='';segment=0;private resetAt=0;private rebuilding:Promise<void>|null=null;private epoch=0;private flushAfterRebuild=false;
 constructor(private file:TrackFile,private changed:()=>void=()=>{}){}
 get stats(){return this.accumulator.stats}
 add(point:Omit<GPSPoint,'segment'>){if(point.time<this.resetAt)return;const p={...point,segment:this.segment};if(!validPoint(p))return;if(!this.ready){this.pending.push(p);return}this.commit(p)}
 private commit(p:GPSPoint){if(!this.accumulator.add(p))return;this.buffer.push(p);if(this.buffer.length>=50)this.flush();this.changed()}
 breakSegment(){this.segment++;if(!this.ready)this.flushAfterRebuild=true;this.flush()}
 flush(){if(!this.buffer.length)return;try{this.file.append(this.buffer.map(p=>JSON.stringify(p)).join('\n')+'\n');this.buffer=[];this.error=''}catch(e){this.error='GPS points could not be saved. They are still in memory.'}this.changed()}
 whenReady(){return this.rebuilding||Promise.resolve()}
 recalculate(){if(this.rebuilding)return this.rebuilding;const task=this.replay();this.rebuilding=task;void task.finally(()=>{if(this.rebuilding===task)this.rebuilding=null});return task}
 private async replay(){if(!this.ready&&this.epoch>0)return;this.flush();if(this.buffer.length)return;const continuing=this.ready,epoch=++this.epoch;this.ready=false;this.changed();try{
  const text=await this.file.read(),lines=text.split('\n'),next=new TrackAccumulator();let invalid=0;
  for(let i=0;i<lines.length;i++){if(epoch!==this.epoch)return;if(lines[i].trim()){try{const p=JSON.parse(lines[i]);if(!validPoint(p))invalid++;else next.add(p)}catch{invalid++}}if(i%1000===999)await new Promise(resolve=>setTimeout(resolve,0))}
  if(epoch!==this.epoch)return;this.accumulator=next;this.segment=Math.max(this.segment,(next.last?.segment??-1)+(continuing?0:1));this.error=invalid?'Skipped '+invalid+' unreadable GPS records.':'';
 }catch{if(epoch!==this.epoch)return;this.error='Could not read the GPS recording. Try recalculating again.'}finally{if(epoch===this.epoch){this.ready=true;const waiting=this.pending;this.pending=[];const offset=waiting.length?Math.max(0,this.segment-waiting[0].segment):0;for(const p of waiting){this.segment=Math.max(this.segment,p.segment+offset);this.commit({...p,segment:p.segment+offset})}if(this.flushAfterRebuild){this.flushAfterRebuild=false;this.flush()}this.changed()}}}
 reset(){try{this.file.reset();this.resetAt=Date.now();this.epoch++;this.accumulator=new TrackAccumulator();this.buffer=[];this.pending=[];this.flushAfterRebuild=false;this.segment=0;this.ready=true;this.error=''}catch{this.error='Could not reset the GPS recording. Your recording was kept.'}this.changed()}
}
