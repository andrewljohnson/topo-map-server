// Compose the whole grid into one symbol so collision placement is atomic.
export function installAmenityImages(map: any) {
 function add(id: string) {
  if(!id.startsWith('amenity-grid:')||map.hasImage(id))return;
  const names=id.slice(13).split(',').filter(Boolean);
  if(!names.length||names.length>12)return;
  const columns=Math.min(3,names.length),rows=Math.ceil(names.length/columns);
  const canvas=document.createElement('canvas');canvas.width=columns*44;canvas.height=rows*44;
  const ctx=canvas.getContext('2d');if(!ctx)return;
  for(let i=0;i<names.length;i++){
   const frame=['campsite','swimming','viewpoint','lodging'].includes(names[i])?'circle':'square';
   const source=map.getImage('poi-'+frame+'-'+names[i]);if(!source)return;
   const tile=document.createElement('canvas');tile.width=source.data.width;tile.height=source.data.height;
   tile.getContext('2d')!.putImageData(new ImageData(new Uint8ClampedArray(source.data.data),source.data.width,source.data.height),0,0);
   ctx.drawImage(tile,(i%columns)*44,Math.floor(i/columns)*44,44,44);
  }
  map.addImage(id,ctx.getImageData(0,0,canvas.width,canvas.height),{pixelRatio:2});
 }
 // Close or coincident amenities can otherwise cover one another. Keep the
 // geographic point unchanged and arrange their symbols around that anchor.
 let signature='';
 function separateCoincident(){
  if(!map.querySourceFeatures||!map.getLayer('amenity-group-members')||map.getZoom()<15)return;
  const vector=map.getStyle().sources.amenities?.type==='vector';
  const buckets=new Map<string,Map<number,any>>();
  for(const f of map.querySourceFeatures('amenities',vector?{sourceLayer:'amenities'}:{})){
   if(map.__topoHiddenAmenityIds?.has(f.id))continue;
   if(f.properties?.kind!=='amenity'||!f.properties.group_id||f.id==null)continue;
   const key=f.geometry.coordinates.join(',');
   if(!buckets.has(key))buckets.set(key,new Map());
   buckets.get(key)!.set(f.id,f);
  }
  const offsets:any[]=[],placed:{x:number,y:number,w:number,h:number}[]=[];
  const scale=.65+Math.min(1,map.getZoom()-15)*.2;
  const all=new Map<number,any>();
  for(const bucket of buckets.values())for(const [id,f]of bucket)all.set(id,f);
  const candidates=[[0,0]];
  for(let r=1;r<=4;r++)for(let x=-r;x<=r;x++)for(let y=-r;y<=r;y++)if(Math.max(Math.abs(x),Math.abs(y))===r)candidates.push([x*28,y*28]);
  candidates.sort((a,b)=>Math.hypot(a[0],a[1])-Math.hypot(b[0],b[1])||a[1]-b[1]||a[0]-b[0]);
  for(const [id,f]of [...all].sort((a,b)=>a[0]-b[0])){
   const point=map.project(f.geometry.coordinates);
   const count=String(f.properties.grid_image||'').startsWith('amenity-grid:')?String(f.properties.grid_image).slice(13).split(',').length:1;
   const w=(count>1?22*Math.min(count,3):24)*scale,h=(count>1?22*Math.ceil(count/3):24)*scale;
   let chosen=candidates.find(([dx,dy])=>!placed.some(p=>Math.abs(p.x-point.x-dx*scale)<(p.w+w)/2+4*scale-1e-6&&Math.abs(p.y-point.y-dy*scale)<(p.h+h)/2+4*scale-1e-6))||[0,0];
   placed.push({x:point.x+chosen[0]*scale,y:point.y+chosen[1]*scale,w,h});
   if(chosen[0]||chosen[1])offsets.push(id,['literal',chosen]);
  }
  const next=JSON.stringify(offsets);if(next===signature)return;signature=next;
  map.setLayoutProperty('amenity-group-members','icon-offset',offsets.length?['match',['id'],...offsets,['literal',[0,0]]]:[0,0]);
 }
 let timer:ReturnType<typeof setTimeout>|undefined;
 const schedule=()=>{if(timer!==undefined)return;timer=setTimeout(()=>{timer=undefined;separateCoincident()},50)};
 const sourceChanged=(event:any)=>{if(event.sourceId==='amenities')schedule()};
 const reset=()=>{signature=''};
 map.on('sourcedata',sourceChanged);
 map.on('moveend',schedule);
 map.on('style.load',reset);
 map.on('idle',separateCoincident);
 map.on('remove',()=>{map.off('idle',separateCoincident);map.off('style.load',reset);map.off('sourcedata',sourceChanged);map.off('moveend',schedule);if(timer!==undefined)clearTimeout(timer)});
 map.on('styleimagemissing',(event: any)=>add(event.id));
}
