"""Build the offline Yosemite amenity pilot from a reproducible Overpass extract.

Usage: python build_amenities.py --fetch (refresh source), or without flags rebuild.
Requires shapely (already in the tile service environment).
"""
import argparse, hashlib, json, math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import polygonize, unary_union

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
BBOX = [37.70, -119.69, 37.78, -119.53]
URL = 'https://overpass-api.de/api/interpreter'
QUERY = '[out:json][timeout:60];(' + ''.join('nwr[' + tag + '](37.70,-119.69,37.78,-119.53);' for tag in ['amenity','tourism','leisure','shop','waterway=slipway']) + ');out body geom;'
SOURCE = BASE / 'yosemite-amenities-osm.json'
AMENITIES = {'toilets':'toilet','drinking_water':'drinking-water','water_point':'drinking-water','restaurant':'restaurant','fast_food':'restaurant','cafe':'cafe','parking':'parking','fuel':'fuel','ranger_station':'information','hospital':'hospital','clinic':'hospital','pharmacy':'pharmacy','picnic_table':'picnic-site','shelter':'marker'}
TOURISM = {'camp_site':'campsite','caravan_site':'campsite','picnic_site':'picnic-site','information':'information','hotel':'lodging','hostel':'lodging','museum':'museum','viewpoint':'viewpoint'}
ORDER = ['campsite','picnic-site','information','drinking-water','toilet','parking','restaurant','cafe','shop','lodging','swimming','marker','hospital','pharmacy','fuel','museum','viewpoint']

def categories(tags):
    icons = set()
    if tags.get('amenity') in AMENITIES: icons.add(AMENITIES[tags['amenity']])
    if tags.get('tourism') in TOURISM: icons.add(TOURISM[tags['tourism']])
    if tags.get('shop') in {'supermarket','convenience','outdoor','gift','general'}: icons.add('shop')
    # A beach does not imply swimming permission or suitability.
    if tags.get('leisure') in {'swimming_area','swimming_pool'} or tags.get('sport') == 'swimming': icons.add('swimming')
    if tags.get('drinking_water') == 'yes': icons.add('drinking-water')
    if tags.get('toilets') == 'yes': icons.add('toilet')
    return sorted(icons, key=lambda x: ORDER.index(x))

def geometry(element):
    if '_geometry' in element:
        from shapely.geometry import shape as read_shape
        return read_shape(element['_geometry'])
    if element['type'] == 'node': return Point(element['lon'], element['lat'])
    if element['type'] == 'way':
        coords = [(p['lon'],p['lat']) for p in element.get('geometry',[]) if p]
        if len(coords) < 2: return None
        if len(coords) > 3 and coords[0] == coords[-1]:
            shape = Polygon(coords)
            return shape if shape.is_valid else shape.buffer(0)
        return LineString(coords)
    outer, inner = [], []
    for member in element.get('members',[]):
        coords = [(p['lon'],p['lat']) for p in member.get('geometry',[]) if p]
        if len(coords) > 1: (inner if member.get('role') == 'inner' else outer).append(LineString(coords))
    polygons = list(polygonize(unary_union(outer))) if outer else []
    if not polygons: return None
    shape = unary_union(polygons)
    holes = list(polygonize(unary_union(inner))) if inner else []
    return shape.difference(unary_union(holes)) if holes else shape

def meters(a,b):
    return math.hypot((a.x-b.x)*111320*math.cos(math.radians(a.y)), (a.y-b.y)*111320)

def feature(point, props):
    return {'type':'Feature','geometry':{'type':'Point','coordinates':[round(point.x,7),round(point.y,7)]},'properties':props}

