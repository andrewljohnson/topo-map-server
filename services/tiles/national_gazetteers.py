"""Pinned, local nationwide GNIS + GeoNames landmark index; no viewport API calls."""
import csv, hashlib, io, json, math, os, sqlite3, zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from feature_matching import match_reason, merge_into, name_key, distance, GENERIC
ROOT=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).parent/'data'))/'gazetteers'
DB=ROOT/'landmarks-v1.sqlite'
GNIS_TYPES={'Summit':('summit','mountain',13),'Gap':('pass','marker',13),'Spring':('spring','marker',14),'Falls':('waterfall','marker',13),'Arch':('arch','marker',14),'Pillar':('rock','marker',14),'Cave':('cave','marker',14)}
GEONAMES_TYPES={'T.MT':GNIS_TYPES['Summit'],'T.PK':GNIS_TYPES['Summit'],'T.HLL':GNIS_TYPES['Summit'],
 'T.PASS':GNIS_TYPES['Gap'],'T.GAP':GNIS_TYPES['Gap'],'T.SDL':GNIS_TYPES['Gap'],
 'H.SPNG':GNIS_TYPES['Spring'],'H.SPNT':GNIS_TYPES['Spring'],'H.SPNS':GNIS_TYPES['Spring'],
 'H.FLLS':GNIS_TYPES['Falls'],'S.CAVE':GNIS_TYPES['Cave'],'T.RK':GNIS_TYPES['Pillar']}

def point(source,ident,name,lon,lat,info,details):
 if not info or not name or '(historical)' in name.lower() or not math.isfinite(lon) or not math.isfinite(lat) or not(-180<=lon<=180 and (lon<=-60 or lon>=170) and 18<=lat<=72):return None
 kind,icon,zoom=info
 url='https://edits.nationalmap.gov/apps/gaz-domestic/public/search/names' if source=='gnis' else 'https://www.geonames.org/'+str(ident)
 props={'id':source+':'+str(ident),source+'_id':str(ident),'agency':'USGS GNIS' if source=='gnis' else 'GeoNames',
  'name':name,'kind':kind,'poi_icon':icon,'poi_frame':'circle','poi_image':'poi-circle-'+icon,'min_zoom':zoom,
  'source_url':url,'license':'Public domain' if source=='gnis' else 'CC BY 4.0',**details}
 return {'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':props}

def gnis(row):
 try:lon,lat=float(row['prim_long_dec']),float(row['prim_lat_dec'])
 except (ValueError,KeyError):return None
 return point('gnis',row['feature_id'],row['feature_name'],lon,lat,GNIS_TYPES.get(row['feature_class']),
  {'source_class':row['feature_class'],'state':row.get('state_name',''),'county':row.get('county_name',''),'map_name':row.get('map_name',''),'updated':row.get('date_edited') or row.get('date_created','')})

def geonames(row):
 if len(row)!=19:raise ValueError('GeoNames record must have 19 fields')
 if row[8]!='US':return None
 try:lon,lat=float(row[5]),float(row[4])
 except ValueError:return None
 code=row[6]+'.'+row[7]
 extra={'source_class':code,'state':row[10],'county':row[11],'updated':row[18], 'alternate_names':row[3]}
 # Only the reported elevation field, never the coarse DEM field, is a spot height.
 if row[15]:
  try:extra['elevation_m']=float(row[15]);extra['elevation_ft']=round(float(row[15])*3.280839895)
  except ValueError:pass
 if code in ('H.SPNT','H.SPNS'):extra['spring_type']='hot' if code=='H.SPNT' else 'sulphur'
 return point('geonames',row[0],row[1],lon,lat,GEONAMES_TYPES.get(code),extra)

def features(extent,database=None):
 path=Path(database or DB)
 # Required once the gazetteer dataset is advertised; missing imports must not
 # become cached successful empty tiles.
 if not path.exists():raise RuntimeError('GNIS/GeoNames index has not been imported')
 w,s,e,n=extent
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  return [json.loads(row[0]) for row in db.execute('SELECT f.feature FROM position p JOIN landmarks f ON f.rowid=p.id WHERE p.maxlon>=? AND p.minlon<=? AND p.maxlat>=? AND p.minlat<=? ORDER BY f.rowid',(w,e,s,n))]

def survey_name_match(a,b):
 """Offline-only candidates; the caller requires one unique catalog counterpart.

Old gazetteer points can mark a formation's center rather than its summit.
Never apply this relaxed survey tolerance to OSM, small amenities, or two GNIS IDs.
 """
 p,q=a['properties'],b['properties']
 if p.get('agency')!='GeoNames' or q.get('agency')!='USGS GNIS':return None
 if p.get('kind') not in ('summit','rock') or p.get('kind')!=q.get('kind'):return None
 key=name_key(p.get('name'),p.get('kind'))
 if key in GENERIC or key!=name_key(q.get('name'),q.get('kind')):return None
 if p.get('match_ambiguous') or q.get('match_ambiguous'):return None
 return 'unique_catalog_survey' if distance(a['geometry']['coordinates'],b['geometry']['coordinates'])<=750 else None

