// Canvas-only assets: no sprites, remote images, or font dependencies.
export function installShieldImages(map: import('maplibre-gl').Map) {
  const identifiers = ['shield-interstate', 'shield-us', 'shield-state', 'shield-county', 'shield-california'];
  function add(id: string) {
    if (!identifiers.includes(id) || map.hasImage(id)) return;
    const canvas = document.createElement('canvas');
    canvas.width = 64; canvas.height = 64;
    const ctx = canvas.getContext('2d')!;
    if (!ctx) throw new Error('Canvas is required for highway shields');
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    function shape() {
      ctx.beginPath();
      if (id === 'shield-interstate') {
        ctx.moveTo(7,5);ctx.quadraticCurveTo(32,1,57,5);ctx.lineTo(57,31);
        ctx.bezierCurveTo(57,45,46,55,32,61);ctx.bezierCurveTo(18,55,7,45,7,31);ctx.closePath();
      } else if (id === 'shield-us') {
        ctx.moveTo(6,13);ctx.quadraticCurveTo(12,11,16,5);ctx.quadraticCurveTo(25,10,32,5);
        ctx.quadraticCurveTo(39,10,48,5);ctx.quadraticCurveTo(52,11,58,13);
        ctx.bezierCurveTo(53,22,55,30,57,38);ctx.bezierCurveTo(55,49,45,51,32,60);
        ctx.bezierCurveTo(19,51,9,49,7,38);ctx.bezierCurveTo(9,30,11,22,6,13);ctx.closePath();
      } else if (id === 'shield-county') {
        ctx.moveTo(32,4);ctx.lineTo(58,20);ctx.lineTo(58,57);ctx.lineTo(6,57);ctx.lineTo(6,20);ctx.closePath();
      } else if (id === 'shield-california') {
        ctx.moveTo(9,7);ctx.quadraticCurveTo(32,1,55,7);ctx.lineTo(55,33);
        ctx.bezierCurveTo(55,46,44,54,32,60);ctx.bezierCurveTo(20,54,9,46,9,33);ctx.closePath();
      } else {
        ctx.moveTo(13,9);ctx.lineTo(51,9);ctx.quadraticCurveTo(58,9,58,16);
        ctx.lineTo(58,48);ctx.quadraticCurveTo(58,55,51,55);ctx.lineTo(13,55);
        ctx.quadraticCurveTo(6,55,6,48);ctx.lineTo(6,16);ctx.quadraticCurveTo(6,9,13,9);ctx.closePath();
      }
    }
    shape();ctx.fillStyle=id==='shield-interstate'?'#285588':id==='shield-county'?'#2d5278':id==='shield-california'?'#286343':'#fffdf6';ctx.fill();
    if (id==='shield-interstate') {
      ctx.save();shape();ctx.clip();ctx.fillStyle='#b9433b';ctx.fillRect(0,0,64,19);
      ctx.fillStyle='#fffdf6';ctx.fillRect(0,19,64,2);ctx.restore();
    }
    shape();ctx.strokeStyle=id==='shield-county'?'#f3d474':(id==='shield-interstate'||id==='shield-california')?'#fffdf6':'#35352f';ctx.lineWidth=2.5;ctx.stroke();
    if(id==='shield-interstate'){shape();ctx.strokeStyle='#404b56';ctx.lineWidth=.8;ctx.stroke();}
    const content=id==='shield-interstate'?[14,25,50,43]:id==='shield-county'?[13,23,51,47]:[14,18,50,43];
    map.addImage(id,ctx.getImageData(0,0,64,64),{pixelRatio:4,content:content as [number,number,number,number],stretchX:[[25,39]],stretchY:[[28,38]]});
  }
  map.on('styleimagemissing',event=>add(event.id));
  map.on('style.load',()=>identifiers.forEach(add));
  if (map.isStyleLoaded()) identifiers.forEach(add);
}
