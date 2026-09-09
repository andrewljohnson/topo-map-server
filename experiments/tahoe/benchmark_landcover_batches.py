#!/usr/bin/env python3
"""Compare batched pixels with every retained fine-raster reference in the 400-parent fixture."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
import national_landcover as lc
import numpy as np
from rasterio.io import MemoryFile

def main():
    start=time.monotonic();checked=pixels=different=0;cells=set();reference=hashlib.sha256()
    for x in range(672*4,692*4):
        for y in range(1552*4,1572*4):
            path=lc.CACHE/'rasters/14'/str(x)/f'{y}.tif'
            if not path.exists(): continue
            data=path.read_bytes();reference.update(f'{x}/{y}:'.encode()+hashlib.sha256(data).digest())
            with MemoryFile(data) as mem,mem.open() as ds: old=ds.read(1)
            size=old.shape[0];values=lc.batch_values(str(lc.CACHE),x//16,y//16,size)
            new=values[y%16*size:(y%16+1)*size,x%16*size:(x%16+1)*size]
            count=int(np.count_nonzero(new!=old));different+=count
            assert count==0,(x,y,count)
            checked+=1;pixels+=old.size;cells.add((x//16,y//16))
    result=dict(seconds=time.monotonic()-start,referenceChildren=checked,comparedPixels=pixels,differentPixels=different,metatiles=len(cells),childrenPerRequest=256,referenceSha256=reference.hexdigest(),source='Annual_NLCD_LndCov_2024_CU_C1V1; ArcGIS raster 40')
    print(json.dumps(result),flush=True)
    (ROOT/'experiments/tahoe/results/landcover-batch-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
