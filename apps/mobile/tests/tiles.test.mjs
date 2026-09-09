import test from 'node:test';import assert from 'node:assert/strict';import {cellTiles,lonX,latY} from '../src/tiles.mjs';
const meta={gridZoom:12,minZoom:8,maxZoom:14,bounds:[-79.49,37.88,-75.03,39.73]};
test('cell downloads ancestor tiles and all descendants, bounded to dataset',()=>{const cell=`${lonX(-76.6122,12)}/${latY(39.2904,12)}`;const tiles=cellTiles(cell,meta);assert.ok(tiles.length>10&&tiles.length<=25);assert.equal(new Set(tiles).size,tiles.length);assert.ok(tiles.some(t=>t.startsWith('8/')));for(const t of tiles){const[z,x,y]=t.split('/').map(Number);assert.ok(x>=lonX(meta.bounds[0],z)&&x<=lonX(meta.bounds[2],z));assert.ok(y>=latY(meta.bounds[3],z)&&y<=latY(meta.bounds[1],z));}});
test('invalid and out of bounds cells have no tiles',()=>{assert.deepEqual(cellTiles('bad',meta),[]);assert.deepEqual(cellTiles('0/0',meta),[]);});
test('combined pilot downloads only published base/DEM keys and clips its halo',()=>{
 const spec={gridZoom:12,minZoom:12,maxZoom:12,bounds:[-180,-85,180,85],halo:1,coverage:{12:[[680,1565,682,1567]]}};
 assert.equal(cellTiles('681/1566',spec).length,9);
 assert.equal(cellTiles('682/1566',spec).length,6);
 assert.deepEqual(cellTiles('690/1566',spec),[]);
 const base={...spec,halo:0,minZoom:0,coverage:{0:[[0,0,0,0]],12:[[681,1566,681,1566]]}};
 assert.deepEqual(cellTiles('681/1566',base),['0/0/0','12/681/1566']);
});
