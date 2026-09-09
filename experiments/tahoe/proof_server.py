"""Local-only map proof exports for the diagnostic web build.

Serves a built web directory and accepts PNG + bounds exports under /__proof.
No cloud credentials or production endpoint are involved.
"""
import argparse,base64,json,re,time
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--port',type=int,default=3004);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 class Handler(SimpleHTTPRequestHandler):
  def __init__(self,*values,**kwargs):super().__init__(*values,directory=str(args.directory),**kwargs)
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
