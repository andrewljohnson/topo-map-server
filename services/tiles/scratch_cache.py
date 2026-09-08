"""Bound replaceable raster/archive scratch files; preserve source databases and ledgers."""
import fcntl,os,threading,time
from pathlib import Path
PATTERNS=('national-dem/**/windows/*.npz','national_dem/**/windows/*.npz','national-landcover/**/rasters/**/*.tif','dem-samples/**/global/**/*.png','national-basemap/ranges/**/*.bin')
def prune(data,limit):
    candidates=[]
    for pattern in PATTERNS:
        for path in Path(data).glob(pattern):
            try:stat=path.stat();candidates.append((stat.st_mtime,path,stat.st_size))
            except FileNotFoundError:pass
    used=sum(size for _,_,size in candidates)
    for _,path,size in sorted(candidates):
        if used<=limit:break
        try:
            # DEM/NLCD writers take this same process lock. Archive .bin writes
            # use atomic replace; readers tolerate eviction before their open.
            with path.with_suffix('.lock').open('a+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                path.unlink(missing_ok=True);used-=size
        except (BlockingIOError,FileNotFoundError):pass
    return used

def start(data):
    limit=int(os.environ.get('TILE_SCRATCH_BYTES','0'))
    if not limit:return
    def maintain():
        while True:
            try:prune(data,limit)
            except Exception as exc:print('Scratch maintenance:',type(exc).__name__,flush=True)
            time.sleep(300)
    threading.Thread(target=maintain,name='scratch-cache',daemon=True).start()
