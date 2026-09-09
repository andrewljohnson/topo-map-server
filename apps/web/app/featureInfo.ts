/** Agency facility/route details attached to base-map features. */
export function installFeatureInfo(map:any,Popup:any,enabled:()=>boolean=()=>true){
 const clean=(value:any)=>{const parsed=new DOMParser().parseFromString(String(value??''),'text/html');for(const el of Array.from(parsed.querySelectorAll('script,style,iframe,object')))el.remove();return (parsed.body.textContent||'').replace(/\s+/g,' ').trim()};
 const normalize=(value:any)=>clean(value).toLowerCase().replace(/[^a-z0-9]/g,'');
 let popup:any;
 map.on('click',(event:any)=>{
  if(!enabled())return;
  const ids=['recreation-pois','recreation-poi-details','amenity-group-members','amenity-details','amenity-secondary-details','amenity-groups','ranked-peaks','peak-labels','outdoor-pois','poi-icons','long-trail-badges','official-road-refs','official-roads-center','trails-path','trails-footway','trails-cycleway','trails-bridleway','trail-labels','tracks-center','road-labels'];
  const networkLayers=(map.getStyle()?.layers||[]).filter((l:any)=>l.source==='trails'&&l['source-layer']==='network'&&l.type==='line'&&!/halo|casing/.test(l.id)).map((l:any)=>l.id);
  const layers=[...new Set([...ids,...networkLayers])].filter(id=>map.getLayer(id));if(!layers.length)return;
  const features=map.queryRenderedFeatures(event.point,{layers});let feature=features.find((f:any)=>f.source==='recreation'||f.source==='trails');
  const base=features.find((f:any)=>f.source==='osm'&&f.sourceLayer==='poi');
  if(base)feature=map.__topoPoiDetails?.get('base:'+JSON.stringify([base.properties.class,base.properties.name,base.geometry.coordinates]))||feature;
  const tapped=features.find((f:any)=>f.source==='amenities');
  if(tapped)feature=map.__topoPoiDetails?.get(tapped.properties.osm_id)||map.__topoPoiDetails?.get(tapped.properties.group_id)||feature;
  if(feature?.source==='recreation')feature=map.__topoPoiDetails?.get(feature.properties.id)||feature;

  const clicked=features.find((f:any)=>f.source==='amenities');
  let site:any;
  if(clicked){
   const q=clicked.properties||{},gid=q.group_id||q.osm_id;
   const vector=map.getStyle().sources.amenities?.type==='vector';
   site=q.kind==='group'?clicked:map.querySourceFeatures('amenities',vector?{sourceLayer:'amenities'}:{}).find((f:any)=>f.properties?.kind==='group'&&f.properties.group_id===gid);
   if(!feature&&site){feature={...site,properties:{...site.properties,agency:'OpenStreetMap',details:'Facilities are listed for this site. Individual locations are shown only where mapped.',source_url:'https://www.openstreetmap.org/'+site.properties.osm_id}}}
  }
  if(!feature)return;const p={...feature.properties},body=document.createElement('div');
  if(site?.properties?.grid_image){const labels:Record<string,string>={'campsite':'Camping','drinking-water':'Drinking water','toilet':'Restrooms','picnic-site':'Picnic area','information':'Information'};
   p.site_facilities=String(site.properties.grid_image).replace(/^amenity-grid:/,'').split(',').map(icon=>labels[icon]||icon).join(', ');
  }body.style.cssText='font:13px/1.5 Arial,sans-serif;color:#234234;max-height:38vh;overflow:auto;padding:5px;max-width:270px';
  const title=document.createElement('strong');title.style.cssText='font-size:15px;display:block;margin-bottom:6px';title.textContent=clean(p.name||p.ref||p.route_ref||p.kind||'Map feature');body.appendChild(title);
  if(clicked?.properties?.facility_location==='site_only'){const note=document.createElement('p');note.textContent='Facility badges describe services at this site; their exact locations are not mapped.';body.appendChild(note)}
  if(p.display_group_count>1){const note=document.createElement('p');note.textContent=p.display_group_count+' nearby records share this name. Individual locations appear at close zoom.';body.appendChild(note)}
  const rows=[['Source',p.agency],['Feature',p.kind],['Elevation',p.elevation_ft!=null?p.elevation_ft+' ft (reported)':''],['GNIS ID',p.gnis_id],['GeoNames ID',p.geonames_id],['Area',p.unit],['Details',p.description||p.details],['Water',p.water],['Restrooms',p.restrooms],['Fee',p.fee],['Season',p.season||p.season_description||p.seasonal],['Site facilities',p.site_facilities],['Services',p.services],['Activities',p.activities],['Access',p.access_notes||p.access],['Vehicle designation',p.vehicle],['Restrictions',p.restrictions],['Surface',p.surface],['Phone',p.phone],['Accessibility',p.accessibility],['Stay limit',p.stay_limit]];
  for(const [key,value]of Object.entries(p))if(key.endsWith('_datesopen')||['passengervehicle','highclearancevehicle','motorcycle','atv','fourwd_gt50inches','e_bike_class1','e_bike_class2','e_bike_class3'].includes(key))rows.push([key.replace(/_/g,' '),value]);
  for(const [label,value]of rows){const text=clean(value);if(!text||text==='false'||text==='0'||text==='Unknown')continue;const row=document.createElement('p');row.style.margin='5px 0';row.textContent=label+': '+text.slice(0,700);body.appendChild(row)}
  try{const records=JSON.parse(p.source_records||'[]');if(records.length>1){const block=document.createElement('details'),summary=document.createElement('summary');summary.textContent=(p.display_group_count>1?'Nearby source records (':'Matched sources (')+records.length+')';block.appendChild(summary);for(const record of records){const item=document.createElement('p');item.textContent=clean(record.agency)+' · '+clean(record.name)+': '+Object.entries(record.details||{}).filter(([key])=>['water','restrooms','fee','season','phone','description','surface','trail_class','use','access','season_description','passengervehicle','motorcycle','atv','ref','elevation_ft','gnis_id','geonames_id','source_class','updated'].includes(key)||key.endsWith('_datesopen')).map(([key,value])=>key+': '+clean(value)).join(' · ');block.appendChild(item)}body.appendChild(block)}}catch{}
  const url=String(p.website||p.source_url||'');if(/^https?:\/\//i.test(url)){const link=document.createElement('a');link.href=url;link.textContent='Source and details';link.target='_blank';link.rel='noopener noreferrer';link.style.color='#286447';body.appendChild(link)}
  if(p.agency==='USFS'&&(feature.sourceLayer==='roads'||p.kind==='motorized_trail')){const note=document.createElement('p');note.textContent='MVUM designation; temporary closures may differ.';note.style.fontSize='11px';body.appendChild(note)}
  popup?.remove();popup=new Popup({maxWidth:'300px',closeOnClick:true,offset:12}).setLngLat(event.lngLat).setDOMContent(body).addTo(map);
 });
 map.on('remove',()=>popup?.remove());
}
