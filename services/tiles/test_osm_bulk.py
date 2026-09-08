import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from osm_bulk import import_pbf, query_local
from national_amenities import query_box
from regions.build_amenities import geometry

OSM="""<osm version="0.6" generator="test">
<node id="1" lat="37.7" lon="-119.5" version="1"><tag k="amenity" v="toilets"/></node>
<node id="2" lat="37.71" lon="-119.5" version="1"/>
<node id="3" lat="37.71" lon="-119.49" version="1"/>
<node id="4" lat="37.7" lon="-119.49" version="1"/>
<way id="10" version="1"><nd ref="1"/><nd ref="2"/><tag k="waterway" v="stream"/><tag k="seasonal" v="yes"/></way>
<way id="20" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="tourism" v="camp_site"/></way>
</osm>"""
class BulkTests(unittest.TestCase):
    def test_real_import_preserves_geometry_tags_and_spatial_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'test.osm';source.write_text(OSM)
            target=root/'index.sqlite';import_pbf(source,target)
            data=query_local(query_box([-119.6,37.6,-119.4,37.8]),target)
            self.assertEqual({(e['type'],e['id']) for e in data['elements']},{('node',1),('way',20)})
            self.assertTrue(all(not geometry(e).is_empty for e in data['elements']))
            self.assertEqual(query_local(query_box([0,0,1,1]),target)['elements'],[])
            tags=query_local('[out:json];way(id:10,99);out tags;',target)['elements']
            self.assertEqual(len(tags),1)
            self.assertEqual(tags[0]['tags']['seasonal'],'yes')
            self.assertTrue(data['_endpoint'].startswith('local-osm-pbf:'))
    def test_production_requires_bulk_without_querying_public_server(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OSM_REQUIRE_BULK':'1'}):
            with self.assertRaises(RuntimeError):query_local('anything',Path(tmp)/'absent')
    def test_local_development_can_keep_existing_overpass_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OSM_REQUIRE_BULK':'0'}):
            self.assertIsNone(query_local('anything',Path(tmp)/'absent'))
if __name__=='__main__':unittest.main()

class FilterEquivalenceTests(unittest.TestCase):
    def test_native_empty_tag_filter_preserves_nodes_ways_and_multipolygons(self):
        import sqlite3
        # Relation geometry must retain its untagged outer way and node members.
        extra='''<way id="30" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
<relation id="40" version="1"><member type="way" ref="30" role="outer"/><tag k="type" v="multipolygon"/><tag k="tourism" v="camp_site"/></relation>'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.osm';source.write_text(OSM.replace('</osm>',extra+'</osm>'))
            results=[]
            for filtered in [False,True]:
                target=root/f'{filtered}.sqlite';import_pbf(source,target,filter_empty=filtered)
                with sqlite3.connect(target) as db:
                    results.append({table:db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall() for table in ['features','extents','waterways','metadata']})
            self.assertEqual(results[0],results[1])
            self.assertTrue(any(row[0]=='relation/40' for row in results[1]['features']))

class InvalidAreaTests(unittest.TestCase):
    def test_invalid_area_preserves_way_and_records_rejection(self):
        import osmium
        import sqlite3
        real=osmium.geom.GeoJSONFactory()
        class Factory:
            def create_multipolygon(self,area):
                if area.orig_id()==20:raise RuntimeError('invalid area (area_id=40)')
                return real.create_multipolygon(area)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.osm';source.write_text(OSM)
            target=root/'index.sqlite'
            with patch('osmium.geom.GeoJSONFactory',return_value=Factory()):import_pbf(source,target)
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute('SELECT osm_key FROM features ORDER BY osm_key').fetchall(),[('node/1',),('way/20',)])
                self.assertEqual(db.execute('SELECT osm_key,stage FROM rejected_geometries').fetchall(),[('way/20','area')])
                self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='complete'").fetchone(),('1',))
    def test_unrelated_geometry_failure_is_not_silenced(self):
        class Factory:
            def create_multipolygon(self,area):raise RuntimeError('unexpected factory failure')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.osm';source.write_text(OSM)
            target=root/'index.sqlite'
            with patch('osmium.geom.GeoJSONFactory',return_value=Factory()):
                with self.assertRaisesRegex(RuntimeError,'unexpected factory failure'):import_pbf(source,target)
            self.assertFalse(target.exists())
