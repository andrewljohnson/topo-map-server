import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import mapbox_vector_tile
import numpy as np
from rasterio.transform import Affine
from shapely.geometry import LineString,box
from shapely.ops import unary_union
import contours
import tile_service as tiles

class ContourTests(unittest.TestCase):
    def test_plane_levels_are_exact_international_feet(self):
        transform=Affine(1,0,0,0,-1,10)
        x=np.arange(10)+.5
        dem=np.tile(x*20*.3048,(10,1))
        lines=list(contours.contour_lines(dem,transform,box(0,0,10,10)))
        self.assertEqual({feet for feet,_ in lines},set(range(20,181,20)))
        for feet,line in lines:
            self.assertAlmostEqual(line.bounds[0],feet/20,places=10)
            self.assertAlmostEqual(line.bounds[2],feet/20,places=10)
    def test_nodata_is_masked_and_flat_sea_has_no_artificial_contour(self):
        transform=Affine(1,0,0,0,-1,10)
        dem=np.tile((np.arange(10)+.5)*20*.3048,(10,1))
        dem[:,5:]=np.nan
        lines=list(contours.contour_lines(dem,transform,box(0,0,10,10)))
        self.assertEqual({feet for feet,_ in lines},{20,40,60,80})
        self.assertEqual(list(contours.contour_lines(np.zeros((10,10)),transform,box(0,0,10,10))),[])
        self.assertEqual(list(contours.contour_lines(np.full((10,10),np.nan),transform,box(0,0,10,10))),[])
    def test_halos_match_continuous_contours_across_chunk_border(self):
        transform=Affine(1,0,0,0,-1,8)
        x=np.arange(12)+.5;y=8-(np.arange(8)+.5)
        dem=(x[None,:]+y[:,None])*10*.3048
        whole=list(contours.contour_lines(dem,transform,box(0,0,12,8)))
        split=list(contours.contour_lines(dem[:,:8],transform,box(0,0,6,8)))
        split+=list(contours.contour_lines(dem[:,4:],transform*Affine.translation(4,0),box(6,0,12,8)))
        for feet in {feet for feet,_ in whole}:
            expected=unary_union([line for value,line in whole if value==feet])
            actual=unary_union([line for value,line in split if value==feet])
            self.assertLess(expected.hausdorff_distance(actual),1e-9)
            self.assertAlmostEqual(expected.length,actual.length,places=9)
    def test_vector_levels_labels_and_dataset_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);osm=directory/'osm.sqlite';elevation=directory/'contours.sqlite'
            with sqlite3.connect(osm) as con:
                con.executescript('CREATE TABLE features(id INTEGER PRIMARY KEY,kind TEXT,subtype TEXT,name TEXT,minzoom INTEGER,area REAL,geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
                con.execute('INSERT INTO metadata VALUES (?,?)',('sourceSha256','osm-source'))
            with patch.object(tiles,'DB',osm),patch.object(tiles,'CONTOURS_DB',elevation),patch.object(tiles,'DATA',directory):
                before=tiles.metadata()
                x,y=tiles.project(*tiles.META['center'])
                with sqlite3.connect(elevation) as con:
                    con.executescript('CREATE TABLE contours(id INTEGER PRIMARY KEY,ele_ft INTEGER,is_index INTEGER,geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
                    con.execute('INSERT INTO metadata VALUES (?,?)',('info',json.dumps({'status':'ready','sourceHash':'real-dem-hash','intervalFt':20,'indexIntervalFt':100})))
                    for ident,feet in enumerate([80,100,120],1):
                        geometry=LineString([(x-.000001,y+ident*.0000001),(x+.000001,y+ident*.0000001)])
                        con.execute('INSERT INTO contours VALUES (?,?,?,?)',(ident,feet,int(feet%100==0),geometry.wkb))
                        a,b,c,d=geometry.bounds;con.execute('INSERT INTO spatial VALUES (?,?,?,?,?)',(ident,a,c,b,d))
                after=tiles.metadata()
                self.assertEqual(before['datasetId'],after['datasetId'],'DEM changes must not invalidate OSM tiles')
                self.assertNotIn('contours',before['tilesets'])
                self.assertIn('contours',after['tilesets'])
                self.assertEqual(after['tilesets']['osm']['datasetId'],after['datasetId'])
                self.assertEqual(after['tileUrl'],'/tiles/{z}/{x}/{y}.pbf?datasetId='+after['datasetId'])
                for z,expected in [(10,[]),(11,[100]),(12,[100]),(13,[80,100,120]),(14,[80,100,120])]:
                    osm_blob=tiles.render_tile(z,int(x*2**z),int(y*2**z))
                    self.assertNotIn('contour',mapbox_vector_tile.decode(osm_blob))
                    blob=tiles.render_contour_tile(z,int(x*2**z),int(y*2**z))
                    decoded=mapbox_vector_tile.decode(blob)
                    self.assertEqual(set(decoded),{'contour'})
                    features=decoded['contour']['features']
                    self.assertEqual(sorted(f['properties']['ele_ft'] for f in features),expected)
                    for feature in features:
                        props=feature['properties']
                        self.assertEqual(props['name'],str(props['ele_ft'])+' ft')
                        self.assertEqual(props['index'],props['ele_ft']%100==0)
                coords=(14,int(x*16384),int(y*16384))
                osm_cached=tiles.tile_bytes(*coords)
                contour_cached=tiles.tile_bytes(*coords,tileset='contours')
                self.assertNotEqual(osm_cached,contour_cached)
                with sqlite3.connect(osm) as con:
                    con.execute("UPDATE metadata SET value='changed-osm' WHERE key='sourceSha256'")
                changed_osm=tiles.metadata()
                self.assertNotEqual(changed_osm['datasetId'],after['datasetId'])
                self.assertEqual(changed_osm['tilesets']['contours']['datasetId'],after['tilesets']['contours']['datasetId'])
                with sqlite3.connect(elevation) as con:
                    con.execute("UPDATE metadata SET value=? WHERE key='info'",(json.dumps({'status':'ready','sourceHash':'changed-dem-source','intervalFt':20,'indexIntervalFt':100}),))
                changed_dem=tiles.metadata()
                self.assertEqual(changed_dem['datasetId'],changed_osm['datasetId'])
                self.assertNotEqual(changed_dem['tilesets']['contours']['datasetId'],changed_osm['tilesets']['contours']['datasetId'])
    @unittest.skipUnless(tiles.CONTOURS_DB.exists(),'Statewide DEM processing has not completed')
    def test_real_statewide_contours_and_provenance(self):
        with sqlite3.connect(tiles.CONTOURS_DB) as con:
            info=json.loads(con.execute("SELECT value FROM metadata WHERE key='info'").fetchone()[0])
            self.assertEqual(info['status'],'ready')
            self.assertEqual(info['verticalDatum'],'NAVD88')
            self.assertGreater(info['featureCount'],1000)
            self.assertGreater(info['chunks'],50)
            self.assertGreater(info['validPixels']/info['coveragePixels'],.98)
            self.assertEqual(con.execute('SELECT count(*) FROM contours WHERE ele_ft%20!=0 OR is_index!=(ele_ft%100=0)').fetchone()[0],0)
            self.assertGreater(con.execute('SELECT max(ele_ft) FROM contours').fetchone()[0],3000,'Western Maryland mountain elevations should be present')
            for lon,lat in [(-79.3,39.5),(-77.3,39.4),(-76.6122,39.2904),(-75.7,38.5)]:
                x,y=tiles.project(lon,lat);radius=.0003
                count=con.execute('SELECT count(*) FROM contours JOIN spatial USING(id) WHERE minx<? AND maxx>? AND miny<? AND maxy>?',(x+radius,x-radius,y+radius,y-radius)).fetchone()[0]
                self.assertGreater(count,0,(lon,lat))
        x,y=tiles.project(*tiles.META['center'])
        features=mapbox_vector_tile.decode(tiles.render_contour_tile(14,int(x*16384),int(y*16384)))['contour']['features']
        self.assertGreater(len(features),0,'Baltimore tile must actually encode contour lines')
        self.assertTrue(all(f['properties']['ele_ft']%20==0 for f in features))

if __name__=='__main__':
    unittest.main()
