export const vectorSets=['osm','amenities','boundaries','waterways','landcover','trails','recreation'];
export function combineStyle(style:any,metadata:any){
 const base={...style.sources.osm,minzoom:metadata.minZoom??12,maxzoom:12,bounds:metadata.bounds};
 for(const layer of style.layers){if(vectorSets.includes(layer.source)&&layer['source-layer']){layer['source-layer']=layer.source+'__'+layer['source-layer'];layer.source='osm';}}
 for(const name of vectorSets)delete style.sources[name];style.sources.osm=base;
 return style;
}
// Existing POI matching/details operate on logical layer identities. The adapter
// translates queries only; MapLibre still owns one actual vector source.
export function logicalMap(map:any){
 const logical=(f:any)=>{if(f.source!=='osm'||!f.sourceLayer?.includes('__'))return f;const [source,...rest]=f.sourceLayer.split('__');return {...f,source,sourceLayer:rest.join('__')};};
 return new Proxy(map,{get(target,key){
  if(key==='getSource')return (source:string)=>target.getSource(vectorSets.includes(source)?'osm':source);
  if(key==='getStyle')return ()=>{const style=target.getStyle();return {...style,sources:{...style.sources,...Object.fromEntries(vectorSets.map(name=>[name,style.sources.osm]))},layers:style.layers.map((l:any)=>{if(l.source!=='osm'||!l['source-layer']?.includes('__'))return l;const [source,...rest]=l['source-layer'].split('__');return {...l,source,'source-layer':rest.join('__')};})};};
  if(key==='querySourceFeatures')return (source:string,options:any={})=>target.querySourceFeatures(vectorSets.includes(source)?'osm':source,vectorSets.includes(source)?{...options,sourceLayer:source+'__'+(options.sourceLayer||source)}:options).map(logical);
  if(key==='queryRenderedFeatures')return (...args:any[])=>target.queryRenderedFeatures(...args).map(logical);
  const value=Reflect.get(target,key);return typeof value==='function'?value.bind(target):value;
 }});
}