def import_archives(gnis_zip,geonames_zip,destination=None):
 destination=Path(destination or DB);destination.parent.mkdir(parents=True,exist_ok=True)
 pending=destination.with_suffix('.pending.sqlite');pending.unlink(missing_ok=True)
 counts=Counter();kinds=Counter();states=Counter();sources={}
 try:
  with sqlite3.connect(pending) as db:
   db.execute('CREATE TABLE landmarks(id TEXT PRIMARY KEY,lon REAL,lat REAL,kind TEXT,name_key TEXT,feature TEXT)')
   db.execute('CREATE INDEX matching ON landmarks(kind,name_key)')
   for source,path in [('gnis',Path(gnis_zip)),('geonames',Path(geonames_zip))]:
    with path.open('rb') as archive_file:digest=hashlib.file_digest(archive_file,'sha256').hexdigest()
    sources[source]={'sha256':digest,'bytes':path.stat().st_size}
    with zipfile.ZipFile(path) as z:
     member=next(m for m in z.namelist() if m.endswith('DomesticNames_National.txt')) if source=='gnis' else 'US.txt'
     with io.TextIOWrapper(z.open(member),encoding='utf-8-sig',newline='') as stream:
      rows=csv.DictReader(stream,delimiter='|') if source=='gnis' else csv.reader(stream,delimiter='\t',quoting=csv.QUOTE_NONE)
      if source=='gnis' and not {'feature_id','feature_name','feature_class','prim_lat_dec','prim_long_dec'}.issubset(rows.fieldnames or []):raise ValueError('Unexpected GNIS schema')
      for row in rows:
       counts[source+'_rows']+=1
       f=gnis(row) if source=='gnis' else geonames(row)
       if f is None:continue
       counts[source+'_accepted']+=1;p=f['properties'];lon,lat=f['geometry']['coordinates'];key=name_key(p['name'],p['kind'])
       candidates=[]
       # GNIS IDs represent distinct official features; retain each. GeoNames is
       # matched against the official names and earlier imported GeoNames records.
       if source=='geonames':
        for ident,raw in db.execute('SELECT id,feature FROM landmarks WHERE kind IN (?,?) AND name_key=? AND lat BETWEEN ? AND ?',(p['kind'],'rock' if p['kind']=='summit' else 'summit' if p['kind']=='rock' else p['kind'],key,lat-.05,lat+.05)):
         other=json.loads(raw);why=match_reason(f,other) or survey_name_match(f,other)
         if why:candidates.append((distance(f['geometry']['coordinates'],other['geometry']['coordinates']),ident,other,why))
       candidates.sort(key=lambda item:(item[0],item[1]))
       if candidates and (len(candidates)==1 or (all(c[3]!='unique_catalog_survey' for c in candidates) and candidates[1][0]-candidates[0][0]>=30)):
        _,ident,target,why=candidates[0]
        original_heights={k:target['properties'].get(k) for k in ('elevation_m','elevation_ft')}
        merge_into(target,f,why)
        if why=='unique_catalog_survey':
         # Preserve the survey elevation in provenance; it is not a spot height
         # measured at the retained, offset GNIS anchor.
         for key,value in original_heights.items():
          if value is None:target['properties'].pop(key,None)
          else:target['properties'][key]=value
        db.execute('UPDATE landmarks SET feature=? WHERE id=?',(json.dumps(target,separators=(',',':')),ident));counts['merged']+=1
        if why=='unique_catalog_survey':counts['survey_offset_merged']+=1
       else:
        if len(candidates)>1:counts['ambiguous_kept']+=1;p['match_ambiguous']=True
        db.execute('INSERT INTO landmarks VALUES(?,?,?,?,?,?)',(p['id'],lon,lat,p['kind'],key,json.dumps(f,separators=(',',':'))))
        kinds[p['kind']]+=1;states[p.get('state','')]+=1
   if not counts['gnis_accepted'] or not counts['geonames_accepted']:raise ValueError('Both nationwide sources must have eligible records')
   db.execute('CREATE VIRTUAL TABLE position USING rtree(id,minlon,maxlon,minlat,maxlat)')
   db.execute('INSERT INTO position SELECT rowid,lon,lon,lat,lat FROM landmarks')
   result={'imported_at':datetime.now(timezone.utc).isoformat(),'counts':dict(counts),'features':sum(kinds.values()),'kinds':dict(kinds),'states':dict(states),'sources':sources}
   db.execute('CREATE TABLE metadata(json TEXT)');db.execute('INSERT INTO metadata VALUES(?)',(json.dumps(result),));db.commit()
   if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Invalid landmark index')
  pending.replace(destination)
  return result
 except Exception:
  pending.unlink(missing_ok=True);raise

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--gnis',type=Path,required=True);parser.add_argument('--geonames',type=Path,required=True);parser.add_argument('--output',type=Path)
 args=parser.parse_args();print(json.dumps(import_archives(args.gnis,args.geonames,args.output),indent=2))
