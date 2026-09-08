#!/usr/bin/env python3
"""Audit DEM coverage at all OSM populated-place label locations; does not fill missing data."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import numpy as np
from rasterio.transform import Affine
from rasterio.warp import transform
from shapely import from_wkb
from shapely.geometry import Point
import contours
import tile_service as tiles


def audit():
    with sqlite3.connect(tiles.CONTOURS_DB) as con:
        info=json.loads(con.execute("SELECT value FROM metadata WHERE key='info'").fetchone()[0])
    directory=None
    for build in sorted((tiles.DATA/'dem'/'checkpoints').glob('*/build.json')):
        candidate=json.loads(build.read_text())
        digests=[]
        for row,col,*_ in candidate['grid']['chunks']:
            with sqlite3.connect(build.parent/f'{row}-{col}.sqlite') as part:
                summary=json.loads(part.execute("SELECT value FROM metadata WHERE key='summary'").fetchone()[0])
                digests.append(summary['demSha256'])
        build_hash=hashlib.sha256(json.dumps(candidate,sort_keys=True).encode()).hexdigest()
        if hashlib.sha256((build_hash+''.join(digests)).encode()).hexdigest()==info['sourceHash']:
            directory=build.parent;fingerprint=candidate;break
    if directory is None:
        raise RuntimeError('No matching DEM checkpoints found for the published contour snapshot')
    grid=fingerprint['grid'];affine=Affine(*grid['transform']);size=fingerprint['chunk_size']
    coverage=from_wkb(bytes.fromhex(fingerprint['coverage']))
    @lru_cache(maxsize=8)
    def raster(key):
        return np.load(directory/(key+'.npy'),mmap_mode='r',allow_pickle=False)
    sampled=0;missing=[]
    with tiles.connect() as con:
        for name,wkb in con.execute("SELECT name,geometry FROM features WHERE kind='label'"):
            point=from_wkb(wkb)
            lon=point.x*360-180;lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*point.y))))
            xs,ys=transform('EPSG:4326','EPSG:4269',[lon],[lat]);x=xs[0];y=ys[0]
            if not coverage.covers(Point(x,y)):
                continue
            col=int(math.floor((x-affine.c)/affine.a));row=int(math.floor((y-affine.f)/affine.e))
            chunkrow=row//size*size;chunkcol=col//size*size;key=f'{chunkrow}-{chunkcol}'
            data=raster(key);localrow=row-max(0,chunkrow-2);localcol=col-max(0,chunkcol-2)
            sampled+=1
            if not np.isfinite(data[localrow,localcol]):
                missing.append({'name':name,'longitude':lon,'latitude':lat})
    report={'sourceHash':info['sourceHash'],'validPixels':info['validPixels'],'coveragePixels':info['coveragePixels'],'validCoveragePercent':round(info['validPixels']/info['coveragePixels']*100,4),'populatedPlacesChecked':sampled,'placesMissingDem':missing,'scope':'Checks every OSM populated-place label in the extract; not an exhaustive pixel-level land/water classification. Missing DEM pixels are not filled.'}
    output=tiles.DATA/'dem'/'coverage-audit.json';output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    audit()
