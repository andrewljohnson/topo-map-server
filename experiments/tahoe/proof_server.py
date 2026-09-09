"""Local-only map proof exports for the diagnostic web build.

Serves a built web directory and accepts PNG + bounds exports under /__proof.
No cloud credentials or production endpoint are involved.
"""
import argparse,base64,json,re,time
from urllib.parse import urlsplit
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--port',type=int,default=3004)
 parser.add_argument('--tiles',type=Path,help='Optional local combined candidate root; serves only base/DEM XYZ files')
 parser.add_argument('--metadata',type=Path,help='Compatible public metadata to adapt for the local z12-only candidate')
 parser.add_argument('--candidate-id',help='Unique local candidate ID')
 args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 if any([args.tiles,args.metadata,args.candidate_id]) and not all([args.tiles,args.metadata,args.candidate_id]):parser.error('--tiles, --metadata and --candidate-id must be supplied together')
 if args.candidate_id and not re.fullmatch('[a-z0-9-]{1,80}',args.candidate_id):parser.error('Use a lowercase alphanumeric candidate ID')
 candidate=None
 if args.tiles:
  candidate=json.loads(args.metadata.read_text());prefix='/__candidate/'+args.candidate_id
  candidate.update(name='Topo · Local z12 candidate',publicAccess=True,releaseId=args.candidate_id,datasetId=args.candidate_id+'-base',minZoom=12,maxZoom=12,tileUrl=prefix+'/base/{z}/{x}/{y}.pbf',publication={'status':'local-candidate','detailRegion':'Local fixture only'})
  candidate.pop('batchUrl',None);candidate.pop('overviewMaxZoom',None)
  for name,tileset in candidate.get('tilesets',{}).items():
   if name not in ('osm','dem'):parser.error('Candidate metadata must use one combined base and one DEM')
   kind='base' if name=='osm' else 'dem';extension='pbf' if kind=='base' else 'png'
   tileset.update(datasetId=args.candidate_id+'-'+kind,minZoom=12,maxZoom=12,tileUrl=prefix+'/'+kind+'/{z}/{x}/{y}.'+extension)
   tileset.pop('batchUrl',None)
   if 'coverage' in tileset:tileset['coverage']={z:rows for z,rows in tileset['coverage'].items() if z=='12'}

 class Handler(SimpleHTTPRequestHandler):
  def __init__(self,*values,**kwargs):super().__init__(*values,directory=str(args.directory),**kwargs)
  def send_bytes(self,data,content_type,encoding=None):
   self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
   if encoding:self.send_header('Content-Encoding',encoding)
   self.end_headers();self.wfile.write(data)
  def do_GET(self):
   path=urlsplit(self.path).path
   if candidate and path=='/metadata':self.send_bytes(json.dumps(candidate).encode(),'application/json');return
   if path.startswith('/__candidate/'):
    match=re.fullmatch(r'/__candidate/([a-z0-9-]+)/(base|dem)/(12)/([0-9]+)/([0-9]+)\.(pbf|png)',path)
    if not candidate or not match or match[1]!=args.candidate_id or (match[2]=='base')!=(match[6]=='pbf') or not all(0<=int(v)<4096 for v in match.group(4,5)):self.send_error(404);return
    target=args.tiles/match[2]/match[3]/match[4]/(match[5]+'.'+match[6])
    if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(args.tiles.resolve()):self.send_error(404);return
    data=target.read_bytes();self.send_bytes(data,'application/vnd.mapbox-vector-tile' if match[2]=='base' else 'image/png','gzip' if data[:2]==b'\x1f\x8b' else None);return
   super().do_GET()
  def do_POST(self):
   if self.path!='/__proof':self.send_error(404);return
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=8000000:self.send_error(413);return
   try:
    request=json.loads(self.rfile.read(length));url=request['image'];prefix='data:image/png;base64,'
    if not url.startswith(prefix):raise ValueError('PNG required')
    image=base64.b64decode(url[len(prefix):],validate=True)
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('PNG required')
    label=re.sub(r'[^a-zA-Z0-9_-]','-',str(request.get('label','map')))[:70];name=str(time.time_ns())+'-'+label
    (args.output/(name+'.png')).write_bytes(image);(args.output/(name+'.json')).write_text(json.dumps(request['view'],indent=2))
    data=json.dumps({'saved':name+'.png'}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
   except (KeyError,ValueError,TypeError):self.send_error(400)
 ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__':main()
