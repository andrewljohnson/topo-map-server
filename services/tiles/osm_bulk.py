"""Local OSM amenity geometries and waterway tags for nationwide production use.
Import a complete Geofabrik US PBF once; readers only open the completed index.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from contextlib import closing
import re
import sqlite3
import shutil
from urllib.parse import quote
from shapely.geometry import shape
from regions.build_amenities import categories

DEFAULT=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).parent/'data'))/'osm-source/us-enrichment.sqlite'

def query_local(query,path=None):
    path=Path(path or os.environ.get('OSM_ENRICHMENT_DB',DEFAULT))
    if not path.exists():
        if os.environ.get('OSM_REQUIRE_BULK')=='1':
            raise RuntimeError('Import the US OSM enrichment index before warming amenities and waterways')
        return None
    with closing(sqlite3.connect('file:'+quote(str(path.resolve()))+'?mode=ro',uri=True)) as db:
        meta=dict(db.execute('SELECT key,value FROM metadata'))
        if meta.get('complete')!='1':raise RuntimeError('OSM enrichment import is incomplete')
        match=re.search(r'way\(id:([0-9,]+)\)',query)
        if match:
            ids=[int(x) for x in match[1].split(',')]
            placeholders=','.join('?' for _ in ids)
            elements=[{'type':'way','id':ident,'tags':json.loads(tags)} for ident,tags in db.execute('SELECT id,tags FROM waterways WHERE id IN ('+placeholders+')',ids)]
        else:
            bounds=re.findall(r'\]\((-?[0-9.]+),(-?[0-9.]+),(-?[0-9.]+),(-?[0-9.]+)\)',query)
            if not bounds or len(set(bounds))!=1:raise ValueError('Unsupported bulk OSM query')
            south,west,north,east=map(float,bounds[0])
            elements=[json.loads(row[0]) for row in db.execute('SELECT f.element FROM features f JOIN extents e ON f.rowid=e.id WHERE e.east>=? AND e.west<=? AND e.north>=? AND e.south<=?',(west,east,south,north))]
    return {'elements':elements,'_endpoint':'local-osm-pbf:'+meta['sha256'],
            'osm3s':{'timestamp_osm_base':meta.get('timestamp','')}}

def import_pbf(source,target,filter_empty=True):
    import osmium
    target.parent.mkdir(parents=True,exist_ok=True)
    # O_EXCL avoids simultaneous imports. A failed .building file is inspectable;
    # remove it explicitly before restarting an interrupted import.
    temp=target.with_suffix('.building')
    with temp.open('xb'):pass
    db=sqlite3.connect(temp)
    db.executescript("""
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE features(osm_key TEXT UNIQUE,element TEXT);
      CREATE VIRTUAL TABLE extents USING rtree(id,west,east,south,north);
      CREATE TABLE waterways(id INTEGER PRIMARY KEY,tags TEXT);
    """)
    factory=osmium.geom.GeoJSONFactory()
    class Importer(osmium.SimpleHandler):
        count=0
        def tick(self):
            self.count+=1
            if self.count%10000==0:
                db.commit();print(self.count,'features/tags indexed',flush=True)
                if shutil.disk_usage(target.parent).free<float(os.environ.get('TILE_MIN_FREE_GB','0'))*10**9:
                    raise RuntimeError('OSM import disk reserve reached')
        def feature(self,kind,ident,tags,geometry):
            if not categories(tags):return
            geom=shape(geometry)
            if geom.is_empty:return
            west,south,east,north=geom.bounds
            element={'type':kind,'id':ident,'tags':tags,'_geometry':geometry}
            rowid=db.execute('INSERT INTO features(osm_key,element) VALUES(?,?) ON CONFLICT(osm_key) DO UPDATE SET element=excluded.element RETURNING rowid',(f'{kind}/{ident}',json.dumps(element,separators=(',',':')))).fetchone()[0]
            db.execute('INSERT OR REPLACE INTO extents VALUES(?,?,?,?,?)',(rowid,west,east,south,north));self.tick()
        def node(self,node):
            tags=dict(node.tags)
            if categories(tags):self.feature('node',node.id,tags,{'type':'Point','coordinates':[node.location.lon,node.location.lat]})
        def way(self,way):
            tags=dict(way.tags)
            if tags.get('waterway'):
                db.execute('INSERT OR REPLACE INTO waterways VALUES(?,?)',(way.id,json.dumps(tags,separators=(',',':'))));self.tick()
            if categories(tags):
                coords=[[n.lon,n.lat] for n in way.nodes]
                if len(coords)>=2:
                    geom={'type':'Polygon','coordinates':[coords]} if len(coords)>3 and coords[0]==coords[-1] else {'type':'LineString','coordinates':coords}
                    self.feature('way',way.id,tags,geom)
        def area(self,area):
            tags=dict(area.tags)
            if categories(tags):self.feature('way' if area.from_way() else 'relation',area.orig_id(),tags,json.loads(factory.create_multipolygon(area)))
    digest=hashlib.sha256()
    with source.open('rb') as stream:
        while chunk:=stream.read(8*1024*1024):digest.update(chunk)
    with osmium.io.Reader(str(source)) as reader:
        timestamp=reader.header().get('osmosis_replication_timestamp')
    # Disk backed node locations avoid keeping the entire country in memory.
    index=target.with_suffix('.nodes')
    handler=Importer()
    try:
        # Location and area-assembly handlers run before callback filters.
        # Untagged nodes still supply way geometry, without Python callbacks.
        handler.apply_file(str(source),locations=True,idx='sparse_file_array,'+str(index),
                           filters=[osmium.filter.EmptyTagFilter()] if filter_empty else [])
        db.executemany('INSERT INTO metadata VALUES(?,?)',[
            ('complete','1'),('sha256',digest.hexdigest()),('source',source.name),
            ('timestamp',timestamp)])
        db.commit();db.close();temp.replace(target)
    finally:
        db.close()
        index.unlink(missing_ok=True)
    print('Imported',target,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args();import_pbf(args.source,args.output)