def build(data):
    items = []
    for e in data['elements']:
        tags = e.get('tags',{})
        icons = categories(tags)
        if not icons: continue
        shape = geometry(e)
        if shape is None or shape.is_empty: continue
        point = shape if shape.geom_type == 'Point' else shape.representative_point()
        items.append({'id':f"{e['type']}/{e['id']}",'tags':tags,'icons':icons,'shape':shape,'point':point})
    sites = [i for i in items if i['tags'].get('name') and (i['tags'].get('tourism') in {'camp_site','caravan_site','picnic_site'} or i['tags'].get('information') == 'visitor_centre')]
    sites.sort(key=lambda i:i['id'])
    members = {s['id']:[] for s in sites}
    assignments = {}
    for item in items:
        if item in sites:
            chosen = item
        else:
            enclosing = [s for s in sites if s['shape'].geom_type in {'Polygon','MultiPolygon'} and s['shape'].covers(item['point'])]
            chosen = min(enclosing,key=lambda s:s['shape'].area) if enclosing else None
            if chosen is None:
                # Only attach adjacent points near point sites; never bridge two neighboring sites.
                nearby = sorted([(meters(item['point'],s['point']),s) for s in sites if s['shape'].geom_type == 'Point'], key=lambda p:p[0])
                if nearby and nearby[0][0] <= 70 and (len(nearby)<2 or nearby[1][0] > nearby[0][0] + 50): chosen = nearby[0][1]
        if chosen:
            assignments[item['id']] = chosen['id']
            members[chosen['id']].append(item)
    features=[]
    for site in sites:
        icons = sorted({icon for i in members[site['id']] for icon in i['icons']},key=lambda x:ORDER.index(x))
        features.append(feature(site['point'],{'kind':'group','name':site['tags']['name'],'icons':icons,'group_id':site['id'],'osm_id':site['id'],'osm_ids':[i['id'] for i in members[site['id']]],'min_zoom':10,'max_zoom':15,'anchor_method':'point_on_surface' if site['shape'].geom_type != 'Point' else 'osm_node','member_count':len(members[site['id']])}))
    # Keep site-reported services visible after the cluster splits. These are
    # badges on the site symbol, never fabricated bathroom/water coordinates.
    site_services = {}
    for site in sites:
        known = {icon for item in members[site['id']] for icon in categories({k:v for k,v in item['tags'].items() if k not in {'toilets','drinking_water'}})}
        reported = {icon for item in members[site['id']] for icon in item['icons']}
        site_services[site['id']] = sorted(reported-known,key=ORDER.index)
    for item in items:
        group_id = assignments.get(item['id'],'')
        # Extra facility tags describe the site, not precise bathroom/water locations.
        primary = categories({k:v for k,v in item['tags'].items() if k not in {'toilets','drinking_water'}})
        for icon in primary:
            services=site_services.get(item['id'],[]) if icon==primary[0] else []
            extra={'site_facilities':','.join(services),'grid_image':'amenity-grid:'+','.join([icon]+services),'facility_location':'site_only'} if services else {}
            if icon=='information':
                information={value.strip().lower() for value in item['tags'].get('information','').split(';') if value.strip()}
                if information:extra['information_type']=';'.join(sorted(information))
                # Direction signs belong at close scales; site clusters still
                # retain every member at their existing z15 handoff.
                if information & {'guidepost','route_marker'}:
                    extra['detail_minzoom']=17 if 'route_marker' in information or (item['tags'].get('bicycle')=='yes' and not item['tags'].get('name')) else 16
            features.append(feature(item['point'],{'kind':'amenity','group_id':group_id,'poi_icon':icon,'poi_frame':'circle' if icon in {'campsite','lodging','swimming','museum','viewpoint'} else 'square','name':item['tags'].get('name',''),'osm_id':item['id'],'min_zoom':15 if group_id else 14,'location_method':'osm_node' if item['shape'].geom_type == 'Point' else 'point_on_surface',**extra}))
    return {'type':'FeatureCollection','attribution':'© OpenStreetMap contributors · ODbL 1.0','source':'OpenStreetMap via Overpass','bounds':[-119.69,37.70,-119.53,37.78],'features':features}

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--fetch',action='store_true'); args=parser.parse_args()
    if args.fetch:
        request=Request(URL+'?'+urlencode({'data':QUERY}),headers={'User-Agent':'topo-map-server Yosemite amenity pilot'})
        SOURCE.write_bytes(urlopen(request,timeout=90).read())
    raw=SOURCE.read_bytes(); data=json.loads(raw)
    if data.get('remark'): raise ValueError(data['remark'])
    result=build(data)
    output=json.dumps(result,separators=(',',':'),ensure_ascii=False)+'\n'
    for app in ['mobile/src','web/app']:
        (ROOT / 'apps' / app / 'amenity-data.json').write_text(output)
    provenance={'source':URL,'query':QUERY,'bbox':BBOX,'osm_timestamp':data.get('osm3s',{}).get('timestamp_osm_base'),'sha256':hashlib.sha256(raw).hexdigest(),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','license_url':'https://www.openstreetmap.org/copyright','grouping':'Site polygon containment; unambiguous distance <=70m only for point sites. Polygon representative points stay inside their sites. No swimming inferred from beaches. Site facility tags contribute to group icons, not invented individual facility points.'}
    (BASE/'yosemite-amenities-sources.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(len(result['features']),'features;',sum(f['properties']['kind']=='group' for f in result['features']),'groups;',len(output.encode()),'bytes per app')

if __name__ == '__main__': main()
