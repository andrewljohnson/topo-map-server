"""Private S3 tile store, bounded local copies, conservative storage accounting.
A single serving instance owns the durable ledger. No client receives S3 URLs.
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from access_control import Denied

class ObjectCache:
    def __init__(self,data,bucket,prefix='tiles/v1',client=None,max_bytes=1_000_000_000_000,local_bytes=10_000_000_000):
        self.data=Path(data);self.bucket=bucket;self.prefix=prefix.strip('/')
        self.max_bytes=max_bytes;self.local_bytes=local_bytes;self.maintenance=threading.Lock();self.last_prune=0
        control=self.data/'control';control.mkdir(parents=True,exist_ok=True)
        identity=hashlib.sha256((bucket+'/'+prefix).encode()).hexdigest()[:16]
        self.database=control/f's3-{identity}.sqlite'
        if client is None:
            import boto3
            from botocore.config import Config
            client=boto3.client('s3',endpoint_url=os.environ.get('R2_ENDPOINT_URL') or os.environ.get('S3_ENDPOINT_URL') or None,region_name='auto' if os.environ.get('R2_BUCKET') else None,aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'),config=Config(connect_timeout=5,read_timeout=30,retries={'max_attempts':2}))
        self.client=client
        with self.db() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS objects(key TEXT PRIMARY KEY,size INTEGER,ready INTEGER DEFAULT 0);
              CREATE TABLE IF NOT EXISTS local(key TEXT PRIMARY KEY,path TEXT,size INTEGER,touched REAL);
              CREATE TABLE IF NOT EXISTS totals(id INTEGER PRIMARY KEY,bytes INTEGER);
              INSERT OR IGNORE INTO totals VALUES(1,0);
            """)
        marker=self.database.with_suffix('.reconciled')
        if not marker.exists():
            self.reconcile();marker.write_text('Do not remove without reconciling the bucket again.\n')
    def reconcile(self):
        for page in self.client.get_paginator('list_objects_v2').paginate(Bucket=self.bucket,Prefix=self.prefix+'/'):
            for item in page.get('Contents',[]):
                self.reserve(item['Key'],item['Size'])
                with self.db() as db:db.execute('UPDATE objects SET ready=1 WHERE key=?',(item['Key'],))
    def db(self):return sqlite3.connect(self.database,timeout=30)
    def key(self,dataset,z,x,y,source):
        return f'{self.prefix}/{dataset}/{z}/{x}/{y}.'+('png' if source=='dem' else 'pbf')
    def reserve(self,key,size):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT size FROM objects WHERE key=?',(key,)).fetchone()
            if old:
                if old[0]!=size:raise RuntimeError('Immutable tile changed size; publish a new dataset version')
                return
            used=db.execute('SELECT bytes FROM totals WHERE id=1').fetchone()[0]
            if used+size>self.max_bytes:raise Denied('S3 storage allowance reached')
            db.execute('INSERT INTO objects(key,size) VALUES(?,?)',(key,size))
            db.execute('UPDATE totals SET bytes=bytes+? WHERE id=1',(size,))
    def local_write(self,key,path,blob):
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as out:out.write(blob);name=out.name
        Path(name).replace(path)
        with self.db() as db:db.execute('INSERT OR REPLACE INTO local VALUES(?,?,?,?)',(key,str(path),len(blob),time.time()))
        self.prune()
    def local_get(self,key,path):
        with self.db() as db:known=db.execute('SELECT ready FROM objects WHERE key=?',(key,)).fetchone()
        if not known or not known[0]:return None
        try:blob=path.read_bytes()
        except FileNotFoundError:return None
        with self.db() as db:db.execute('INSERT OR REPLACE INTO local VALUES(?,?,?,?)',(key,str(path),len(blob),time.time()))
        return blob
    def get(self,key,path):
        blob=self.local_get(key,path)
        if blob is not None:return blob
        try:response=self.client.get_object(Bucket=self.bucket,Key=key)
        except Exception as exc:
            code=getattr(exc,'response',{}).get('Error',{}).get('Code')
            if code in ('NoSuchKey','404','NotFound'):return None
            # Permission/network failures must not trigger regeneration or writes.
            raise
        stream=response['Body']
        try:blob=stream.read()
        finally:stream.close()
        self.reserve(key,len(blob))
        with self.db() as db:db.execute('UPDATE objects SET ready=1 WHERE key=?',(key,))
        self.local_write(key,path,blob)
        return blob
    def put(self,key,path,blob,source):
        # Failed puts retain their reservation; retries cannot exceed the cap.
        self.reserve(key,len(blob))
        self.client.put_object(Bucket=self.bucket,Key=key,Body=blob,
            ContentType='image/png' if source=='dem' else 'application/vnd.mapbox-vector-tile',
            CacheControl='private, no-store',**({} if os.environ.get('R2_ENDPOINT_URL') or os.environ.get('S3_ENDPOINT_URL') else {'ServerSideEncryption':'AES256'}))
        with self.db() as db:db.execute('UPDATE objects SET ready=1 WHERE key=?',(key,))
        self.local_write(key,path,blob)
    def prune(self,force=False):
        if not force and time.monotonic()-self.last_prune<30:return
        if not self.maintenance.acquire(blocking=False):return
        try:
            self.last_prune=time.monotonic()
            with self.db() as db:
                used=db.execute('SELECT COALESCE(SUM(size),0) FROM local').fetchone()[0]
                for key,path,size in db.execute('SELECT key,path,size FROM local ORDER BY touched').fetchall():
                    if used<=self.local_bytes:break
                    Path(path).unlink(missing_ok=True)
                    db.execute('DELETE FROM local WHERE key=?',(key,));used-=size
        finally:self.maintenance.release()

_instance=None
def current():
    global _instance
    bucket=os.environ.get('R2_BUCKET') or os.environ.get('S3_TILE_BUCKET')
    if not bucket:return None
    if _instance is None:
        _instance=ObjectCache(os.environ['TILE_DATA_DIR'],bucket,os.environ.get('S3_TILE_PREFIX','tiles/v1'),
          max_bytes=int(os.environ.get('S3_MAX_BYTES','1000000000000')),
          local_bytes=int(os.environ.get('TILE_LOCAL_CACHE_BYTES','10000000000')))
    return _instance
