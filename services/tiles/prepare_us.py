#!/usr/bin/env python3
"""Prepare a frozen US OSM extract, then resume the nationwide warmer."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

SOURCE='https://download.geofabrik.de/north-america/us-latest.osm.pbf'

def download(source,path,expected_md5):
    part=path.with_suffix('.part')
    offset=part.stat().st_size if part.exists() else 0
    headers={'User-Agent':'topo-map-server/1.0 (US bulk enrichment import)'}
    if offset:headers['Range']=f'bytes={offset}-'
    try:
        response=urlopen(Request(source,headers=headers),timeout=120)
    except HTTPError as exc:
        if exc.code!=416:raise
        # A completed .part left by interruption may already be the whole file.
        response=None
    if response is not None:
      with response:
          resumed=offset and response.status==206 and response.headers.get('Content-Range','').startswith(f'bytes {offset}-')
          if response.status==206 and not resumed:raise RuntimeError('Unexpected partial download response')
          with part.open('ab' if resumed else 'wb') as out:
              while chunk:=response.read(4*1024*1024):
                  if shutil.disk_usage(path.parent).free<50*10**9:raise RuntimeError('OSM download reached 50 GB disk reserve')
                  out.write(chunk)
    digest=hashlib.md5(usedforsecurity=False)
    with part.open('rb') as stream:
        while chunk:=stream.read(8*1024*1024):digest.update(chunk)
    if digest.hexdigest()!=expected_md5:
        part.unlink()
        raise RuntimeError('OSM extract changed during download; retrying a fresh snapshot')
    part.replace(path)

def prepare(data):
    from osm_bulk import import_pbf
    folder=data/'osm-source';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'us-enrichment.sqlite'
    if target.exists():return
    source=folder/'us-latest.osm.pbf'
    if not source.exists():
        with urlopen(SOURCE+'.md5',timeout=60) as response:checksum=response.read().decode().split()[0]
        if len(checksum)!=32 or any(c not in '0123456789abcdef' for c in checksum):raise ValueError('Invalid source checksum')
        download(SOURCE,source,checksum)
        (folder/'source.json').write_text(json.dumps({'url':SOURCE,'md5':checksum,'downloadedAt':time.time()}))
    # This entrypoint owns the unfinished staging files; the completed database
    # remains untouched until the new import succeeds atomically.
    target.with_suffix('.building').unlink(missing_ok=True)
    target.with_suffix('.building-journal').unlink(missing_ok=True)
    target.with_suffix('.nodes').unlink(missing_ok=True)
    import_pbf(source,target)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=Path('/data'))
    parser.add_argument('--api',default='http://tiles:3001')
    args=parser.parse_args()
    jobs=args.data/'jobs';jobs.mkdir(parents=True,exist_ok=True)
    lock=(jobs/'us-prepare.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX)
    while True:
        try:
            (jobs/'us-prepare-status.json').write_text(json.dumps({'status':'preparing-osm','updatedAt':time.time()}))
            prepare(args.data)
            (jobs/'us-prepare-status.json').write_text(json.dumps({'status':'complete','updatedAt':time.time()}))
            break
        except Exception as exc:
            (jobs/'us-prepare-status.json').write_text(json.dumps({'status':'retrying','error':str(exc),'updatedAt':time.time()}))
            print('US source preparation:',exc,flush=True);time.sleep(60)
    os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name('warm_us.py')),'--api',args.api,'--data',str(args.data)])
