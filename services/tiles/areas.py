"""Bundled overview boundaries and a lightweight nationwide area directory."""
from functools import lru_cache
import json
from area_labels import label_center
from pathlib import Path

AREA_FILE=Path(__file__).resolve().parent/'regions'/'protected-areas.geojson'

@lru_cache(maxsize=1)
def area_data():
    original=json.loads(AREA_FILE.read_text())
    features=[];catalog=[]
    for feature in original['features']:
        props=dict(feature['properties'])
        kind=props['kind'];bounds=props['bounds'];center=props['center']
        anchor,method=label_center(feature['geometry']) if 'label_center' not in props else (props['label_center'],props.get('label_method','precomputed'))
        props.update(label_center=anchor,label_method=method)
        span=max(0,bounds[2]-bounds[0])*max(0,bounds[3]-bounds[1])
        national=kind=='park' and 'national park' in (props.get('designation','')+' '+props['name']).lower()
        props['min_zoom']=3 if national or span>8 else 5 if kind=='forest' else 7 if kind=='wilderness' else 6
        props['priority']=(0 if national else 1 if kind=='forest' else 2 if kind=='wilderness' else 3)-min(span,100)/1000
        features.append({**feature,'properties':props})
        features.append({'type':'Feature','id':str(props['id'])+'-label','geometry':{'type':'Point','coordinates':anchor},'properties':props})
        catalog.append({key:props[key] for key in ('id','name','kind','bounds','center','designation') if key in props})
    catalog.sort(key=lambda x:x['name'].casefold())
    return catalog,{'type':'FeatureCollection','features':features}

@lru_cache(maxsize=2)
def area_bytes(geometry=False):
    return json.dumps(area_data()[1 if geometry else 0],separators=(',',':')).encode()
