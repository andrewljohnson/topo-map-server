/** Point-placed lake labels need explicit upright handling after map rotation.
 * MapLibre's text-keep-upright applies to line placement. Relayout only when a
 * rotation gesture ends, preserving smooth interaction and source coordinates.
 */
export function installLakeOrientation(map:any){
 const id='lake-labels';let base:any,last:number|null=null;
 const update=()=>{
  if(!base||!map.getLayer(id))return;
  const bearing=Math.round(map.getBearing()*1000)/1000;if(bearing===last)return;
  if(bearing===0&&last===null){last=0;return}
  const upright=(angle:any)=>['let','lake_angle',angle,['case',['<',['cos',['*',['-',['var','lake_angle'],bearing],Math.PI/180]],-1e-8],['+',['var','lake_angle'],180],['var','lake_angle']]];
  // Preserve the top-level zoom expression required by the style specification.
  const rotation=base[0]==='step'?base.map((value:any,i:number)=>i===2||i>=4&&i%2===0?upright(value):value):upright(base);
  map.setLayoutProperty(id,'text-rotate',bearing===0?base:rotation);last=bearing;
 };
 const reset=()=>{base=map.getStyle()?.layers?.find((l:any)=>l.id===id)?.layout?.['text-rotate'];last=null;update()};
 map.on('rotateend',update);map.on('style.load',reset);
 if(map.isStyleLoaded())reset();
 map.on('remove',()=>{map.off('rotateend',update);map.off('style.load',reset)});
}
