"""Conservative line conflation in local ground metres, before MVT quantization.

OSM is the reference network; agency-only portions extend it. Mere crossings and
close but differently named paths do not match. All matched source records survive.
"""
import json, math, re, unicodedata
from shapely.geometry import LineString, Point
from shapely.ops import unary_union, nearest_points, substring
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


def overlap_mask(incoming, reference, a, b, *, aligned_road=False, confirmed_trail=False):
    if not compatible(a,b):return None
    na,nb=normalized_name(a.get('name')),normalized_name(b.get('name'))
    # A shared distinctive name supports moderate GPS alignment differences.
    same=bool(na and nb and na==nb) or bool(a.get('route_ref') and a.get('route_ref')==b.get('route_ref')) or shared_road_ref(a,b)
    tolerance=50.0 if confirmed_trail else 15.0 if same else 8.0 if aligned_road else 2.5 if na and nb else 5.0
    if incoming.equals(reference):return incoming.buffer(.01)
    # A closed loop has no net start-to-end progress, so use whole-shape agreement.
    if any(g.is_ring for g in lines(incoming)) and .88 <= incoming.length/max(reference.length,.01) <= 1.12 and incoming.hausdorff_distance(reference)<=tolerance:
        return incoming.buffer(.01).union(reference.buffer(.01))
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


def refine_trail_match(incoming, reference, a, b, seed):
    """Refine this already established pair, never learn global name aliases.

    A tight match away from a junction and substantial directional agreement
    permit up to 50m of agency survey/generalization offset for the remainder.
    The original source names and unmatched branches remain intact.
    """
    if a.get('kind') not in ('trail','long_distance_trail') or b.get('agency')!='OpenStreetMap':return seed
    if not a.get('name') or not b.get('name') or reference.length<200:return seed
    interiors=[substring(part,25,part.length-25) for part in lines(reference) if part.length>50]
    if not interiors:return seed
    interior=unary_union(interiors)
    if incoming.intersection(seed).intersection(interior.buffer(2.5)).length<30:return seed
    expanded=overlap_mask(incoming,reference,a,b,confirmed_trail=True)
    if expanded is None or reference.intersection(expanded).length<max(150,reference.length*.6):return seed
    return seed.union(expanded)


def preserve_source_junctions(result, additions, matches):
    """Reconnect only an agency junction proven in the pre-conflation sources.

    A removed agency segment can have a slightly displaced OSM replacement.
    Preserve the original branch and add a short connection to that established
    replacement. Proximity alone is never evidence for a new junction.
    """
    if not matches:return result
    geometries=[f['geometry'] for f in result];tree=STRtree(geometries)
    original_ends={};original_shapes={};source_corridors={}
    for f in additions:
        key=(f['properties'].get('agency'),f['properties'].get('id'))
        original_shapes.setdefault(key,[]).append(f['geometry'])
        original_ends.setdefault(key,[]).extend(Point(c) for g in lines(f['geometry']) for c in (g.coords[0],g.coords[-1]))
    retained_by_key={}
    for index,f in enumerate(result):retained_by_key.setdefault((f['properties'].get('agency'),f['properties'].get('id')),[]).append(index)
    match_tree=STRtree([m[0] for m in matches]);output=[]
    for index,f in enumerate(result):
        props=f['properties'];key=(props.get('agency'),props.get('id'))
        if key not in original_ends:output.append(f);continue
        changed=False;parts=[]
        for line in lines(f['geometry']):
            coords=list(line.coords);discard=False
            if line.is_ring:parts.append(line);continue
            for end in (0,-1):
                point=Point(coords[end])
                if not any(point.distance(p)<.01 for p in original_ends[key]):continue
                if any(int(j)!=index and point.distance(geometries[int(j)])<.05 for j in tree.query(point.buffer(.05))):continue
                eligible=[]
                for j in match_tree.query(point.buffer(.05)):
                    original,mask,target,limit,other_key,other_props=matches[int(j)]
                    # A trim can move the adjoining retained tail just outside
                    # its mask. Require the original shared node and a nearby
                    # established match; never infer a junction from proximity.
                    if other_key==key or point.distance(original)>.05 or mask.distance(point)>limit:continue
                    if any(bool(props.get(k,False))!=bool(other_props.get(k,False)) for k in ('is_bridge','is_tunnel')):continue
                    if key not in source_corridors:source_corridors[key]=unary_union(original_shapes[key]).buffer(1)
                    # Duplicate surveys sharing a terminal segment do not prove
                    # a junction; the source partner must actually branch away.
                    if original.intersection(point.buffer(20)).difference(source_corridors[key]).length<5:continue
                    # Prefer the closest retained part of that exact source
                    # partner over a more distant replacement centerline.
                    targets=[geometries[k] for k in retained_by_key.get(other_key,[]) if k!=index]+[target]
                    for candidate in targets:
                        anchor=nearest_points(point,candidate)[1];distance=point.distance(anchor)
                        if .05<distance<=limit:eligible.append((distance,anchor))
                if eligible:
                    anchor=min(eligible,key=lambda item:item[0])[1]
                    opposite=Point(coords[-1 if end==0 else 0])
                    # A short terminal survey offset can already start at this
                    # same mapped junction. Do not turn it into an out-and-back
                    # spur by adding the identical connection in reverse.
                    opposite_original=any(opposite.distance(p)<.01 for p in original_ends[key])
                    if not opposite_original and opposite.distance(anchor)<.01 and line.length<15 and line.length<=point.distance(anchor)*1.05:
                        discard=True;changed=True;break
                    if end==0:coords.insert(0,(anchor.x,anchor.y))
                    else:coords.append((anchor.x,anchor.y))
                    changed=True
            if not discard:parts.append(LineString(coords))
        output.append({**f,'geometry':unary_union(parts),'properties':{**props,'junction_basis':'matched_source_junction'}} if changed else f)
    return output


