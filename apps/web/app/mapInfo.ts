/** Current-viewport legend shared with the embedded mobile renderer. */
export function installMapInfo(map: any) {
 let cleanup=()=>{};
 map.addControl({onAdd:()=>{
 const append=(parent:Node,...children:Node[])=>{for(const child of children)parent.appendChild(child)};
 const names: Record<string,string> = {restaurant:'Restaurant',cafe:'Café',toilet:'Restrooms','drinking-water':'Drinking water',parking:'Parking',fuel:'Fuel',information:'Information',hospital:'Medical care',pharmacy:'Pharmacy','picnic-site':'Picnic area',campsite:'Camping',lodging:'Lodging',mountain:'Peak',viewpoint:'Viewpoint',park:'Park',monument:'Historic site',museum:'Museum',shop:'Shop',swimming:'Swimming',waterfall:'Waterfall',cascade:'Cascade',arch:'Natural arch',cave:'Cave',spring:'Spring',rock:'Rock landmark',pass:'Pass / saddle',shelter:'Shelter',marker:'Other amenity',fishing:'Fishing','boat-ramp':'Boat ramp'};
 const labels: Record<string,string> = {forest:'Woodland',grass:'Grassland / meadow','landcover-scrub':'Scrub','landcover-agriculture':'Farmland','landcover-orchard':'Orchard','landcover-wetland':'Wetland',residential:'Developed land',rock:'Bare rock','landcover-sand':'Sand / beach','landcover-ice':'Glacier / ice',water:'Lake / water',buildings:'Building','contours':'Contour · feet','contour-index':'Index contour · feet','waterways':'Stream / river','waterways-perennial':'Stream / river','waterways-intermittent':'Intermittent / seasonal stream','waterways-seasonal':'Seasonal stream / river','state-boundaries':'State boundary','park-boundaries':'Park boundary','forest-boundaries':'National forest boundary','wilderness-boundaries':'Wilderness boundary','roads-local':'Local road','roads-tertiary':'Connecting road','roads-secondary':'Secondary road','roads-primary':'Primary road','roads-highway':'Highway','unpaved-roads':'Unpaved road','tracks-center':'Track / forest road','trails-path':'Trail','trails-footway':'Footpath','trails-cycleway':'Bicycle path','trails-bridleway':'Bridleway','trails-pedestrian':'Pedestrian way','trails-sidewalk':'Sidewalk / crossing','trails-step-treads':'Steps','railway':'Railway','location-marker':'Your location','location-accuracy':'Location accuracy'};
 Object.assign(labels,{'nlcd-forest':'Woodland','nlcd-scrub':'Scrub','nlcd-grass':'Grassland / meadow','nlcd-wetland':'Wetland','nlcd-farmland':'Farmland','nlcd-rock':'Bare rock','nlcd-ice':'Glacier / ice','nlcd-developed':'Developed land','official-roads-center':'MVUM forest road','official-trails':'Agency trail','official-motorized-trails':'Motorized trail','long-trail-route':'Long-distance trail','long-trail-pct':'Pacific Crest Trail (PCT)','long-trail-trt':'Tahoe Rim Trail (TRT)','long-trail-other':'Other long-distance trail'});
 const style=document.createElement('style'); style.textContent=`
 .topo-info-control{width:24px;height:24px;position:relative;pointer-events:auto}
 .topo-info-control button{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border:0;border-radius:50%;padding:0;background:#fafbf5;color:#153e30;box-shadow:0 2px 8px #14304425;cursor:pointer}
 .topo-info-control button::before{content:'i';font:bold 13px Georgia,serif;color:#fff;background:#173b2e;border-radius:50%;width:15px;height:15px;line-height:15px;text-align:center}
 .topo-info-overlay{position:absolute;inset:0;z-index:20;background:#18342628;font:14px/1.4 Arial,sans-serif;color:#234234}
 .topo-info-overlay[hidden]{display:none}
 .topo-info-sheet{position:absolute;bottom:0;left:var(--safe-left,env(safe-area-inset-left,0px));right:var(--safe-right,env(safe-area-inset-right,0px));max-width:580px;margin:auto;background:#fafbf5;border-radius:20px 20px 0 0;box-shadow:0 -4px 28px #14304424;max-height:55vh;display:flex;flex-direction:column;padding-bottom:var(--safe-bottom,env(safe-area-inset-bottom,0px));box-sizing:border-box;overflow:hidden}
 .topo-info-heading{display:flex;align-items:center;justify-content:space-between;padding:8px 12px 0 20px;flex-shrink:0}
 .topo-info-heading h2{font:bold 18px Arial,sans-serif;margin:10px 0}
 .topo-info-heading button{border:0;background:none;color:#234234;width:44px;height:44px;font-size:27px;cursor:pointer}
 .topo-info-scroll{overflow:auto;overscroll-behavior:contain;padding:0 20px 20px;-webkit-overflow-scrolling:touch}
 .topo-info-note{font-size:12px;color:#617264;margin:0 0 12px}
 .topo-info-legend{column-count:2;column-gap:16px;column-fill:balance;margin-bottom:20px}
 .topo-info-group{margin:0}
 .topo-info-group h3{font-size:13px;line-height:18px;font-weight:700;margin:16px 0 10px;padding:0;color:#234234;break-after:avoid;-webkit-column-break-after:avoid}
 .topo-info-group:first-child h3{margin-top:0}
 .topo-info-list{margin:0;padding:0;list-style:none;break-before:avoid}
 .topo-info-list li{display:flex;align-items:center;gap:8px;font-size:12px;min-height:28px;break-inside:avoid;-webkit-column-break-inside:avoid;margin-bottom:8px}
 .topo-info-list canvas{width:40px;height:28px;flex-shrink:0}
 .topo-info-credits{border-top:1px solid #d8dfd3;padding-top:12px;font-size:11px;line-height:1.7}
 .topo-info-credits h3{font-size:13px;margin:0 0 5px}.topo-info-credits p{margin:0 0 5px}.topo-info-credits a{color:#286447;text-decoration:underline}
 .topo-info-sheet :focus-visible{outline:2px solid #286447;outline-offset:2px}
 `;document.head.appendChild(style);
 const el=(tag:string,className='')=>{const node=document.createElement(tag);node.className=className;return node};
 const control=el('div','maplibregl-ctrl topo-info-control');const button=el('button') as HTMLButtonElement;button.type='button';button.setAttribute('aria-label','Map legend and attribution');button.setAttribute('aria-expanded','false');append(control,button);
 const overlay=el('div','topo-info-overlay');overlay.hidden=true;
 const sheet=el('section','topo-info-sheet');sheet.setAttribute('role','dialog');sheet.setAttribute('aria-modal','true');sheet.setAttribute('aria-label','Map legend and attribution');
 const heading=el('div','topo-info-heading'),title=el('h2');title.textContent='Map legend';const close=el('button') as HTMLButtonElement;close.type='button';close.textContent='×';close.setAttribute('aria-label','Close map legend');append(heading,title,close);
 const scroll=el('div','topo-info-scroll'),note=el('p','topo-info-note'),list=el('div','topo-info-legend'),credits=el('div','topo-info-credits');note.hidden=true;append(scroll,note,list,credits);append(sheet,heading,scroll);append(overlay,sheet);map.getContainer().appendChild(overlay);
 let signature='';
 function sample(canvas:HTMLCanvasElement,item:any){
  canvas.width=80;canvas.height=56;const ctx=canvas.getContext('2d');if(!ctx)return;ctx.scale(2,2);
  if(item.image){const image=map.getImage(item.image);if(image?.data){const d=image.data,tmp=document.createElement('canvas');tmp.width=d.width;tmp.height=d.height;tmp.getContext('2d')!.putImageData(new ImageData(new Uint8ClampedArray(d.data),d.width,d.height),0,0);const size=Math.min(26/d.width,26/d.height);ctx.drawImage(tmp,(40-d.width*size)/2,(28-d.height*size)/2,d.width*size,d.height*size);if(item.shield){ctx.fillStyle=['interstate','county','california'].includes(item.shield)?'#fffdf5':'#30332e';ctx.font='bold 9px Arial';ctx.textAlign='center';ctx.fillText(item.shield==='interstate'?'80':'50',20,17)}return}}
  const paint=item.layer?.paint||{},color=paint['line-color']||paint['fill-color']||paint['circle-color']||'#476b50';ctx.strokeStyle=ctx.fillStyle=typeof color==='string'?color:'#476b50';
  if(item.id==='terrain-shading'){const gradient=ctx.createLinearGradient(4,6,36,22);gradient.addColorStop(0,'#faf8ed');gradient.addColorStop(.5,'#c5ccb8');gradient.addColorStop(1,'#7b8473');ctx.fillStyle=gradient;ctx.fillRect(4,6,32,16);return}
  if(item.layer?.type==='fill'){ctx.globalAlpha=typeof paint['fill-opacity']==='number'?paint['fill-opacity']:1;ctx.fillRect(4,6,32,16);ctx.globalAlpha=1;const pattern=map.getImage(item.pattern||'');if(pattern?.data){const d=pattern.data,tmp=document.createElement('canvas');tmp.width=d.width;tmp.height=d.height;tmp.getContext('2d')!.putImageData(new ImageData(new Uint8ClampedArray(d.data),d.width,d.height),0,0);ctx.drawImage(tmp,0,0,32,16,4,6,32,16)}ctx.strokeStyle='#70806f';ctx.lineWidth=.5;ctx.strokeRect(4,6,32,16);return}
  if(item.layer?.type==='circle'){ctx.beginPath();ctx.arc(20,14,6,0,Math.PI*2);ctx.fill();return}
  // A legend stroke uses the same ordered paint layers as its map feature.
  const zoom=typeof map.getZoom==='function'?map.getZoom():14;
  const width=(value:any):number=>{
   if(typeof value==='number')return value;
   if(Array.isArray(value)&&value[0]==='interpolate'&&value[2]?.[0]==='zoom'){
    if(zoom<=value[3])return value[4];
    for(let i=5;i<value.length;i+=2)if(zoom<=value[i])return value[i-1]+(value[i+1]-value[i-1])*(zoom-value[i-2])/(value[i]-value[i-2]);
    return value[value.length-1];
   }return 1.5;
  };
  const stack=item.stack?.length?item.stack:[item.layer];
  const outer=Math.max(...stack.map((layer:any)=>width(layer?.paint?.['line-width'])));
  const magnification=stack.length>1?6/Math.max(.1,outer):1;
  for(const layer of stack){
   const paint=layer?.paint||{};ctx.strokeStyle=typeof paint['line-color']==='string'?paint['line-color']:'#476b50';
   ctx.lineWidth=stack.length>1?width(paint['line-width'])*magnification:(item.id==='contours'?1:1.8);
   ctx.lineCap=layer?.layout?.['line-cap']||'butt';
   const dash=paint['line-dasharray'];ctx.setLineDash(Array.isArray(dash)&&dash.every((v:any)=>typeof v==='number')?dash.map((v:number)=>v*ctx.lineWidth):[]);
   ctx.beginPath();ctx.moveTo(4,14);ctx.lineTo(36,14);ctx.stroke();
  }
  if(item.id==='railway'){ctx.setLineDash([]);ctx.lineWidth=1;for(let x=6;x<38;x+=6){ctx.beginPath();ctx.moveTo(x,10);ctx.lineTo(x,18);ctx.stroke()}}
 }
 function refresh(){if(overlay.hidden)return;const styleLayers=new Map<string,any>((map.getStyle()?.layers||[]).map((layer:any)=>[layer.id,layer]));const items=new Map<string,any>();let features:any[]=[];try{features=map.queryRenderedFeatures()}catch{return}
  const addPoi=(icon:string,frame:string)=>{if(!names[icon])return;const id='poi-'+frame+'-'+icon;items.set(id,{id,label:names[icon],image:id})};
  for(const f of features){const raw=f.layer?.id||'',id=raw.replace(/-bridge$/,'').replace(/^detailed-/,'').replace(/-overview$/,''),p=f.properties||{};
   if(raw==='amenity-groups'||(p.grid_image&&String(p.grid_image).startsWith('amenity-grid:'))){for(const icon of String(p.grid_image||'').replace(/^amenity-grid:/,'').split(','))addPoi(icon,['campsite','swimming','viewpoint','lodging'].includes(icon)?'circle':'square');continue}
   if(raw.startsWith('recreation-poi')||raw==='ranked-peaks'){
    const label=({trailhead:'Trailhead',spring:'Spring',waterfall:'Waterfall',shelter:'Shelter',summit:'Summit',pass:'Pass / saddle',arch:'Natural arch',rock:'Rock landmark',cave:'Cave',ranger_station:'Ranger station',visitor_center:'Visitor center'} as any)[p.kind];
    if(label){const cascade=p.kind==='waterfall'&&/cascade/i.test(p.name||'');const id='poi-recreation-'+(cascade?'cascade':p.kind);items.set(id,{id,label:cascade?'Cascade':label,image:map.__topoPoiIcon?.(p)||p.poi_image||'poi-'+p.poi_frame+'-'+p.poi_icon});continue}
   }
   if(['poi-icons','outdoor-pois','peak-labels','amenity-details','amenity-group-members','recreation-pois','recreation-poi-details'].includes(raw)){const natural=map.__topoPoiIcon?.(p);if(natural){const [,frame,...icon]=natural.split('-');addPoi(icon.join('-'),frame)}else addPoi(p.poi_icon,p.poi_frame);continue}
   if(raw==='long-trail-badges'){const id='trail-badge-'+p.route_ref;items.set(id,{id,label:p.name||p.route_ref,image:p.badge});continue}
   if(id==='highway-shields'){const kind=p.network==='US:CA'?'california':p.shield_kind||'state';items.set('shield-'+kind,{id:'shield-'+kind,label:({interstate:'Interstate highway',us:'U.S. highway',state:'State route',california:'California route',county:'County route'} as any)[kind]||'Route shield',image:'shield-'+kind,shield:kind});continue}
   if(labels[id]){
    const legendZoom=map.getZoom?.()??14,terrainInterval=legendZoom>=14?20:legendZoom>=13?40:legendZoom>=12?100:200;
    const terrainLabel=map.getSource?.('dem')&&(id==='contours'||id==='contour-index')?(id==='contours'?'Contour · '+terrainInterval+' ft':'Index contour · '+(terrainInterval*5)+' ft'):labels[id];
    let stackIds:string[]=[];
    if(id==='official-roads-center')stackIds=['official-roads-casing','official-roads','official-roads-center'];
    else if(id==='official-trails'||id==='official-motorized-trails')stackIds=['official-trails-halo',raw];
    else if(['long-trail-pct','long-trail-trt','long-trail-other'].includes(id))stackIds=[id+'-halo',id];
    else if(id==='long-trail-route')stackIds=['long-trail-halo',raw];
    else if(id==='tracks-center')stackIds=['tracks-casing','tracks','tracks-center'];
    else if(id==='trails-step-treads')stackIds=['trails-halo','trails-steps','trails-step-treads'];
    else if(id.startsWith('trails-'))stackIds=['trails-halo',raw];
    else if(id.startsWith('roads-'))stackIds=[id+'-casing',id];
    else if(id==='unpaved-roads'){
     const road=['motorway','motorway_link','trunk','trunk_link'].includes(p.class)?'highway':String(p.class||'').startsWith('primary')?'primary':String(p.class||'').startsWith('secondary')?'secondary':String(p.class||'').startsWith('tertiary')?'tertiary':'local';
     stackIds=['roads-'+road+'-casing','roads-'+road,raw];
    }
    items.set(id,{id,label:terrainLabel,pattern:styleLayers.get(raw+'-texture')?.paint?.['fill-pattern'],layer:styleLayers.get(raw)||f.layer,stack:stackIds.map(key=>styleLayers.get(raw.endsWith('-overview')?key.replace(/-overview$/,'')+'-overview':key)).filter(Boolean)});
   }
  }
  if(map.getSource?.('dem')&&map.getZoom()>=3)items.set('terrain-shading',{id:'terrain-shading',label:'Shaded relief'});
  // One swatch per land-cover class when NLCD and OSM both cover the view.
  const fills=new Map<string,any>();
  for(const item of items.values())if(item.layer?.type==='fill'){
   const prior=fills.get(item.label);
   if(prior){if(item.id.startsWith('nlcd-')){items.delete(prior.id);fills.set(item.label,item)}else items.delete(item.id)}
   else fills.set(item.label,item);
  }
  const groups=['Places & amenities','Roads & trails','Water','Elevation','Land cover','Boundaries','Your location'];
  const group=(id:string)=>id.startsWith('poi-')?0:id.startsWith('official-')||id.startsWith('long-trail')||id.startsWith('trail-badge-')||id.startsWith('roads-')||id.startsWith('trails-')||id.startsWith('tracks-')||id.startsWith('shield-')||id==='unpaved-roads'||id==='railway'?1:id==='water'||id.startsWith('waterways')?2:id==='contours'||id==='contour-index'||id==='terrain-shading'?3:id.endsWith('-boundaries')?5:id.startsWith('location-')?6:4;
  const order=['roads-highway','roads-primary','roads-secondary','roads-tertiary','roads-local','unpaved-roads','tracks-center','trails-path','trails-footway','trails-cycleway','trails-bridleway','trails-pedestrian','trails-sidewalk','trails-step-treads','railway','water','waterways-perennial','waterways','waterways-intermittent','waterways-seasonal','contour-index','contours'];
  const rank=(id:string)=>order.includes(id)?order.indexOf(id):100;
  const rows=[...items.values()].sort((a,b)=>group(a.id)-group(b.id)||rank(a.id)-rank(b.id)||a.label.localeCompare(b.label));
  const next=JSON.stringify(rows.map(i=>[i.id,i.layer?.paint,i.stack,typeof map.getZoom==='function'?map.getZoom():14]));if(next===signature)return;signature=next;list.replaceChildren();
  for(let index=0;index<groups.length;index++){
   const members=rows.filter(item=>group(item.id)===index);if(!members.length)continue;
   const section=el('section','topo-info-group'),heading=el('h3'),entries=el('ul','topo-info-list');heading.textContent=groups[index];append(section,heading,entries);append(list,section);
   for(const item of members){const row=el('li'),canvas=el('canvas') as HTMLCanvasElement,label=el('span');canvas.setAttribute('aria-hidden','true');sample(canvas,item);label.textContent=item.label;append(row,canvas,label);append(entries,row)}
  }
  note.hidden=rows.length>0;note.textContent=rows.length?'':'No map symbols loaded in this view yet.';
 }
 function attribution(){credits.replaceChildren();const title=el('h3');title.textContent='Map attribution';append(credits,title);const seen=new Set<string>();for(const source of Object.values(map.getStyle()?.sources||{}) as any[]){if(!source.attribution||seen.has(source.attribution))continue;seen.add(source.attribution);const para=el('p'),parsed=new DOMParser().parseFromString(String(source.attribution),'text/html');
   const copy=(from:Node,to:Node)=>{for(const child of Array.from(from.childNodes)){if(child.nodeType===3)to.appendChild(document.createTextNode(child.textContent||''));else if(child instanceof Element){if(child.tagName==='A'&&/^https?:\/\//i.test(child.getAttribute('href')||'')){const a=document.createElement('a');a.href=child.getAttribute('href')!;a.target='_blank';a.rel='noopener noreferrer';a.textContent=child.textContent;to.appendChild(a)}else if(!['SCRIPT','STYLE','IFRAME','OBJECT'].includes(child.tagName))copy(child,to)}}};copy(parsed.body,para);append(credits,para)}
  const links=el('p');for(const [label,url] of [['NPS','https://www.nps.gov/subjects/gisandmapping/'],['USFS','https://data.fs.usda.gov/geodata/'],['Wilderness Connect','https://wilderness.net/'],['Natural Earth','https://www.naturalearthdata.com/'],['Maki icons · CC0','https://github.com/mapbox/maki']]){if(links.childNodes.length)append(links,document.createTextNode(' · '));const a=document.createElement('a');a.textContent=label;a.href=url;a.target='_blank';a.rel='noopener noreferrer';append(links,a)}append(credits,links)
 }
 function notifyDrawer(open:boolean){(window as any).ReactNativeWebView?.postMessage(JSON.stringify({type:'infoDrawer',open}))}
 function hide(){notifyDrawer(false);overlay.hidden=true;button.setAttribute('aria-expanded','false');button.focus()}
 function open(){notifyDrawer(true);overlay.hidden=false;button.setAttribute('aria-expanded','true');signature='';attribution();refresh();close.focus()}
 const keydown=(event:KeyboardEvent)=>{if(overlay.hidden)return;if(event.key==='Escape'){event.preventDefault();hide()}else if(event.key==='Tab'){const nodes=Array.from(sheet.querySelectorAll<HTMLElement>('button,a[href]')),first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}};
 button.onclick=open;close.onclick=hide;overlay.onclick=e=>{if(e.target===overlay)hide()};for(const type of ['mousedown','touchstart','dblclick','wheel'])overlay.addEventListener(type,e=>e.stopPropagation());document.addEventListener('keydown',keydown);
 map.on('idle',refresh);map.on('moveend',refresh);
 cleanup=()=>{notifyDrawer(false);document.removeEventListener('keydown',keydown);map.off('idle',refresh);map.off('moveend',refresh);overlay.remove();style.remove();control.remove()};
 return control;
 },onRemove:()=>cleanup()},'bottom-right');
}
