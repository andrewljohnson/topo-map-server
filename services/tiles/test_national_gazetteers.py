import csv, io, json, sqlite3, tempfile, unittest, zipfile
from pathlib import Path
import national_gazetteers as g

def gnis_row(ident='1',name='Mount Example',kind='Summit',lon='-120',lat='39'):
 return {'feature_id':ident,'feature_name':name,'feature_class':kind,'prim_long_dec':lon,'prim_lat_dec':lat,'state_name':'California'}
def geo_row(ident='2',name='Mt. Example',code='T.PK',lon='-120.0001',lat='39',elevation=''):
 return [ident,name,name,'Example Mountain',lat,lon,*code.split('.'),'US','','CA','','','','0',elevation,'999','America/Los_Angeles','2026-09-06']

class GazetteerTests(unittest.TestCase):
 def test_kind_and_coordinate_filters(self):
  for f in [gnis_row(kind='Lake'),gnis_row(name='Old Peak (historical)'),gnis_row(lon='nan'),gnis_row(lat='0')]:self.assertIsNone(g.gnis(f))
  for code in ['R.TRL','S.CMP','S.CMPL','S.ARCH','T.PKS']:self.assertIsNone(g.geonames(geo_row(code=code)))
 def test_spring_never_implies_drinking_water(self):
  f=g.geonames(geo_row(code='H.SPNT'));self.assertEqual(f['properties']['kind'],'spring');self.assertEqual(f['properties']['spring_type'],'hot');self.assertNotEqual(f['properties']['poi_icon'],'drinking-water')
 def test_dem_value_is_not_reported_as_spot_height(self):
  self.assertNotIn('elevation_ft',g.geonames(geo_row())['properties'])
  self.assertEqual(g.geonames(geo_row(elevation='1000'))['properties']['elevation_ft'],3281)
 def test_both_sides_of_alaska_dateline(self):
  for lon in ('-179','179'):
   self.assertIsNotNone(g.gnis(gnis_row(lon=lon,lat='52')))
 def test_import_merges_but_retains_unique_features_and_source_records(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);a=tmp/'gnis.zip';b=tmp/'geo.zip';dest=tmp/'db.sqlite'
   buf=io.StringIO();rows=[gnis_row(),gnis_row('3','Remote Peak',lon='-121')];w=csv.DictWriter(buf,fieldnames=rows[0].keys(),delimiter='|');w.writeheader();w.writerows(rows)
   with zipfile.ZipFile(a,'w') as z:z.writestr('Text/DomesticNames_National.txt',buf.getvalue())
   with zipfile.ZipFile(b,'w') as z:z.writestr('US.txt','\t'.join(geo_row(elevation='1000'))+'\n'+'\t'.join(geo_row('4','New Spring',code='H.SPNG',lon='-122'))+'\n')
   stats=g.import_archives(a,b,dest);self.assertEqual(stats['features'],3);self.assertEqual(stats['counts']['merged'],1)
   f=g.features((-120.1,38.9,-119.9,39.1),dest)[0];p=f['properties'];self.assertEqual(p['gnis_id'],'1');self.assertEqual(p['geonames_id'],'2');self.assertEqual(p['agency'],'USGS GNIS');self.assertEqual(p['source_count'],2)
   self.assertEqual(f['geometry']['coordinates'],[-120,39]);self.assertEqual(p['elevation_ft'],3281)
   self.assertEqual(len(json.loads(p['source_records'])),2)
   previous=dest.read_bytes()
   with zipfile.ZipFile(b,'w') as z:z.writestr('US.txt','bad schema')
   with self.assertRaises(ValueError):g.import_archives(a,b,dest)
   self.assertEqual(dest.read_bytes(),previous)
 def test_missing_index_is_an_error_not_empty_coverage(self):
  with self.assertRaises(RuntimeError):g.features((-120,38,-119,39),'/missing-gazetteer-file.sqlite')
