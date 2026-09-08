"""Read local R2 configuration without executing shell code or exposing secrets."""
import os,shlex
from pathlib import Path

def load(path=None):
    path=Path(path or os.environ.get('TOPO_CLOUD_CONFIG',Path.home()/'.config/topo-map/cloudflare.env'))
    if path.stat().st_mode&0o077:raise ValueError('Cloud credentials must have permissions 600')
    result={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        name,value=line.removeprefix('export ').split('=',1)
        parsed=shlex.split(value,comments=True);result[name.strip()]=parsed[0] if parsed else ''
    for key in ('CLOUDFLARE_ACCOUNT_ID','R2_BUCKET','R2_ENDPOINT_URL','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY'):
        if not result.get(key):raise ValueError('Missing '+key)
    expected='https://'+result['CLOUDFLARE_ACCOUNT_ID']+'.r2.cloudflarestorage.com'
    if result['R2_ENDPOINT_URL'].rstrip('/')!=expected:raise ValueError('R2 endpoint must match the configured account')
    return result

def client(config):
    import boto3
    from botocore.config import Config
    return boto3.client('s3',endpoint_url=config['R2_ENDPOINT_URL'],region_name='auto',aws_access_key_id=config['R2_ACCESS_KEY_ID'],aws_secret_access_key=config['R2_SECRET_ACCESS_KEY'],config=Config(max_pool_connections=32,connect_timeout=10,read_timeout=60,retries={'max_attempts':3},request_checksum_calculation='when_required',response_checksum_validation='when_required'))
