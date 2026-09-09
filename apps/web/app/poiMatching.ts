/** Deduplicate loaded/offline points without deleting source records or changing coordinates. */
export function installPoiMatching(map:any){
 const key=(name:any,kind:string)=>{
  let text=String(name||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim().replace(/\bmt\b/g,'mount').replace(/\bcamp ground\b/g,'campground');
  const suffix:any={campground:/\s+campground$/,trailhead:/\s+trail\s*head$/,visitor_center:/\s+visitor\s+cent(er|re)$/};
  return (suffix[kind]?text.replace(suffix[kind],''):text).replace(/\s/g,'');
 };
 const generic=new Set(['','camp','campground','trailhead','visitorcenter','restroom','restrooms','toilet','toilets','water','waterpoint','waterfountain','drinkingwater','spring','peak','summit','shop','store','picnicarea','viewpoint','information']);
 const kind=(f:any)=>{
  const p=f.properties||{};
  if(p.base_key)return ({peak:'summit',volcano:'summit',saddle:'pass',camp_site:'campground',caravan_site:'campground',alpine_hut:'shelter',trailhead:'trailhead'} as any)[p.class]||p.class;
  if(p.kind!=='amenity'&&p.kind!=='group')return p.kind;
  const icon=p.poi_icon||String(p.grid_image||'').replace(/^amenity-grid:/,'').split(',')[0],name=key(p.name,'');
  if(icon==='information')return /trailhead/.test(name)?'trailhead':/visitorcent(er|re)/.test(name)?'visitor_center':/ranger/.test(name)?'ranger_station':'information';
  return ({campsite:'campground',toilet:'restroom','drinking-water':'drinking_water',shop:'store',restaurant:'food','picnic-site':'picnic_site',viewpoint:'viewpoint',lodging:'lodging',mountain:'summit'} as any)[icon]||icon;
 };
 const meters=(a:any,b:any)=>{const [x,y]=a.geometry.coordinates,[u,v]=b.geometry.coordinates;return Math.hypot((((x-u+180)%360+360)%360-180)*111320*Math.cos((y+v)*Math.PI/360),(y-v)*111320)};
 const reason=(a:any,b:any)=>{
  const p=a.properties,q=b.properties,k=kind(a);if(k!==kind(b)&&!(['summit','rock'].includes(k)&&['summit','rock'].includes(kind(b))))return '';
  if(p.gnis_id&&q.gnis_id&&p.gnis_id!==q.gnis_id)return '';
  const d=meters(a,b);
  for(const id of ['ridb_id','gnis_id','geonames_id'])if(p[id]&&String(p[id])===String(q[id])&&d<5000)return id;
  if(p.match_ambiguous||q.match_ambiguous)return '';
  const name=key(p.name,k);if(generic.has(name)||name!==key(q.name,k))return '';
  return d<=(['summit','rock','pass'].includes(k)?300:['restroom','drinking_water','store','food'].includes(k)?15:120)?'name_kind_distance':'';
 };
 const read=(source:string,style:any,sourceLayer=source)=>{
  if(!map.getSource(source))return [];
  const vector=style.sources[source]?.type==='vector';
  return [...new Map(map.querySourceFeatures(source,vector?{sourceLayer}:{}).filter((f:any)=>f.geometry?.type==='Point'&&f.id!=null).map((f:any)=>[source==='osm'?JSON.stringify([f.properties.class,f.properties.name,f.geometry.coordinates]):f.id,f])).values()] as any[];
 };
 // Candidate indexes narrow comparisons without changing matching thresholds or
 // tie order. Full reasons still decide every match, including conflicting IDs.
 const matchingKeys=(f:any)=>{
  const p=f.properties,k=kind(f),name=key(p.name,k),family=['summit','rock'].includes(k)?'summit-rock':k;
  return [...['ridb_id','gnis_id','geonames_id'].filter(id=>p[id]).map(id=>id+':'+String(p[id])),...(!generic.has(name)?['name:'+family+':'+name]:[])];
 };
 const matchingIndex=(features:any[])=>{
  const buckets=new Map<string,Set<number>>();
  const add=(f:any,index:number)=>{for(const key of matchingKeys(f)){if(!buckets.has(key))buckets.set(key,new Set());buckets.get(key)!.add(index)}};
  features.forEach(add);
  return {add,candidates:(f:any)=>[...new Set(matchingKeys(f).flatMap(key=>[...(buckets.get(key)||[])]))].sort((a,b)=>a-b).map(index=>({index,feature:features[index]}))};
 };
 const bases=new Map<string,any>(),signatures=new Map<string,string>();
 let timer:ReturnType<typeof setTimeout>|undefined;
 function refresh(){
  if(!map.querySourceFeatures)return;
  // MapLibre serializes the style and the combined-source facade remaps its
  // layers. Share one coherent snapshot throughout this synchronous refresh.
  const style=map.getStyle();if(!style)return;
  const osmData=read('amenities',style),osm=osmData.filter(f=>f.properties.kind==='amenity'),recreation=read('recreation',style);
  const groups=new Map(osmData.filter(f=>f.properties.kind==='group').map(f=>[f.properties.group_id,f]));
  const zoom=map.getZoom();
  const groupRanks=new Map<string,{minimum:number,rank:number}>(),peakRanks=new Map<string,number>();
  const base=read('osm',style,'poi').map(f=>({...f,id:f.id,geometry:f.geometry,source:'osm',sourceLayer:'poi',properties:{...f.properties,base_key:JSON.stringify([f.properties.class,f.properties.name,f.geometry.coordinates])}}));
  const osmVisible=(f:any)=>{const p=f.properties;if(p.base_key){const minimum=p.poi_icon==='mountain'?Math.max(11,(p.min_zoom??14)-1):['campsite','viewpoint','swimming','information','lodging'].includes(p.poi_icon)?Math.max(11,p.min_zoom??12):Math.max(14,p.min_zoom??14);return zoom>=Math.max(minimum,style.layers?.find((l:any)=>l.id==='peak-labels'&&p.poi_icon==='mountain')?.minzoom||0)}if(!p.group_id)return zoom>=Math.max(p.detail_minzoom??14,['shop','restaurant','cafe','information'].includes(p.poi_icon)?15:14);if(zoom>=15)return true;const group=groups.get(p.group_id);if(!group)return false;const g=group.properties;return zoom>=Math.max(g.min_zoom||10,String(g.grid_image||'').includes(',')?10:13,groupRanks.get(p.group_id)?.minimum||0)};
  const hiddenOSM=new Set<number>(),hiddenRecreation=new Set<number>(),details=new Map<string,any>(),kept:any[]=[];
  // Parent/site representations are preferable to unnamed representations of the same object.
  osm.sort((a,b)=>(b.properties.osm_id===b.properties.group_id?1:0)-(a.properties.osm_id===a.properties.group_id?1:0)||Number(!!b.properties.name)-Number(!!a.properties.name)||String(a.properties.osm_id).localeCompare(String(b.properties.osm_id)));
  const groupMembers=new Map<string,any[]>();
  for(const f of osm){
   const p=f.properties,groupKey=JSON.stringify([p.group_id,p.poi_icon]);
   const same=p.group_id&&(groupMembers.get(groupKey)||[]).find(g=>{const q=g.properties;return p.group_id&&p.group_id===q.group_id&&p.poi_icon===q.poi_icon&&p.osm_id?.split('/')[0]!==q.osm_id?.split('/')[0]&&(!p.name||!q.name||key(p.name,kind(f))===key(q.name,kind(g)))&&meters(f,g)<=3});
   if(same)hiddenOSM.add(f.id);else {kept.push(f);if(p.group_id){if(!groupMembers.has(groupKey))groupMembers.set(groupKey,[]);groupMembers.get(groupKey)!.push(f)}}
  }
  const canonical:any[]=[],canonicalIndex=matchingIndex(canonical),amenityIndex=matchingIndex(kept),baseIndex=matchingIndex(base);
  const priority=(f:any)=>({NPS:0,USFS:1,'Recreation.gov':2,'USGS GNIS':3,GeoNames:4} as any)[f.properties.agency]??5;
  const sourceRecords=(f:any)=>{try{const records=JSON.parse(f.properties.source_records||'[]');if(records.length)return records}catch{}return [{id:f.properties.id,agency:f.properties.agency,name:f.properties.name,coordinates:f.geometry.coordinates,source_url:f.properties.source_url,details:f.properties}]};
  function merged(a:any,b:any,why:string){
   const p={...a.properties};for(const [k,v]of Object.entries(b.properties))if(!p[k])p[k]=v;
   const records=[...new Map([...sourceRecords(a),...sourceRecords(b)].map((r:any)=>[r.id,r])).values()];
   p.source_records=JSON.stringify(records);p.source_count=records.length;p.match_reason=why;
   return {...a,id:a.id,geometry:a.geometry,source:a.source,sourceLayer:a.sourceLayer,properties:p};
  }
  for(const f of recreation.sort((a,b)=>Number(zoom>=(b.properties.min_zoom??10))-Number(zoom>=(a.properties.min_zoom??10))||priority(a)-priority(b)||String(a.properties.id).localeCompare(String(b.properties.id)))){
   const matches=canonicalIndex.candidates(f).map(({index:i,feature:g})=>({i,why:reason(f,g),d:meters(f,g)})).filter(c=>c.why).sort((a,b)=>Number(b.why.endsWith('_id'))-Number(a.why.endsWith('_id'))||a.d-b.d);
   const best=matches[0];const same=best&&(best.why.endsWith('_id')||matches.length===1||matches[1].d-best.d>=30)?best.i:-1;
   if(same>=0){hiddenRecreation.add(f.id);canonical[same]=merged(canonical[same],f,reason(f,canonical[same]));canonicalIndex.add(canonical[same],same)}else {canonical.push(f);canonicalIndex.add(f,canonical.length-1)}
  }
  // Nearby same-name small facilities may be distinct buildings or imprecise
  // agency points. Share their presentation, never their underlying identity.
  const hiddenDetailNames=new Set<number>();
  const facilityWords=new Set(['vault','flush','pit','public','accessible','men','mens','women','womens','unisex','restroom','restrooms','toilet','toilets','wc','water','drinking','potable','pump','fountain']);
  const distinctive=(f:any)=>['restroom','drinking_water'].includes(kind(f))&&f.properties.agency&&f.properties.unit&&String(f.properties.name||'').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').split(/[^a-z0-9]+/).some(word=>word.length>=3&&!facilityWords.has(word));
  const presentationGroups:{lead:any,members:any[]}[]=[];
  for(const f of canonical){
   if(!distinctive(f))continue;
   const p=f.properties;
   const group=presentationGroups.find(g=>g.lead.properties.agency===p.agency&&g.lead.properties.unit===p.unit&&kind(g.lead)===kind(f)&&key(g.lead.properties.name,kind(f))===key(p.name,kind(f))&&g.members.every(m=>meters(f,m)<=120));
   if(group)group.members.push(f);else presentationGroups.push({lead:f,members:[f]});
  }
  for(const group of presentationGroups){
   if(group.members.length<2)continue;
   let combined=group.lead;
   for(const member of group.members.slice(1)){
    combined=merged(combined,member,'nearby_named_facility_display_group');
    hiddenDetailNames.add(member.id);
    if(zoom<17)hiddenRecreation.add(member.id);
   }
   combined.properties.display_group_count=group.members.length;
   canonical[canonical.indexOf(group.lead)]=combined;
  }
  for(const f of canonical){
   const amenityCandidates=amenityIndex.candidates(f).map(c=>c.feature).filter(g=>reason(f,g));
   const candidates=(amenityCandidates.length?amenityCandidates:baseIndex.candidates(f).map(c=>c.feature).filter(g=>reason(f,g))).sort((a,b)=>meters(f,a)-meters(f,b));
   // Do not guess between distinct nearby sites with equally good names.
   const same=candidates[0],ambiguous=candidates[1]&&meters(f,candidates[1])-meters(f,same)<30;
   if(same&&!ambiguous){
    const p=f.properties,q=same.properties;
    if(p.label_rank!=null){
     if(q.base_key&&['summit','rock'].includes(kind(f)))peakRanks.set(q.class+'|'+q.name,p.label_rank);
     if(p.rank_family==='destination'&&q.group_id&&(q.osm_id===q.group_id||key(groups.get(q.group_id)?.properties.name,kind(f))===key(p.name,kind(f))))groupRanks.set(q.group_id,{minimum:p.label_minzoom,rank:p.label_rank});
    }
    if(osmVisible(same))hiddenRecreation.add(f.id);const id=same.properties.osm_id||'base:'+same.properties.base_key,prior=details.get(id);
    details.set(id,prior?merged(prior,f,reason(f,same)):f);
   }
   details.set(f.properties.id,f);
  }
  map.__topoPoiDetails=details;
  map.__topoPoiMatchStats={osmDuplicates:hiddenOSM.size,agencyDuplicates:hiddenRecreation.size,nearbyFacilityGroups:presentationGroups.filter(g=>g.members.length>1).length,matchedSites:[...details.keys()].filter(id=>/^(node|way|relation)\//.test(id)).length};
  map.__topoHiddenAmenityIds=hiddenOSM;
  const apply=(id:string,hidden:Set<number>)=>{
   const layer=style.layers?.find((l:any)=>l.id===id);if(!layer)return;
   if(!bases.has(id))bases.set(id,layer.filter);
   const sorted=[...hidden].sort((a,b)=>a-b),sig=JSON.stringify(sorted);if(signatures.get(id)===sig)return;signatures.set(id,sig);
   const base=bases.get(id);map.setFilter(id,sorted.length?['all',...(base?[base]:[]),['!',['in',['id'],['literal',sorted]]]]:base);
  };
  for(const id of ['amenity-details','amenity-secondary-details','amenity-signposts','amenity-cycle-signposts','amenity-group-members'])apply(id,hiddenOSM);
  for(const id of ['recreation-pois','recreation-poi-details','ranked-peaks'])apply(id,hiddenRecreation);
  const hiddenGroups=new Set<number>();for(const [id,rank]of groupRanks){const group=groups.get(id);if(group&&zoom<rank.minimum)hiddenGroups.add(group.id)}apply('amenity-groups',hiddenGroups);
  const sort=(id:string,field:any,entries:any[])=>{
   if(!map.setLayoutProperty||!style.layers?.some((l:any)=>l.id===id))return;
   entries.sort((a,b)=>String(a[0]).localeCompare(String(b[0])));
   const expression=entries.length?['match',field,...entries.flat(),100000]:100000,signature=JSON.stringify(expression);
   if(signatures.get('sort:'+id)===signature)return;signatures.set('sort:'+id,signature);map.setLayoutProperty(id,'symbol-sort-key',expression);
  };
  if(map.setLayoutProperty&&style.layers?.some((l:any)=>l.id==='recreation-poi-details')){
   const ids=[...hiddenDetailNames].sort((a,b)=>a-b),signature=JSON.stringify(ids);
   if(signatures.get('detail-names')!==signature){
    signatures.set('detail-names',signature);
    map.setLayoutProperty('recreation-poi-details','text-field',ids.length?['case',['in',['id'],['literal',ids]],'',['get','name']]:['get','name']);
   }
  }
  sort('peak-labels',['concat',['get','class'],'|',['get','name']],[...peakRanks]);
  sort('amenity-groups',['get','group_id'],[...groupRanks].map(([id,rank])=>[id,rank.rank]));

 }
 const schedule=()=>{if(timer!==undefined)return;timer=setTimeout(()=>{timer=undefined;refresh()},50)};
 const source=(e:any)=>{if(['osm','amenities','recreation'].includes(e.sourceId))schedule()};
 const reset=()=>{bases.clear();signatures.clear();schedule()};
 map.on('sourcedata',source);map.on('moveend',schedule);map.on('idle',refresh);map.on('style.load',reset);
 map.on('remove',()=>{if(timer!==undefined)clearTimeout(timer);map.off('sourcedata',source);map.off('moveend',schedule);map.off('idle',refresh);map.off('style.load',reset)});
}
