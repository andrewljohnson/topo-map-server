export function logicalMap(map:any){
 const vectorSets=['osm','amenities','boundaries','waterways','landcover','trails','recreation'];
 const logical=(f:any)=>{if(f.source!=='osm'||!f.sourceLayer?.includes('__'))return f;const [source,...rest]=f.sourceLayer.split('__');return {...f,source,sourceLayer:rest.join('__')};};
 return new Proxy(map,{get(target,key){
  if(key==='getSource')return (source:string)=>target.getSource(vectorSets.includes(source)?'osm':source)||target.getSource(source+'-region-0');
  if(key==='getStyle')return ()=>{const style=target.getStyle();return {...style,sources:{...style.sources,...Object.fromEntries(vectorSets.map(name=>[name,style.sources.osm]))},layers:style.layers.map((l:any)=>{if(l.source!=='osm'||!l['source-layer']?.includes('__'))return l;const [source,...rest]=l['source-layer'].split('__');return {...l,source,'source-layer':rest.join('__')};})};};
  if(key==='querySourceFeatures')return (source:string,options:any={})=>target.querySourceFeatures(vectorSets.includes(source)?'osm':source,vectorSets.includes(source)?{...options,sourceLayer:source+'__'+(options.sourceLayer||source)}:options).map(logical);
  if(key==='queryRenderedFeatures')return (...args:any[])=>target.queryRenderedFeatures(...args).map(logical);
  const value=Reflect.get(target,key);return typeof value==='function'?value.bind(target):value;
 }});
}
