import sys,time,json,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/tiles'))
import numpy as np
from rasterio.io import MemoryFile
from rasterio.errors import NotGeoreferencedWarning
from national_dem import decode_png
warnings.filterwarnings('ignore',category=NotGeoreferencedWarning)
inputs=[]
for path in sorted((ROOT/'services/tiles/data/experiments/tahoe-z12-v1/dem/12').glob('*/*.png')):
 values=decode_png(path.read_bytes());encoded=np.rint(np.clip(values+32768,0,65535.99609375)*256).astype('uint32')
 rgb=np.stack([(encoded>>16)&255,(encoded>>8)&255,encoded&255]).astype('uint8');inputs.append((values,rgb))
results=[]
for level in (6,3,1,6):
 start=time.monotonic();cpu=time.process_time();blobs=[]
 for values,rgb in inputs:
  with MemoryFile() as mem:
   with mem.open(driver='PNG',width=1024,height=1024,count=3,dtype='uint8',ZLEVEL=level) as dst:dst.write(rgb)
   blobs.append(mem.read())
 result=dict(zlevel=level,seconds=time.monotonic()-start,cpuSeconds=time.process_time()-cpu,bytes=sum(map(len,blobs)),tiles=len(blobs))
 for (values,_),blob in zip(inputs,blobs):np.testing.assert_array_equal(values,decode_png(blob))
 results.append(result);print(json.dumps(result),flush=True)
(ROOT/'experiments/tahoe/results/dem-compression.json').write_text(json.dumps(results,indent=2))