def conflate(reference, additions):
    """Return one network, retaining unmatched tails/branches and source metadata.

    Feature geometries must already be in ground metres with a processing halo.
    Input dictionaries are local to this build and may be enriched in-place.
    """
    # Keep full tile-fragment context for geometric matching. Upstream may batch
    # unrelated paths into one feature, so apply metadata only to the matched
    # geometry in the final partition, never indiscriminately to that feature.
    result=[{**f,'properties':dict(f['properties'])} for f in reference]
    matched_metadata={}
    junction_matches=[]
    fixed=len(result)
    # Geometry is immutable once a result is appended. Reuse its matching
    # corridor across additions; property enrichment does not change geometry.
    corridors={}
    tree=STRtree([f['geometry'] for f in result]) if result else None
    for feature in additions:
        geometry=feature['geometry']
        candidates=([int(i) for i in tree.query(geometry.buffer(15))] if tree is not None else [])+list(range(fixed,len(result)))
        remaining=geometry
        anchors=[];anchor_limits=[]
        for index in sorted(candidates):
            existing=result[index]
            reference_props=original_properties(existing['properties'])
            if index not in corridors:corridors[index]=existing['geometry'].buffer(15)
            if not remaining.intersects(corridors[index]):continue
            mask=overlap_mask(remaining,existing['geometry'],feature['properties'],reference_props)
            if mask is None:continue
            refined=refine_trail_match(remaining,existing['geometry'],feature['properties'],reference_props,mask)
            snap_limit=50.01 if refined is not mask else 15.01
            mask=refined
            # Long, tightly aligned rural road overlap establishes a shared
            # segment even when agency/OSM names differ. Allow modest remaining
            # survey offsets only after that evidence; never widen service lanes
            # or use proximity alone to merge parallel campground roads.
            rural={'track','unclassified'}
            if feature['properties'].get('kind')=='forest_road' and existing['properties'].get('class') in rural and remaining.intersection(mask).length>=100:
                extended=overlap_mask(remaining,existing['geometry'],feature['properties'],reference_props,aligned_road=True)
                if extended is not None:mask=mask.union(extended)
            original=original_properties(existing['properties'])
            incoming=feature['properties']
            pavement=(original.get('class')=='track' and not original.get('surface') and incoming.get('kind')=='forest_road' and paved_surface(incoming.get('surface')) and existing['geometry'].difference(mask).length<=existing['geometry'].length*.05)
            matched_metadata.setdefault(index,[]).append((mask,dict(incoming),pavement))
            junction_matches.append((geometry,mask,existing['geometry'],snap_limit,(incoming.get('agency'),incoming.get('id')),dict(incoming)))
            anchors.append(existing['geometry']);anchor_limits.append(snap_limit)
            remaining=remaining.difference(mask)
            if remaining.is_empty:break
        parts=[]
        for part in lines(remaining):
            if part.length < 1:continue
            coords=list(part.coords);cut_ends=[]
            # Connect only newly cut ends, never move original trail endpoints.
            for end in (0,-1):
                point=part.boundary.geoms[0 if end==0 else -1] if not part.is_ring else None
                if point is None:continue
                original_end=any(point.distance(endpoint)<.01 for line in lines(geometry) for endpoint in getattr(line.boundary,'geoms',[]))
                cut_ends.append(not original_end)
                if not original_end and anchors:
                    candidates=[nearest_points(point,g)[1] for g in anchors]
                    eligible=[p for p,limit in zip(candidates,anchor_limits) if point.distance(p)<=limit]
                    if eligible:
                        anchor=min(eligible,key=point.distance);coords[end]=(anchor.x,anchor.y)
            # Tiny survey excursions can have both cut ends project to the same
            # reference point. Keeping their middle vertex creates a false spike
            # (or apparent disconnected spur) longer than the source excursion.
            if len(cut_ends)==2 and all(cut_ends) and Point(coords[0]).distance(Point(coords[-1]))<.01:
                # A three-vertex remainder can collapse to an exact retraced
                # line even when slightly longer than the tiny-loop cutoff.
                # Both ends were cuts; original dead ends and actual loops stay.
                if part.length<15 or (part.length<50 and len(set(coords))<=2):continue
            parts.append(LineString(coords))
        if parts:
            feature={**feature,'geometry':unary_union(parts)}
            result.append(feature)
    result=preserve_source_junctions(result,additions,junction_matches)
    output=[]
    for index,feature in enumerate(result):
        segments=[(part,dict(feature['properties'])) for part in lines(feature['geometry'])]
        for mask,incoming,pavement in matched_metadata.get(index,[]):
            next_segments=[]
            for geometry,props in segments:
                inside=geometry.intersection(mask)
                outside=geometry.difference(mask)
                # Keep the complete reference geometry. Only matched portions
                # acquire agency names, route badges, permissions and provenance.
                next_segments.extend((part,dict(props)) for part in lines(outside))
                if not inside.is_empty:
                    enriched=dict(props);merge_properties(enriched,incoming)
                    if pavement:
                        enriched['class']='unclassified';enriched['class_basis']='agency_explicit_pavement'
                    next_segments.extend((part,dict(enriched)) for part in lines(inside))
            segments=next_segments
        output.extend({**feature,'geometry':geometry,'properties':props} for geometry,props in segments)
    return output
