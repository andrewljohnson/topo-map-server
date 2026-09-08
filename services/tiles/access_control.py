"""Private credentials and durable, atomic application workload limits.
Every protected response goes through this ledger; tile CDN caching is disabled.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

actor = ContextVar('tile_actor', default='client')
class Denied(Exception):
    def __init__(self,message,status=429):super().__init__(message);self.status=status

DEFAULTS={'download_bytes':100_000_000_000,'requests':1_000_000,
          'generations':20_000,'warm_generations':25_000_000,
          'warm_download_bytes':2_000_000_000_000,'warm_requests':5_000_000,
          'requests_per_minute':1200,'warm_requests_per_minute':240,
          'concurrency':8,'warm_concurrency':1}

class Access:
    def __init__(self,data,config):
        self.path=Path(config); self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True)
        self.database=self.data/'usage.sqlite'
        self.lock=threading.Lock();self.active={'client':0,'warm':0}
        with self.db() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS usage(month TEXT,role TEXT,metric TEXT,value INTEGER,PRIMARY KEY(month,role,metric));
              CREATE TABLE IF NOT EXISTS rate(minute INTEGER,role TEXT,value INTEGER,PRIMARY KEY(minute,role));
            """)
    def db(self):return sqlite3.connect(self.database,timeout=30)
    def config(self):
        data=json.loads(self.path.read_text())
        limits={**DEFAULTS,**data.get('limits',{})}
        if any(type(v) is not int or v<0 for v in limits.values()):raise ValueError('Limits must be nonnegative integers')
        for c in data['credentials']:
            if c['role'] not in ('client','warm') or len(c['sha256'])!=64:raise ValueError('Invalid credential record')
        return data,limits
    def identify(self,header):
        if not header.startswith('Bearer ') or len(header)>512:raise Denied('Map access key required',401)
        digest=hashlib.sha256(header[7:].encode()).hexdigest()
        data,_=self.config()
        for credential in data.get('credentials',[]):
            if credential.get('enabled',True) and hmac.compare_digest(digest,credential['sha256']):
                role=credential['role']
                if role not in ('client','warm'):break
                return role
        raise Denied('Map access key is invalid or revoked',401)
    @staticmethod
    def month():return datetime.now(timezone.utc).strftime('%Y-%m')
    def charge(self,metric,amount,role=None):
        role=role or actor.get();_,limits=self.config()
        name=('warm_'+metric) if role=='warm' else metric
        limit=int(limits[name]);month=self.month()
        if amount<0:raise ValueError('Negative charge')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT value FROM usage WHERE month=? AND role=? AND metric=?',(month,role,metric)).fetchone()
            used=row[0] if row else 0
            if used+amount>limit:raise Denied(f'Monthly {metric.replace("_"," ")} allowance reached')
            db.execute('INSERT INTO usage VALUES(?,?,?,?) ON CONFLICT(month,role,metric) DO UPDATE SET value=value+excluded.value',(month,role,metric,amount))
    @contextmanager
    def request(self,header):
        role=self.identify(header);_,limits=self.config();prefix='warm_' if role=='warm' else ''
        with self.lock:
            if self.active[role]>=int(limits[prefix+'concurrency']):raise Denied('Too many simultaneous map requests')
            self.active[role]+=1
        token=actor.set(role)
        try:
            minute=int(time.time()//60)
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM rate WHERE minute<?',(minute-2,))
                row=db.execute('SELECT value FROM rate WHERE minute=? AND role=?',(minute,role)).fetchone()
                if row and row[0]>=int(limits[prefix+'requests_per_minute']):raise Denied('Map request rate limit reached')
                db.execute('INSERT INTO rate VALUES(?,?,1) ON CONFLICT(minute,role) DO UPDATE SET value=value+1',(minute,role))
            # Deny before doing any S3 reads or rendering when downloads are exhausted.
            self.charge('download_bytes',1)
            self.charge('requests',1)
            yield role
        finally:
            actor.reset(token)
            with self.lock:self.active[role]-=1
    def status(self):
        role=actor.get();_,limits=self.config();prefix='warm_' if role=='warm' else ''
        with self.db() as db:
            used=dict(db.execute('SELECT metric,value FROM usage WHERE month=? AND role=?',(self.month(),role)))
        return {'month':self.month(),'role':role,'used':used,'limits':{key:limits[prefix+key] for key in ('download_bytes','requests','generations')}}

_instance=None
def current():
    global _instance
    config=os.environ.get('TOPO_ACCESS_FILE')
    if not config:return None
    if _instance is None:
        _instance=Access(Path(os.environ['TILE_DATA_DIR'])/'control',config)
    return _instance

def generation():
    access=current()
    if access:access.charge('generations',1)
