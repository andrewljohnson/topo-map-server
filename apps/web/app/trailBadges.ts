/** Original route identifiers; not official agency/association insignia. */
export function installTrailBadges(map:any){
 const colors:Record<string,string>={PCT:'#296a91',AT:'#415d3c',CDT:'#8c553b',JMT:'#745b3e',TRT:'#775595',PNT:'#745b3e',AZT:'#745b3e',FT:'#745b3e',IAT:'#745b3e',NCT:'#745b3e',NET:'#745b3e',PHT:'#745b3e',NTT:'#745b3e'};
 function add(ref:string){const id='trail-'+ref;if(!colors[ref]||map.hasImage(id))return;const canvas=document.createElement('canvas');canvas.width=80;canvas.height=80;const ctx=canvas.getContext('2d',{willReadFrequently:true})!;
  ctx.beginPath();ctx.moveTo(20,3);ctx.lineTo(60,3);ctx.quadraticCurveTo(77,3,77,20);ctx.lineTo(77,60);ctx.quadraticCurveTo(77,77,60,77);ctx.lineTo(20,77);ctx.quadraticCurveTo(3,77,3,60);ctx.lineTo(3,20);ctx.quadraticCurveTo(3,3,20,3);ctx.closePath();ctx.fillStyle='#fffdf4';ctx.fill();ctx.strokeStyle=colors[ref];ctx.lineWidth=5;ctx.stroke();ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(16,27);ctx.lineTo(64,27);ctx.stroke();ctx.fillStyle=colors[ref];ctx.font='bold 27px Arial,sans-serif';ctx.textAlign='center';ctx.fillText(ref,40,56);map.addImage(id,ctx.getImageData(0,0,80,80),{pixelRatio:3});
 }
 map.on('styleimagemissing',(event:any)=>{if(event.id.startsWith('trail-'))add(event.id.slice(6))});
 map.on('styledata',()=>{if(map.isStyleLoaded())for(const ref of Object.keys(colors))add(ref)});
 if(map.isStyleLoaded())for(const ref of Object.keys(colors))add(ref);
}
