"""Conservative entity matching for recreation points and natural landmarks."""
import json, math, re, unicodedata

GENERIC={'','camp','campground','trailhead','visitorcenter','restroom','restrooms','toilet','toilets','water','waterpoint','waterfountain','drinkingwater','spring','peak','summit','shop','store','picnicarea','viewpoint','information'}
SUFFIXES={'campground':r'\s+(?:campground|camp\s+ground)$','trailhead':r'\s+trail\s*head$','visitor_center':r'\s+visitor\s+cent(?:er|re)$'}
def name_key(name,kind=''):
 text=unicodedata.normalize('NFKD',str(name or '')).casefold()
 text=''.join(c for c in text if not unicodedata.combining(c))
 text=re.sub(r'[^a-z0-9]+',' ',text).strip()
 text=re.sub(r'\bmt\b','mount',text)
 text=re.sub(r'\bcamp ground\b','campground',text)
 if kind in SUFFIXES:text=re.sub(SUFFIXES[kind],'',text)
 return re.sub(r'\s+','',text)
def distance(a,b):
 return math.hypot(((a[0]-b[0]+180)%360-180)*111320*math.cos(math.radians((a[1]+b[1])/2)),(a[1]-b[1])*111320)
def match_reason(a,b):
 p,q=a['properties'],b['properties']
 if p.get('kind')!=q.get('kind') and {p.get('kind'),q.get('kind')}!={'summit','rock'}:return None
 if p.get('gnis_id') and q.get('gnis_id') and p['gnis_id']!=q['gnis_id']:return None
 meters=distance(a['geometry']['coordinates'],b['geometry']['coordinates'])
 for key in ('ridb_id','gnis_id','geonames_id'):
  if p.get(key) and str(p[key])==str(q.get(key,'')) and meters<5000:return key
 if p.get('match_ambiguous') or q.get('match_ambiguous'):return None
 left,right=name_key(p.get('name'),p.get('kind')),name_key(q.get('name'),q.get('kind'))
 if left in GENERIC or left!=right:return None
 # Preserve separately named campground loops and nearby generic facilities.
 limit=300 if p.get('kind') in ('summit','rock','pass') else 15 if p.get('kind') in ('restroom','drinking_water','store','food') else 120
 return 'name_kind_distance' if meters<=limit else None
def record(f):
 p=f['properties']
 return {'id':p.get('id',''),'agency':p.get('agency',''),'name':p.get('name',''),'coordinates':f['geometry']['coordinates'],'source_url':p.get('source_url',''),
         'details':{k:v for k,v in p.items() if k not in ('source_records','source_count','match_reason')}}

def merge_into(target,other,reason):
 p,q=target['properties'],other['properties']
 refs=json.loads(p.get('source_records','[]')) or [record(target)]
 for entry in json.loads(q.get('source_records','[]')) or [record(other)]:
  if entry['id'] not in {r['id'] for r in refs}:refs.append(entry)
 for key,value in q.items():
  if not p.get(key):p[key]=value
 p['source_records']=json.dumps(refs,separators=(',',':'))
 p['match_reason']=reason
 p['source_count']=len(refs)
 return target

def osm_kind(p):
 icon=p.get('poi_icon') or (p.get('icons') or [''])[0]
 if icon=='information':
  name=name_key(p.get('name'))
  return 'trailhead' if 'trailhead' in name else 'visitor_center' if 'visitorcenter' in name or 'visitorcentre' in name else 'ranger_station' if 'ranger' in name else 'information'
 return {'campsite':'campground','toilet':'restroom','drinking-water':'drinking_water','shop':'store','restaurant':'food','picnic-site':'picnic_site','viewpoint':'viewpoint','lodging':'lodging','mountain':'summit'}.get(icon,icon)
