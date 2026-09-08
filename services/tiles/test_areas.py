import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import areas

class AreaTests(unittest.TestCase):
    def test_catalog_and_label_points_share_bounds_and_classification(self):
        features=[]
        for kind,name in [('park','Yosemite National Park'),('forest','Eldorado National Forest'),('wilderness','Desolation Wilderness')]:
            features.append({'type':'Feature','properties':{'id':kind,'name':name,'kind':kind,'bounds':[-120,38,-119,39],'center':[-119.5,38.5]},'geometry':{'type':'Polygon','coordinates':[[[-120,38],[-119,38],[-119,39],[-120,39],[-120,38]]]}})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'areas.json';path.write_text(json.dumps({'type':'FeatureCollection','features':features}))
            areas.area_data.cache_clear();areas.area_bytes.cache_clear()
            with patch.object(areas,'AREA_FILE',path):
                catalog,geo=areas.area_data()
                self.assertEqual(len(catalog),3);self.assertEqual(len(geo['features']),6)
                labels=[f for f in geo['features'] if f['geometry']['type']=='Point']
                self.assertEqual([f['properties']['min_zoom'] for f in labels],[3,5,7])
                self.assertEqual(labels[0]['geometry']['coordinates'],labels[0]['properties']['label_center'])
                self.assertEqual(catalog[0]['center'],[-119.5,38.5])
                self.assertEqual(json.loads(areas.area_bytes()),catalog)
                self.assertEqual(json.loads(areas.area_bytes(True)),geo)
            areas.area_data.cache_clear();areas.area_bytes.cache_clear()


class LabelCenterTests(unittest.TestCase):
    def test_concavity_holes_and_disconnected_islands_keep_labels_inside(self):
        from area_labels import label_center
        from shapely.geometry import Polygon, MultiPolygon, Point, mapping
        concave=Polygon([(0,0),(4,0),(4,1),(1,1),(1,3),(4,3),(4,4),(0,4)])
        hole=Polygon([(0,0),(4,0),(4,4),(0,4)],holes=[[(1,1),(3,1),(3,3),(1,3)]])
        main=Polygon([(0,0),(2,0),(2,2),(0,2)])
        distant=Polygon([(50,0),(51,0),(51,1),(50,1)])
        for g in [concave,hole,MultiPolygon([main,distant])]:
            point,method=label_center(mapping(g))
            self.assertTrue(g.covers(Point(point)))
            if g.geom_type=='MultiPolygon':self.assertTrue(main.covers(Point(point)))
            else:self.assertEqual(method,'interior_visual_center')

    def test_all_nationwide_anchors_inside_and_yosemite_uses_visual_center(self):
        from area_labels import label_center
        from shapely.geometry import shape,Point
        data=json.loads(areas.AREA_FILE.read_text())
        self.assertGreater(len(data['features']),1000)
        for feature in data['features']:
            p=feature['properties'];g=shape(feature['geometry'])
            self.assertTrue(g.covers(Point(p['label_center'])),p['name'])
            if p['name']=='Yosemite National Park':
                self.assertEqual(p['label_method'],'mercator_centroid')
                self.assertAlmostEqual(p['label_center'][0],-119.557,delta=.005)
            if p['name']=='Yosemite Wilderness':
                self.assertLess(p['label_center'][0],-119.50,'label must not stay near the eastern edge')
