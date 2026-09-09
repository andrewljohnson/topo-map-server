#!/usr/bin/env python3
"""Verify current 400-parent outputs against the retained first full reference."""
import gzip,hashlib,json,sys,time,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
import numpy as np
from rasterio.errors import NotGeoreferencedWarning
from national_dem import decode_png
warnings.filterwarnings('ignore',category=NotGeoreferencedWarning)
def main():
    out=ROOT/'services/tiles/data/experiments/sierra-100x-z12-v1'
    reference=json.loads((ROOT/'experiments/tahoe/results/sierra-100x-resumed-first.json').read_text())
    current=json.loads((out/'report.json').read_text());start=time.monotonic()
    expected={row['key']:row['sha256'] for row in reference['parents']}
    actual={row['key']:row['sha256'] for row in current['parents']}
    assert actual==expected,'Parent content changed'
    for key,digest in actual.items():
        assert hashlib.sha256(gzip.decompress((out/'base'/f'{key}.pbf').read_bytes())).hexdigest()==digest,key
    originals=list((out/'reference-dem-level6').glob('12/*/*.png'))
    assert len(originals)==reference['dem']['tiles']==current['dem']['tiles']
    total=0
    for path in originals:
        key=path.relative_to(out/'reference-dem-level6')
        first=decode_png(path.read_bytes());second=decode_png((out/'dem'/key).read_bytes())
        np.testing.assert_array_equal(first,second,err_msg=str(key));total+=first.size
    result=dict(seconds=time.monotonic()-start,identicalVectorParents=len(actual),identicalDemParents=len(originals),identicalElevationSamples=total,comparedRunStartedAt=current['startedAt'],vectorBytes=sum(r['gzipBytes'] for r in current['parents']),demBytes=current['dem']['bytes'])
    print(json.dumps(result),flush=True)
    (ROOT/'experiments/tahoe/results/scale-full-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
