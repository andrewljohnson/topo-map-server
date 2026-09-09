"""Conservative line conflation in local ground metres, before MVT quantization.

OSM is the reference network; agency-only portions extend it. Mere crossings and
close but differently named paths do not match. All matched source records survive.
"""
import json, math, re, unicodedata
from shapely.geometry import LineString
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree


def lines(geometry):
    if geometry.geom_type == 'LineString':
        return [geometry] if geometry.length else []
    return [part for g in getattr(geometry, 'geoms', []) for part in lines(g)]


def normalized_name(value):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    aliases={'mt':'mount','mtn':'mountain','blvd':'boulevard','sp':'spur','hwy':'highway'}
    value = re.sub(r'\b(mt|mtn|blvd|sp|hwy)\b',lambda m:aliases[m[0]],value)
    value = re.sub(r'\b(trail|trl|road|rd)\b', '', value)
    return re.sub(r'[^a-z0-9]', '', value)


def records(props):
    if props.get('source_records'):
        return json.loads(props['source_records'])
    return [{'id':str(props.get('id', '')), 'agency':props.get('agency', 'OpenStreetMap'),
             'name':props.get('name', ''), 'details':{k:v for k,v in props.items() if k not in ('source_records', 'source_count')}}]


def merge_properties(target, incoming):
    combined = { (r['agency'],r['id']):r for r in records(target) + records(incoming) }
    target['source_records'] = json.dumps(list(combined.values()), separators=(',',':'), sort_keys=True)
    target['source_count'] = len(combined)
    # Preserve reference geometry/class/name. Fill missing descriptive information;
    # conflicting values remain in source_records, including MVUM permissions.
    for key,value in incoming.items():
        if key not in ('id','class','kind','source_records','source_count') and not target.get(key):
            target[key] = value


def original_properties(props):
    # Never use a reference copied from a previous agency match as independent
    # evidence for another match.
    if props.get('source_records'):
        for record in records(props):
            if record['id']==str(props.get('id','')) and record['agency']==props.get('agency','OpenStreetMap'):
                return record['details']
    return props


def road_refs(props):
    value=str(original_properties(props).get('ref','')).upper()
    values={re.sub(r'^(?:NFSR|NF|FR|FS)\s*[- ]?\s*(?=\d)','',v.strip()) for v in value.split(';') if v.strip()}
    return {v for v in values if re.search(r'\d',v)}


def shared_road_ref(a,b):
    if not any(p.get('kind')=='forest_road' for p in (a,b)):return False
    return bool(road_refs(a)&road_refs(b))


def paved_surface(value):
    value=str(value or '').strip().upper()
    return value in ('ASPHALT','PAVED','CONCRETE') or value.startswith(('AC -','BST -','PCC -'))


def compatible(a, b):
    # A nearby bridge/tunnel is not the same at-grade path.
    for key in ('is_bridge','is_tunnel'):
        if bool(a.get(key,False)) != bool(b.get(key,False)):
            return False
    ca,cb=a.get('class','path'),b.get('class','path')
    paths={'path','footway','cycleway','bridleway','steps','pedestrian','sidewalk','crossing'}
    # Motorized agency trails may legitimately correspond to OSM tracks.
    return (ca in paths)==(cb in paths) or (a.get('kind')=='motorized_trail' and cb=='track') or (b.get('kind')=='motorized_trail' and ca=='track')


