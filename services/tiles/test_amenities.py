import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).parent / 'regions' / 'build_amenities.py'
spec = importlib.util.spec_from_file_location('build_amenities', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def node(identifier,x,y,**tags):
    return {'type':'node','id':identifier,'lon':x,'lat':y,'tags':tags}


def site():
    return {'type':'way','id':1,'tags':{'tourism':'camp_site','name':'Camp','drinking_water':'yes'},'geometry':[{'lon':x,'lat':y} for x,y in [(0,0),(.001,0),(.001,.001),(0,.001),(0,0)]]}


class AmenityGroupingTests(unittest.TestCase):
    def test_polygon_membership_and_facility_tags(self):
        result=module.build({'elements':[site(),node(2,.0002,.0002,amenity='toilets'),node(3,.0003,.0003,amenity='toilets'),node(4,.0011,.0003,amenity='toilets')]})['features']
        group=next(f for f in result if f['properties']['kind']=='group')
        self.assertEqual(group['properties']['icons'],['campsite','drinking-water','toilet'])
        self.assertEqual(group['properties']['member_count'],3)
        outside=next(f for f in result if f['properties'].get('osm_id')=='node/4')
        self.assertEqual(outside['properties']['group_id'],'')
        self.assertEqual(outside['geometry']['coordinates'],[.0011,.0003])
        # A site tag cannot invent an exact water point.
        self.assertFalse(any(f['properties'].get('poi_icon')=='drinking-water' for f in result))
        self.assertTrue(module.geometry(site()).covers(module.Point(*group['geometry']['coordinates'])))

    def test_site_only_bathroom_remains_badge_after_split(self):
        raw={'elements':[node(1,-91.1,48,tourism='camp_site',name='Boundary Waters camp',toilets='yes')]}
        result=module.build(raw)['features']
        member=next(f for f in result if f['properties']['kind']=='amenity')
        self.assertEqual(member['properties']['grid_image'],'amenity-grid:campsite,toilet')
        self.assertEqual(member['properties']['facility_location'],'site_only')
        self.assertEqual(member['geometry']['coordinates'],[-91.1,48])
        self.assertFalse(any(f['properties'].get('poi_icon')=='toilet' for f in result))
        raw['elements'].append(node(2,-91.1001,48,amenity='toilets'))
        result=module.build(raw)['features']
        members=[f for f in result if f['properties']['kind']=='amenity']
        self.assertTrue(any(f['properties'].get('poi_icon')=='toilet' for f in members))
        self.assertFalse(any('grid_image' in f['properties'] for f in members),'known facility splits to mapped location')

    def test_ambiguous_proximity_keeps_real_point(self):
        result=module.build({'elements':[node(1,0,0,tourism='picnic_site',name='A'),node(2,.0005,0,tourism='picnic_site',name='B'),node(3,.00025,0,amenity='toilets')]})['features']
        point=next(f for f in result if f['properties'].get('osm_id')=='node/3')
        self.assertEqual(point['properties']['group_id'],'')

    def test_beach_does_not_imply_swimming(self):
        self.assertEqual(module.categories({'natural':'beach'}),[])
        self.assertEqual(module.categories({'leisure':'swimming_area'}),['swimming'])

    def test_bundled_data_reproducible_and_identical(self):
        mobile=module.ROOT/'apps/mobile/src/amenity-data.json'
        web=module.ROOT/'apps/web/app/amenity-data.json'
        self.assertEqual(mobile.read_bytes(),web.read_bytes())
        actual=json.loads(mobile.read_text())
        self.assertEqual(actual,module.build(json.loads(module.SOURCE.read_text())))
        groups={f['properties']['group_id'] for f in actual['features'] if f['properties']['kind']=='group'}
        self.assertGreaterEqual(len(groups),10)
        for f in actual['features']:
            p=f['properties']
            if p['kind']=='group':
                self.assertLessEqual(len(p['icons']),12)
                self.assertEqual(len(p['icons']),len(set(p['icons'])))
            elif p['group_id']:
                self.assertIn(p['group_id'],groups)
                self.assertEqual(p['min_zoom'],15)
            else:self.assertEqual(p['min_zoom'],14)

if __name__=='__main__':unittest.main()
