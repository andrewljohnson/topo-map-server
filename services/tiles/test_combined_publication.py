import gzip,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
from PIL import Image
from publish_combined import plan,metadata,rectangles,validate_combined
from publish_cloud import Publisher
class Missing(Exception):response={'Error':{'Code':'NoSuchKey'}}
class Store:
 def __init__(self):self.objects={};self.puts=0;self.corrupt=False
 def put_object(self,Key,Body,**kw):self.objects[Key]=(Body,kw);self.puts+=1
 def head_object(self,Key,**kw):
  if Key not in self.objects:raise Missing()
  body,meta=self.objects[Key];return {'ContentLength':len(body),'Metadata':meta['Metadata'],'ContentEncoding':meta.get('ContentEncoding')}
 def get_object(self,Key,**kw):return {'Body':io.BytesIO(b'bad' if self.corrupt else self.objects[Key][0])}
class CombinedPublicationTests(unittest.TestCase):
 def test_pilot_contract_only_two_tilesets_exact_coverage_and_halo(self):
  p=plan('pilot');m=metadata('test',p)
  self.assertEqual(len(p['parents']),80);self.assertEqual(len(p['dem']),140)
  self.assertEqual(set(m['tilesets']),{'osm','dem'});self.assertEqual(m['tilesets']['dem']['tileSize'],1024)
  self.assertEqual(m['tilesets']['osm']['maxZoom'],12);self.assertEqual(m['tilesets']['dem']['minZoom'],12)
  for kind,keys in [('osm',[(12,x,y) for x,y in p['parents']]),('dem',[(12,x,y) for x,y in p['dem']])]:
   rects=m['tilesets'][kind]['coverage']['12'];actual={(12,x,y) for a,b,c,d in rects for x in range(a,c+1) for y in range(b,d+1)}
   self.assertEqual(actual,set(keys))
 def test_validation_accepts_1024_dem_and_rejects_wrong_size_and_layers(self):
  def png(size):
   out=io.BytesIO();Image.new('RGB',(size,size)).save(out,format='PNG');return out.getvalue()
  validate_combined(png(1024),'dem')
  with self.assertRaises(ValueError):validate_combined(png(512),'dem')
  valid=mapbox_vector_tile.encode({'name':'osm__land','features':[]});validate_combined(gzip.compress(valid),'osm')
  with self.assertRaises(ValueError):validate_combined(gzip.compress(mapbox_vector_tile.encode({'name':'land','features':[]})),'osm')
 def test_resume_after_upload_before_verified_checkpoint_and_reject_corruption(self):
  store=Store()
  with tempfile.TemporaryDirectory() as d,patch('publish_cloud.client',return_value=store):
   publisher=Publisher({'R2_BUCKET':'test'},Path(d));blob=gzip.compress(b'tile');key='release/base/12/1/1.pbf'
   store.corrupt=True
   with self.assertRaisesRegex(ValueError,'checksum'):publisher.put(key,blob,'vector',content_encoding='gzip',verify_body=True)
   with publisher.db() as db:self.assertEqual(db.execute('SELECT done FROM uploads').fetchone(),(0,))
   store.corrupt=False;publisher.put(key,blob,'vector',content_encoding='gzip',verify_body=True)
   self.assertEqual(store.puts,1,'resume validates existing object without re-upload')
   with publisher.db() as db:self.assertEqual(db.execute('SELECT done FROM uploads').fetchone(),(1,))
   publisher.put(key,blob,'vector',content_encoding='gzip',verify_body=True);self.assertEqual(store.puts,1)
   with self.assertRaises(ValueError):publisher.put(key,b'changed','vector',verify_body=True)
if __name__=='__main__':unittest.main()