def overlap_mask(incoming, reference, a, b, *, aligned_road=False):
    if not compatible(a,b):return None
    na,nb=normalized_name(a.get('name')),normalized_name(b.get('name'))
    # A shared distinctive name supports moderate GPS alignment differences.
    same=bool(na and nb and na==nb) or bool(a.get('route_ref') and a.get('route_ref')==b.get('route_ref')) or shared_road_ref(a,b)
    tolerance=15.0 if same else 8.0 if aligned_road else 2.5 if na and nb else 5.0
    if incoming.equals(reference):return incoming.buffer(.01)
    # A closed loop has no net start-to-end progress, so use whole-shape agreement.
    if any(g.is_ring for g in lines(incoming)) and .88 <= incoming.length/max(reference.length,.01) <= 1.12 and incoming.hausdorff_distance(reference)<=tolerance:
        return incoming.buffer(.01)
    parts=[]
    for ref in lines(reference):
        corridor=ref.buffer(tolerance,cap_style=2)
        for part in lines(incoming.intersection(corridor)):
            # Require sustained overlap, not the small footprint of a crossing.
            minimum=min(35.0, incoming.length*.85, ref.length*.85)
            if part.length < max(8.0,minimum):continue
            # Follow the reference in the same or reversed direction. A transverse
            # crossing or sharp shortcut must not qualify solely by proximity.
            positions=[ref.project(part.interpolate(i/8, normalized=True)) for i in range(9)]
            progress=abs(positions[-1]-positions[0])
            travelled=sum(abs(v-u) for u,v in zip(positions,positions[1:]))
            if not part.length*.88 <= progress <= part.length*1.12 or travelled > progress*1.08:continue
            parts.append(part.buffer(tolerance,cap_style=2).intersection(corridor))
    return unary_union(parts) if parts else None


def conflate(reference, additions):
    """Return one network, retaining unmatched tails/branches and source metadata.

    Feature geometries must already be in ground metres with a processing halo.
    Input dictionaries are local to this build and may be enriched in-place.
    """
    result=list(reference)
    fixed=len(result)
    # Geometry is immutable once a result is appended. Reuse its matching
    # corridor across additions; property enrichment does not change geometry.
    corridors={}
    tree=STRtree([f['geometry'] for f in result]) if result else None
    for feature in additions:
        geometry=feature['geometry']
        candidates=([int(i) for i in tree.query(geometry.buffer(15))] if tree is not None else [])+list(range(fixed,len(result)))
        remaining=geometry
        anchors=[]
        for index in sorted(candidates):
            existing=result[index]
            if index not in corridors:corridors[index]=existing['geometry'].buffer(15)
            if not remaining.intersects(corridors[index]):continue
            mask=overlap_mask(remaining,existing['geometry'],feature['properties'],existing['properties'])
            if mask is None:continue
            # Long, tightly aligned rural road overlap establishes a shared
            # segment even when agency/OSM names differ. Allow modest remaining
            # survey offsets only after that evidence; never widen service lanes
            # or use proximity alone to merge parallel campground roads.
            rural={'track','unclassified'}
            if feature['properties'].get('kind')=='forest_road' and existing['properties'].get('class') in rural and remaining.intersection(mask).length>=100:
                extended=overlap_mask(remaining,existing['geometry'],feature['properties'],existing['properties'],aligned_road=True)
                if extended is not None:mask=mask.union(extended)
            original=original_properties(existing['properties'])
            incoming=feature['properties']
            pavement=(original.get('class')=='track' and not original.get('surface') and incoming.get('kind')=='forest_road' and paved_surface(incoming.get('surface')) and existing['geometry'].difference(mask).length<=existing['geometry'].length*.05)
            merge_properties(existing['properties'],incoming)
            if pavement:
                existing['properties']['class']='unclassified'
                existing['properties']['class_basis']='agency_explicit_pavement'
            anchors.append(existing['geometry'])
            remaining=remaining.difference(mask)
            if remaining.is_empty:break
        parts=[]
        for part in lines(remaining):
            if part.length < 1:continue
            coords=list(part.coords)
            # Connect only newly cut ends, never move original trail endpoints.
            for end in (0,-1):
                point=part.boundary.geoms[0 if end==0 else -1] if not part.is_ring else None
                if point is None:continue
                original_end=any(point.distance(endpoint)<.01 for line in lines(geometry) for endpoint in getattr(line.boundary,'geoms',[]))
                if not original_end and anchors:
                    anchor=nearest_points(point,unary_union(anchors))[1]
                    if point.distance(anchor)<=15.01:coords[end]=(anchor.x,anchor.y)
            parts.append(LineString(coords))
        if parts:
            feature={**feature,'geometry':unary_union(parts)}
            result.append(feature)
    return result
