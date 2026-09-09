#!/usr/bin/env python3
"""Serve only the local Tahoe experiment artifacts. Never generates on demand."""
import argparse,re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'services/tiles/data/experiments'
REGIONS={'tahoe','tahoe-10x','sierra-100x','sf-10x','smokies-10x','desert-10x','western-1000x'}
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  key=self.path.split('?')[0].strip('/')
  region='tahoe'
  if key.startswith('regions/'):
   parts=key.split('/',2)
   if len(parts)!=3 or parts[1] not in REGIONS:self.send_error(404);return
   _,region,key=parts
  if key in ('metadata','report','progress'):key+='.json'
  if not re.fullmatch(r'(metadata|report|progress)\.json|base/(?:10|11|12)/\d+/\d+\.pbf|dem/12/\d+/\d+\.png',key):self.send_error(404);return
  path=ROOT/(region+'-z12-v1')/key
  if not path.is_file():self.send_error(404);return
  data=path.read_bytes();self.send_response(200)
  self.send_header('Access-Control-Allow-Origin','*');self.send_header('Cache-Control','no-store')
  self.send_header('Content-Type','application/json' if key.endswith('.json') else 'image/png' if key.endswith('.png') else 'application/vnd.mapbox-vector-tile')
  if key.endswith('.pbf'):self.send_header('Content-Encoding','gzip')
  self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=3012);args=p.parse_args()
 print(f'Tahoe sample API on http://0.0.0.0:{args.port}',flush=True)
 ThreadingHTTPServer(('0.0.0.0',args.port),Handler).serve_forever()
