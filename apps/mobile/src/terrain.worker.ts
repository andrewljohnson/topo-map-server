import contour from 'maplibre-contour';
const ctx:any=self,pending=new Map<number,any>(),jobs=new Map<number,AbortController>();let sequence=0,minZoom=3;
const manager=new contour.LocalDemManager({demUrlPattern:'{z}/{x}/{y}',encoding:'terrarium',maxzoom:13,cacheSize:24,timeoutMs:180000,
 getTile:(key:string,controller:AbortController)=>new Promise<any>((resolve,reject)=>{const id=++sequence;const cancel=()=>{pending.delete(id);ctx.postMessage({type:'cancelDem',id});reject(Error('Cancelled'))};pending.set(id,{resolve,reject,cancel,signal:controller.signal});controller.signal.addEventListener('abort',cancel,{once:true});ctx.postMessage({type:'dem',id,key})}),
 decodeImage:async(data:any)=>data});
ctx.onmessage=async(event:any)=>{const m=event.data;
 if(m.type==='configure'){manager.maxzoom=m.maxZoom===12?12:13;minZoom=m.minZoom===12?12:3;return}
 if(m.type==='demResult'){const p=pending.get(m.id);if(!p)return;pending.delete(m.id);p.signal.removeEventListener('abort',p.cancel);m.error?p.reject(Error(m.error)):p.resolve({data:m.tile});return}
 if(m.type==='cancel'){jobs.get(m.id)?.abort();return}
 if(m.type!=='contour')return;
 const controller=new AbortController();jobs.set(m.id,controller);const start=performance.now();
 try{const levels=m.z>=14?[20,100]:m.z>=13?[40,200]:m.z>=12?[100,500]:[200,1000];
  const result=await manager.fetchContourTile(m.z,m.x,m.y,{levels,multiplier:1/.3048,overzoom:m.z<=minZoom?0:1,contourLayer:'contour',elevationKey:'ele_ft',levelKey:'level',buffer:2,subsampleBelow:128},controller);
  if(controller.signal.aborted)throw Error('Cancelled');const buffer=result.arrayBuffer.slice(0);ctx.postMessage({type:'contourResult',id:m.id,buffer,ms:performance.now()-start},[buffer]);
 }catch(e){ctx.postMessage({type:'contourResult',id:m.id,error:String(e)})}finally{jobs.delete(m.id)}
};
