#!/usr/bin/env python3
"""Create separate client/operator keys without printing secrets or overwriting keys."""
import argparse,hashlib,json,os,secrets
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
a.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
names=('access.json','client.token','warm.token')
if any((a.directory/n).exists() for n in names):p.error('Credentials already exist; refusing to overwrite')
os.umask(0o077)
credentials=[]
for role in ('client','warm'):
    token=secrets.token_urlsafe(32)
    with (a.directory/(role+'.token')).open('x') as out:out.write(token+'\n')
    credentials.append({'id':role,'role':role,'sha256':hashlib.sha256(token.encode()).hexdigest(),'enabled':True})
limits={'download_bytes':100000000000,'requests':1000000,'generations':20000,'warm_generations':25000000,'warm_download_bytes':2000000000000,'warm_requests':5000000,'requests_per_minute':1200,'warm_requests_per_minute':240,'concurrency':8,'warm_concurrency':1}
with (a.directory/'access.json').open('x') as out:json.dump({'credentials':credentials,'limits':limits},out,indent=2)
print('Created access.json, client.token and warm.token in',a.directory)
print('Paste client.token into the app and website. Never distribute warm.token or AWS keys.')
