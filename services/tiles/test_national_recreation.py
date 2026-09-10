import json, tempfile, unittest, zipfile, csv, io
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
import national_recreation as r

def nps(kind='Trailhead',name='Test Trailhead',**props):
 return {'geometry':{'type':'Point','coordinates':[-119.79,37.947]},'properties':dict(POITYPE=kind,POINAME=name,FEATUREID='stable-id',PUBLICDISPLAY='Public Map Display',DATAACCESS='Unrestricted',**props)}

class RecreationTests(unittest.TestCase):
 def test_true_coordinates_and_stable_id(self):
  f=nps();result=r.normalize(f,'nps');self.assertEqual(result['geometry'],f['geometry']);self.assertEqual(result['properties']['id'],'nps:stable-id');self.assertEqual(result['properties']['kind'],'trailhead')
 def test_restricted_removed(self):
  self.assertIsNone(r.normalize(nps(OPENTOPUBLIC='No'),'nps'));self.assertIsNone(r.normalize(nps(ISEXTANT='No'),'nps'))
 def test_spring_does_not_imply_drinking_water(self):
  p=r.normalize(nps('Spring'),'nps')['properties'];self.assertNotEqual(p['poi_icon'],'drinking-water');self.assertEqual(p['poi_frame'],'circle')
 def test_services_remain_details_not_invented_points(self):
  f={'geometry':{'type':'Point','coordinates':[-120,39]},'properties':{'site_cn':'1','site_name':'Test Camp','site_type':'CAMPGROUND','water_availability':'Potable water','restroom_availability':'Vault'}}
  result=r.normalize(f,'usfs');self.assertEqual(result['properties']['restrooms'],'Vault');self.assertEqual(result['properties']['poi_icon'],'campsite')
 def test_public_name_changed_use(self):
  f={'geometry':{'type':'Point','coordinates':[-120,39]},'properties':{'site_cn':'1','site_name':'Old Campground','public_site_name':'Bayview Trailhead and Day-Use Area','site_type':'CAMPGROUND'}}
  self.assertEqual(r.normalize(f,'usfs')['properties']['kind'],'trailhead')
 def test_dedupe_close_same_name_only(self):
  a=r.normalize(nps(),'nps');b=json.loads(json.dumps(a));b['properties']['id']='ridb:2';b['properties']['phone']='555';self.assertEqual(len(r.dedupe([a,b])),1);self.assertEqual(a['properties']['phone'],'555');b['geometry']['coordinates'][0]+=.1;self.assertEqual(len(r.dedupe([a,b])),2)
 def test_ridb_identity_merges_different_representative_points(self):
  a=r.normalize(nps('Campground','Fallen Leaf Campground'),'nps');a['properties']['ridb_id']='232769'
  b=json.loads(json.dumps(a));b['geometry']['coordinates'][0]+=.005;b['properties']['id']='ridb:232769';b['properties']['phone']='555'
  self.assertEqual(len(r.dedupe([a,b])),1);self.assertEqual(a['properties']['phone'],'555')
 def test_osm_match_preserves_point_and_details(self):
  import national_amenities
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'cells/1/2.json';path.parent.mkdir(parents=True)
   f=r.normalize(nps('Campground','Camp A'),'nps');coords=f['geometry']['coordinates'][:]
   path.write_text(json.dumps({'features':[{'geometry':f['geometry'],'properties':{'name':'Camp A','icons':['campsite'],'osm_id':'way/1'}}]}))
   with patch.object(national_amenities,'CACHE',Path(directory)):
    result=r.mark_osm_duplicates([f],1,2)[0]
   self.assertTrue(result['properties']['osm_duplicate']);self.assertEqual(result['properties']['matched_osm_id'],'way/1');self.assertEqual(result['geometry']['coordinates'],coords)
 def test_halfmoon_matches_containing_site_not_anchor_radius(self):
  import national_amenities
  from copy import deepcopy
  fixture=json.loads((Path(__file__).parent/'fixtures/halfmoon-campground.json').read_text())
  for variant in ('actual','outside','other_name','other_kind','ambiguous'):
   with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'cells/173/406.json';path.parent.mkdir(parents=True)
    points=deepcopy(fixture['features'])
    f=r.normalize(fixture['agency'],'usfs');original=deepcopy(f['geometry'])
    if variant=='outside':f['geometry']['coordinates']=[-119.072,34.6502]
    if variant=='other_name':f['properties']['name']='Halfmoon Loop B'
    if variant=='other_kind':f['properties']['kind']='restroom'
    if variant=='ambiguous':
     extra=deepcopy(points[-1]);extra['properties']['osm_id']='way/other';points.append(extra)
    path.write_text(json.dumps({'features':points}))
    elements=deepcopy(fixture['elements'])
    if variant=='ambiguous':
     extra=deepcopy(elements[0]);extra['id']='other';elements.append(extra)
    path.with_suffix('.raw.json').write_text(json.dumps({'elements':elements}))
    with patch.object(national_amenities,'CACHE',Path(directory)):
     result=r.mark_osm_duplicates([f],173,406)[0]
    if variant=='actual':
     self.assertEqual(result['properties']['osm_match_reason'],'name_kind_site_polygon')
     self.assertEqual(result['properties']['matched_osm_id'],'way/1347238220')
     self.assertGreater(result['properties']['osm_match_distance_m'],120)
     self.assertEqual(result['geometry'],original)
     self.assertEqual(result['properties']['restrooms'],'Vault toilet')
    else:self.assertNotIn('matched_osm_id',result['properties'],variant)
 def test_encode_overzoom_details_not_dropped(self):
  f=nps('Restroom');lon,lat=f['geometry']['coordinates'];z=14;x=int((lon+180)/360*2**z);y=int((1-r.math.asinh(r.math.tan(r.math.radians(lat)))/r.math.pi)/2*2**z)
  with patch.object(r,'cell_data',return_value={'features':[f]}),patch.object(r,'ridb_features',return_value=[]),patch.object(r,'ranked_features',return_value=[]):
   data=mapbox_vector_tile.decode(r.render_tile(z,x,y))['recreation']['features'];self.assertEqual(len(data),1);self.assertEqual(data[0]['properties']['min_zoom'],15)
 def test_import_filters_invalid_and_permit_centroids(self):
  with tempfile.TemporaryDirectory() as directory:
   fields=['FacilityID','FacilityName','FacilityTypeDescription','FacilityLongitude','FacilityLatitude','Enabled'];out=io.StringIO();w=csv.DictWriter(out,fieldnames=fields);w.writeheader()
   for ident,kind,lon in [('a','Campground','-120'),('b','Permit','-120'),('c','Campground','0')]:w.writerow(dict(FacilityID=ident,FacilityName=ident,FacilityTypeDescription=kind,FacilityLongitude=lon,FacilityLatitude='39',Enabled='true'))
   archive=Path(directory)/'source.zip'
   with zipfile.ZipFile(archive,'w') as z:z.writestr('Facilities_API_v1.csv',out.getvalue())
   target=Path(directory)/'ridb.sqlite';self.assertEqual(r.import_ridb(archive,target),1)
   with patch.object(r,'RIDB_DB',target):self.assertEqual(len(r.ridb_features((-121,38,-119,40))),1)
if __name__=='__main__':unittest.main()
