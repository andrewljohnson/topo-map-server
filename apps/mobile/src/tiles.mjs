export function lonX(lon,z){return Math.floor((lon+180)/360*2**z)}
export function latY(lat,z){const r=Math.max(-85.0511,Math.min(85.0511,lat))*Math.PI/180;return Math.floor((1-Math.asinh(Math.tan(r))/Math.PI)/2*2**z)}
export function cellTiles(cell,meta){
 const [gx,gy]=cell.split('/').map(Number),g=meta.gridZoom;
 if(!Number.isInteger(gx)||!Number.isInteger(gy)||gx<0||gy<0||gx>=2**g||gy>=2**g) return [];
 const result=new Set(),halo=meta.halo||0;
 for(let z=meta.minZoom;z<=Math.min(meta.maxZoom,14);z++){
  const factor=2**(z-g);
  const x0=Math.max(Math.floor(gx*factor),lonX(meta.bounds[0],z)),x1=Math.min(Math.ceil((gx+1)*factor)-1,lonX(meta.bounds[2],z));
  const y0=Math.max(Math.floor(gy*factor),latY(meta.bounds[3],z)),y1=Math.min(Math.ceil((gy+1)*factor)-1,latY(meta.bounds[1],z));
  if(x0>x1||y0>y1)continue;
  for(let x=x0-halo;x<=x1+halo;x++)for(let y=Math.max(0,y0-halo);y<=Math.min(2**z-1,y1+halo);y++)result.add(`${z}/${(x+2**z)%2**z}/${y}`);
 }
 return [...result];
}
