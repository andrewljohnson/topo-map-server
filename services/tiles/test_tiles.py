import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mapbox_vector_tile
from shapely import from_wkb
from shapely.geometry import Point, Polygon
import tile_service as tiles

class TileTests(unittest.TestCase):
    def test_mercator_origin(self):
        self.assertEqual(tiles.project(0,0),(0.5,0.5))
    def test_bounds_and_zoom(self):
        x,y = tiles.project(*tiles.META['center'])
        self.assertTrue(tiles.valid_tile(14,int(x*2**14),int(y*2**14)))
        for coord in [(15,0,0),(5,0,0),(14,0,0),(6,64,0),(6,0,-1)]:
            self.assertFalse(tiles.valid_tile(*coord))
    def test_zoom_filtering(self):
        self.assertEqual(tiles.minimum_zoom('road','motorway'),6)
        self.assertEqual(tiles.minimum_zoom('building',''),14)
        self.assertEqual(tiles.minimum_zoom('label','city'),6)
    def test_mvt_polygon_hole_and_coordinate_orientation(self):
        z = 14
        x,y = [int(v*2**z) for v in tiles.project(*tiles.META['center'])]
        n = 2**z
        def ring(a,b):
            return [((x+a)/n,(y+a)/n),((x+b)/n,(y+a)/n),((x+b)/n,(y+b)/n),((x+a)/n,(y+b)/n),((x+a)/n,(y+a)/n)]
        poly = Polygon(ring(.1,.9),[ring(.4,.6)])
        point = Point((x+.2)/n,(y+.25)/n)
        with tempfile.TemporaryDirectory() as tmp, patch.object(tiles,'DB',Path(tmp)/'test.sqlite'):
            with tiles.connect() as con:
                con.executescript('CREATE TABLE features(id INTEGER PRIMARY KEY,kind TEXT,subtype TEXT,name TEXT,minzoom INTEGER,area REAL,geometry BLOB); CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy);')
                for ident,kind,geom in [(1,'water',poly),(2,'label',point)]:
                    con.execute('INSERT INTO features VALUES (?,?,?,?,?,?,?)',(ident,kind,'test','Test',6,geom.area,geom.wkb))
                    a,b,c,d = geom.bounds
                    con.execute('INSERT INTO spatial VALUES (?,?,?,?,?)',(ident,a,c,b,d))
            decoded = mapbox_vector_tile.decode(tiles.render_tile(z,x,y),default_options={'y_coord_down':True})
        polygon = decoded['water']['features'][0]['geometry']
        self.assertEqual(polygon['type'],'Polygon')
        self.assertEqual(len(polygon['coordinates']),2,'inner ring must remain a hole')
        pt = decoded['label']['features'][0]['geometry']['coordinates']
        self.assertAlmostEqual(pt[0],819,delta=1)
        self.assertAlmostEqual(pt[1],1024,delta=1,msg='MVT Y grows south')
    @unittest.skipUnless(tiles.DB.exists(),'Run prepare first')
    def test_real_maryland_vectors_and_cache(self):
        with tiles.connect() as con:
            self.assertGreater(con.execute('SELECT count(*) FROM features').fetchone()[0],100000)
        coords = (14,*[int(v*16384) for v in tiles.project(*tiles.META['center'])])
        blob = tiles.tile_bytes(*coords)
        decoded = mapbox_vector_tile.decode(blob)
        self.assertGreater(len(decoded['road']['features']),20)
        self.assertGreater(len(decoded['building']['features']),20)
        self.assertEqual(decoded['road']['extent'],4096)
        with patch.object(tiles,'render_tile',side_effect=AssertionError('must use cache')):
            self.assertEqual(tiles.tile_bytes(*coords),blob)
    @unittest.skipUnless(tiles.DB.exists(),'Run prepare first')
    def test_coastal_water_classification(self):
        with tiles.connect() as con:
            water = [from_wkb(row[0]) for row in con.execute("SELECT geometry FROM features WHERE kind='water' AND subtype='coastal'")]
        for lon,lat,expected in [(-76.4,38.8,True),(-75.05,38.4,True),(-76.6122,39.2904,False),(-76.4922,38.9784,False),(-77.41,39.41,False)]:
            point = Point(tiles.project(lon,lat))
            self.assertEqual(any(g.contains(point) for g in water),expected,(lon,lat))
    def test_outside_region_rejected(self):
        with self.assertRaises(ValueError):
            tiles.tile_bytes(14,0,0)

if __name__ == '__main__':
    unittest.main()
