from urllib.request import urlopen
from urllib.parse import urlencode
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,time
BASE=Path(__file__).parent/'raw'
BASE.mkdir(parents=True,exist_ok=True)
URLS={'forest':'https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0','park':'https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2','wilderness':'https://services1.arcgis.com/ERdCHt0sNM6dENSD/arcgis/rest/services/Wilderness_Areas_in_the_United_States/FeatureServer/0'}
def get(url,params):
 for i in range(3):
  try:
   d=json.load(urlopen(url+'/query?'+urlencode(params),timeout=60))
   if 'error' in d:raise ValueError(d['error'])
   return d
  except Exception:
   if i==2:raise
   time.sleep(1)
def fetch(item):
 name,url=item
 ids=get(url,{'f':'json','where':'1=1','returnIdsOnly':'true'})['objectIds']
 (BASE/(name+'-ids.json')).write_text(json.dumps(ids));print(name,len(ids),'IDs',flush=True)
 for i in range(0,len(ids),50):
  path=BASE/f'{name}-{i//50:03d}.geojson'
  if path.exists():continue
  data=get(url,{'f':'geojson','objectIds':','.join(map(str,ids[i:i+50])),'outFields':'*','returnGeometry':'true','outSR':'4326','maxAllowableOffset':.003,'geometryPrecision':5})
  if data.get('exceededTransferLimit'):raise ValueError('Truncated '+str(path))
  path.write_text(json.dumps(data,separators=(',',':')));print(name,i+len(data['features']),'features',path.stat().st_size,flush=True)
with ThreadPoolExecutor(3) as pool:list(pool.map(fetch,URLS.items()))
