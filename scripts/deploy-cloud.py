#!/usr/bin/env python3
"""Release committed main to the user's Cloudflare account; local-only secrets."""
import argparse,hashlib,io,json,os,re,subprocess,sys,tarfile,tempfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/tiles'))
from cloud_config import load

def run(args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode().strip()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
remote=os.environ.get('DEPLOY_REMOTE','origin')
if subprocess.run(['git','remote','get-url',remote],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
    run(['git','fetch','--no-tags',remote,'main'],cwd=ROOT);sha=git('rev-parse','FETCH_HEAD^{commit}')
else:sha=git('rev-parse','refs/heads/main^{commit}')
if a.dry_run:print('Would deploy committed main revision',sha,'to Cloudflare');sys.exit()
config=load();private=Path.home()/'.config/topo-map'
if not (private/'client.token').exists():run([sys.executable,str(ROOT/'scripts/create-map-credentials.py'),'--directory',str(private)])
token=(private/'client.token').read_text().strip()
with tempfile.TemporaryDirectory(prefix='topo-release-') as tmp:
    stage=Path(tmp)
    archive=subprocess.check_output(['git','archive',sha],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(stage,filter='data')
    cloud=stage/'services/cloud';web=stage/'apps/web'
    env={**os.environ,'CLOUDFLARE_ACCOUNT_ID':config['CLOUDFLARE_ACCOUNT_ID'],'TOPO_STATIC_EXPORT':'1','WRANGLER_SEND_METRICS':'false'}
    cfg=json.loads((cloud/'wrangler.json').read_text());cfg['r2_buckets'][0]['bucket_name']=config['R2_BUCKET'];(cloud/'wrangler.json').write_text(json.dumps(cfg))
    run(['node','--test',str(cloud/'worker.test.mjs')],env=env)
    run(['pnpm','install','--frozen-lockfile'],cwd=web,env=env)
    run(['pnpm','build'],cwd=web,env=env)
    command=[str(web/'node_modules/.bin/wrangler')]
    result=run(command+['deploy','--config',str(cloud/'wrangler.json')],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    print(result.stdout)
    # The Worker denies tile access until its verification hash is installed.
    secret=stage/'secrets.json';secret.write_text(json.dumps({'ACCESS_SHA256':hashlib.sha256(token.encode()).hexdigest(),'PUBLISH_SHA256':hashlib.sha256((private/'warm.token').read_text().strip().encode()).hexdigest()}));secret.chmod(0o600)
    run(command+['secret','bulk',str(secret),'--config',str(cloud/'wrangler.json')],env=env)
    urls=re.findall(r'https://[a-zA-Z0-9.-]+\.workers\.dev',result.stdout)
    if not urls:raise RuntimeError('No deployment URL returned')
    url=urls[-1]
    def check(path,expected,authenticated=False):
        import time
        options='header = "Authorization: Bearer '+token+'"\n' if authenticated else ''
        for attempt in range(4):
            result=subprocess.run(['curl','--silent','--show-error','--max-time','60','--output',os.devnull,'--write-out','%{http_code}','--config','-',url+path],input=options,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.returncode==0 and result.stdout==str(expected):return
            if attempt<3:time.sleep(3)
        raise RuntimeError('Live smoke check failed for '+path+'; HTTP '+result.stdout)
    for path in ('/','/metadata','/tiles/0/0/0.pbf'):check(path,200,True)
    check('/metadata',200 if cfg['vars'].get('PUBLIC_MAP')=='1' else 401)
    check('/operator/jobs',401)
    (private/'deployment.json').write_text(json.dumps({'url':url,'sha':sha},indent=2))
    print('Live:',url)
    print('Map access key file:',private/'client.token')
