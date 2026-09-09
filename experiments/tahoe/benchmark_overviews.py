#!/usr/bin/env python3
"""Bounded native-zoom overview sampling for the CONUS throughput model."""
import gzip,hashlib,importlib,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/tiles'))
from mapbox_vector_tile.Mapbox import vector_tile_pb2 as pb
from coverage_policy import allowed
SOURCES={'osm':('national_basemap',0),'boundaries':('national_boundaries',8),'landcover':('national_landcover',6),'trails':('national_trails',5),'amenities':('national_amenities',10),'waterways':('national_waterways',6),'recreation':('national_recreation',6)}

def combine_native(children):
    result=pb.tile()
    for source,blob in children:
        tile=pb.tile();tile.ParseFromString(blob)
        for layer in tile.layers:
            merged=result.layers.add();merged.CopyFrom(layer);merged.name=source+'__'+layer.name
    return result.SerializeToString(deterministic=True)

def tile_at(z,lon,lat):
    return (z,int((lon+180)/360*2**z),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z))

def main():
    points=[(-120.03,38.90),(-122.42,37.77),(-83.50,35.61),(-115.40,36.27)]
    keys={tile_at(z,*point) for point in points for z in (6,7,8,9,10,11)}
    keys|={tile_at(z,*point) for point in [(2.35,48.86),(139.69,35.69)] for z in (0,3,6,7)}
    out=ROOT/'services/tiles/data/experiments/native-overview-sample-v1';out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();report={'tiles':[],'workers':1,'mode':'native source detail at each overview zoom; retained inputs plus misses','startedAt':time.time()}
    for z,x,y in sorted(keys):
        row={'key':f'{z}/{x}/{y}','sources':{}};children=[];begin=time.monotonic()
        for source,(module_name,minzoom) in SOURCES.items():
            if z<minzoom or not allowed(source,z,x,y):continue
            stage=time.monotonic();blob=importlib.import_module(module_name).render_tile(z,x,y)
            row['sources'][source]=time.monotonic()-stage;children.append((source,blob))
        merged=combine_native(children);blob=gzip.compress(merged,mtime=0)
        path=out/'base'/str(z)/str(x)/f'{y}.pbf';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)
        row.update(seconds=time.monotonic()-begin,gzipBytes=len(blob),sha256=hashlib.sha256(merged).hexdigest())
        report['tiles'].append(row);(out/'progress.json').write_text(json.dumps(report))
    report['seconds']=time.monotonic()-started
    (ROOT/'experiments/tahoe/results/native-overview-sample.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
if __name__=='__main__':main()
