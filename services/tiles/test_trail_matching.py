import copy, json, unittest
from shapely.geometry import LineString
from trail_matching import conflate

def feature(coords, name='', agency='OSM', ident='one', **props):
 return {'id':ident,'geometry':LineString(coords),'properties':{'id':ident,'name':name,'agency':agency,'class':'path',**props}}

class TrailMatchingTest(unittest.TestCase):
 def test_offset_named_copy_merges_metadata(self):
  base=feature([(0,0),(200,0)],'Eagle Trail')
  agency=feature([(0,9),(200,9)],'EAGLE TRL','USFS','two',motorcycle='N')
  result=conflate([base],[agency])
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]['geometry'].wkt,base['geometry'].wkt)
  self.assertEqual(result[0]['properties']['source_count'],2)
  self.assertEqual(result[0]['properties']['motorcycle'],'N')
 def test_unmatched_extension_remains_connected(self):
  result=conflate([feature([(0,0),(100,0)],'Eagle')],[feature([(0,7),(160,7)],'Eagle','USFS','two')])
  self.assertEqual(len(result),2)
  self.assertLess(result[1]['geometry'].length,70)
  self.assertEqual(list(result[1]['geometry'].coords)[0],(100,0))
  self.assertEqual(list(result[1]['geometry'].coords)[-1],(160,7))
 def test_crossing_is_not_a_duplicate(self):
  result=conflate([feature([(0,0),(200,0)])],[feature([(100,-100),(100,100)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2);self.assertAlmostEqual(result[1]['geometry'].length,200)
 def test_nearby_different_names_remain(self):
  result=conflate([feature([(0,0),(200,0)],'Upper')],[feature([(0,8),(200,8)],'Lower','USFS','two')])
  self.assertEqual(len(result),2);self.assertAlmostEqual(result[1]['geometry'].length,200)
 def test_parallel_unnamed_paths_remain_outside_strict_tolerance(self):
  result=conflate([feature([(0,0),(200,0)])],[feature([(0,8),(200,8)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2)
 def test_bridge_and_surface_path_remain(self):
  result=conflate([feature([(0,0),(200,0)],is_bridge=True)],[feature([(0,0),(200,0)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2)
 def test_reverse_digitization_matches(self):
  result=conflate([feature([(0,0),(200,0)])],[feature([(200,1),(0,1)],agency='USFS',ident='two')])
  self.assertEqual(len(result),1)
 def test_agency_only_and_agency_duplicates(self):
  result=conflate([],[feature([(0,0),(200,0)],'Eagle','NPS'),feature([(0,7),(200,7)],'Eagle','USFS','two'),feature([(500,0),(600,0)],'Remote','USFS','three')])
  self.assertEqual(len(result),2);self.assertEqual(result[0]['properties']['source_count'],2)
 def test_switchback_shortcut_not_removed(self):
  result=conflate([feature([(0,0),(100,0),(100,12),(0,12)],'Eagle')],[feature([(0,0),(0,12)],'Eagle','USFS','two')])
  self.assertEqual(len(result),2)
 def test_conflicting_permissions_preserved(self):
  result=conflate([feature([(0,0),(200,0)],motorcycle='no')],[feature([(0,0),(200,0)],agency='MVUM',ident='two',motorcycle='yes')])
  p=result[0]['properties'];self.assertEqual(p['motorcycle'],'no')
  self.assertEqual({r['details']['motorcycle'] for r in json.loads(p['source_records'])},{'no','yes'})
 def test_distinct_road_and_path_remain(self):
  result=conflate([feature([(0,0),(200,0)],**{'class':'track'})],[feature([(0,1),(200,1)],agency='USFS',ident='two')])
  self.assertEqual(len(result),2)

 def test_closed_loop_duplicates_merge(self):
  coords=[(0,0),(100,0),(100,100),(0,100),(0,0)]
  result=conflate([feature(coords,'Loop')],[feature([(x+4,y+4) for x,y in coords],'Loop','USFS','two')])
  self.assertEqual(len(result),1)
 def test_exact_short_duplicate_merges(self):
  result=conflate([feature([(0,0),(2,0)])],[feature([(2,0),(0,0)],agency='USFS',ident='two')])
  self.assertEqual(len(result),1)

 def test_shared_long_route_identity_matches_name_variants(self):
  result=conflate([feature([(0,0),(200,0)],'Pacific Crest National Scenic Trail',route_ref='PCT')],[feature([(0,8),(200,8)],'PACIFIC CREST (PCT)','USFS','two',route_ref='PCT')])
  self.assertEqual(len(result),1)

 def test_forest_road_name_abbreviations(self):
  for first,second in [('MT. WATSON BLVD','Mount Watson Boulevard'),('JACKASS SP','Jackass Spur')]:
   result=conflate([feature([(0,0),(200,0)],first,**{'class':'track'})],[feature([(0,9),(200,9)],second,'USFS','two',kind='forest_road',**{'class':'track'})])
   self.assertEqual(len(result),1)
 def test_explicit_forest_ref_handles_different_names(self):
  base=feature([(0,0),(200,0)],'Willow Creek Road',ref='FR 31051',**{'class':'track'})
  agency=feature([(0,9),(200,9)],'Horse Meadows Road','USFS','two',ref='31051',kind='forest_road',**{'class':'track'})
  self.assertEqual(len(conflate([base],[agency])),1)
 def test_forest_ref_suffix_and_spur_are_not_discarded(self):
  for ref in ['73A','73-1','41073']:
   base=feature([(0,0),(200,0)],'Upper Road',ref='NF 73',**{'class':'track'})
   agency=feature([(0,9),(200,9)],'Lower Road','USFS','two',ref=ref,kind='forest_road',**{'class':'track'})
   self.assertEqual(len(conflate([base],[agency])),2)
 def test_inherited_ref_is_not_independent_evidence(self):
  from trail_matching import road_refs,merge_properties
  base=feature([(0,0),(200,0)],'First Road',**{'class':'track'})['properties']
  incoming=feature([(0,0),(200,0)],'Agency','USFS','two',ref='73',kind='forest_road')['properties']
  merge_properties(base,incoming)
  self.assertEqual(base['ref'],'73');self.assertEqual(road_refs(base),set())
 def test_explicit_pavement_promotes_fully_matched_track_and_keeps_provenance(self):
  base=feature([(0,0),(200,0)],'Mount Watson Boulevard',ref='NF 73',**{'class':'track'})
  agency=feature([(0,9),(200,9)],'MT. WATSON BOULEVARD','USFS','two',surface='BST - BITUMINOUS SURFACE TREATMENT',kind='forest_road',ref='73',**{'class':'unclassified'})
  result=conflate([base],[agency]);p=result[0]['properties']
  self.assertEqual(len(result),1);self.assertEqual(p['class'],'unclassified')
  self.assertEqual(json.loads(p['source_records'])[0]['details']['class'],'track')
 def test_partial_or_conflicting_pavement_does_not_promote_whole_road(self):
  for surface,length in [('',100),('gravel',200)]:
   base=feature([(0,0),(200,0)],'Example',surface=surface,**{'class':'track'})
   agency=feature([(0,0),(length,0)],'Example','USFS','two',surface='AC - ASPHALT',kind='forest_road',**{'class':'unclassified'})
   result=conflate([base],[agency]);self.assertEqual(result[0]['properties']['class'],'track')

 def test_long_aligned_rural_road_seed_handles_name_disagreement(self):
  base=feature([(0,0),(500,0)],'National Forest Development Road 039',**{'class':'track'})
  agency=feature([(0,1),(200,1),(250,6),(500,6)],'Kings Canyon Road','USFS','two',kind='forest_road',**{'class':'track'})
  self.assertEqual(len(conflate([base],[agency])),1)
 def test_parallel_roads_without_shared_alignment_remain(self):
  base=feature([(0,0),(500,0)],'Upper',**{'class':'track'})
  agency=feature([(0,6),(500,6)],'Lower','USFS','two',kind='forest_road',**{'class':'track'})
  self.assertEqual(len(conflate([base],[agency])),2)
 def test_short_shared_junction_does_not_swallow_different_road(self):
  base=feature([(0,0),(500,0)],'Upper',**{'class':'track'})
  agency=feature([(0,1),(40,1),(50,6),(500,6)],'Lower','USFS','two',kind='forest_road',**{'class':'track'})
  result=conflate([base],[agency]);self.assertGreater(sum(f['geometry'].length for f in result if f['properties']['agency']=='USFS'),400)
 def test_service_lane_does_not_get_rural_alignment_expansion(self):
  base=feature([(0,0),(500,0)],'Campground Loop A',**{'class':'service'})
  agency=feature([(0,1),(200,1),(250,6),(500,6)],'Campground Loop B','USFS','two',kind='forest_road',**{'class':'track'})
  result=conflate([base],[agency]);self.assertGreater(sum(f['geometry'].length for f in result if f['properties']['agency']=='USFS'),200)

 def test_forest_reference_prefixes_and_missing_numbers(self):
  from trail_matching import road_refs
  for ref in ['NF 73','NFSR 73','FR-73','FS73']:
   self.assertEqual(road_refs({'ref':ref}),{'73'})
  self.assertEqual(road_refs({'ref':'NF;FR'}),set())

 def test_confirmed_named_agency_survey_refines_remaining_trace(self):
  base=feature([(0,0),(600,0)],'Local name',agency='OpenStreetMap')
  incoming=feature([(0,20),(80,20),(100,1),(180,1),(210,35),(600,35)],'Survey name','USFS','two',kind='trail')
  result=conflate([base],[incoming]);self.assertEqual(len(result),1)
  self.assertEqual(result[0]['geometry'].wkt,LineString([(0,0),(600,0)]).wkt)
  self.assertEqual(result[0]['properties']['name'],'Local name')
  self.assertEqual(result[0]['properties']['source_count'],2)
 def test_parallel_trails_without_tight_seed_remain(self):
  result=conflate([feature([(0,0),(600,0)],'First',agency='OpenStreetMap')],[feature([(0,20),(600,20)],'Second','USFS','two',kind='trail')])
  self.assertEqual(len(result),2)
 def test_trail_short_shared_junction_is_not_alias_evidence(self):
  result=conflate([feature([(0,0),(600,0)],'First',agency='OpenStreetMap')],[feature([(0,1),(40,1),(60,20),(600,20)],'Second','USFS','two',kind='trail')])
  self.assertGreater(sum(f['geometry'].length for f in result if f['properties']['agency']=='USFS'),500)
 def test_refined_trail_extension_reconnects_without_moving_original_endpoint(self):
  incoming=feature([(0,20),(80,20),(100,1),(180,1),(210,35),(750,35)],'Survey','USFS','two',kind='trail')
  result=conflate([feature([(0,0),(600,0)],'Local',agency='OpenStreetMap')],[incoming])
  self.assertEqual(len(result),2)
  self.assertLess(result[1]['geometry'].distance(result[0]['geometry']),.001)
  self.assertEqual(list(result[1]['geometry'].coords)[-1],(750,35))
 def test_real_tahoe_reports_refine_only_the_established_pairs(self):
  from pathlib import Path
  from shapely.geometry import shape
  from trail_matching import overlap_mask,refine_trail_match
  fixtures=json.loads((Path(__file__).parent/'fixtures/tahoe-trail-alignment.json').read_text())
  improved=0
  for row in fixtures:
   a,b=row['incoming'],row['reference'];g,h=shape(a['geometry']),shape(b['geometry'])
   seed=overlap_mask(g,h,a['properties'],b['properties'])
   if seed is None:continue
   refined=refine_trail_match(g,h,a['properties'],b['properties'],seed)
   if h.intersection(refined).length>h.intersection(seed).length+100:improved+=1
  self.assertGreaterEqual(improved,3,'TRT and both Mt Rose child tiles need refinement')


class SegmentMetadataTests(unittest.TestCase):
 def test_unrelated_multiline_component_does_not_inherit_a_route(self):
  from shapely.geometry import MultiLineString
  base=feature([(0,0),(200,0)],agency='OpenStreetMap')
  base['geometry']=MultiLineString([[(0,0),(200,0)],[(500,0),(500,200)]])
  result=conflate([base],[feature([(0,1),(200,1)],'Agency Trail','USFS','two',route_ref='TRT')])
  matched=next(f for f in result if f['geometry'].bounds[0]==0)
  other=next(f for f in result if f['geometry'].bounds[0]==500)
  self.assertEqual(matched['properties']['route_ref'],'TRT')
  self.assertEqual(other['properties']['name'],'')
  self.assertNotIn('route_ref',other['properties'])
  self.assertNotIn('source_records',other['properties'])
 def test_partial_match_enriches_only_the_shared_segment(self):
  from shapely.ops import unary_union
  base=feature([(0,0),(300,0)],agency='OpenStreetMap')
  result=conflate([base],[feature([(100,1),(200,1)],'Agency Trail','USFS','two',route_ref='PCT')])
  self.assertTrue(unary_union([f['geometry'] for f in result]).equals(base['geometry']))
  named=[f for f in result if f['properties'].get('route_ref')=='PCT']
  self.assertEqual(sum(f['geometry'].length for f in named),100)
  self.assertEqual(sum(f['geometry'].length for f in result if not f['properties'].get('name')),200)
 def test_two_route_overlaps_keep_their_own_extents(self):
  from shapely.ops import unary_union
  base=feature([(0,0),(300,0)],agency='OpenStreetMap')
  result=conflate([base],[feature([(0,1),(100,1)],'First','USFS','two',route_ref='PCT'),feature([(200,1),(300,1)],'Second','USFS','three',route_ref='TRT')])
  self.assertTrue(unary_union([f['geometry'] for f in result]).equals(base['geometry']))
  for f in result:
   if f['properties'].get('route_ref')=='PCT':self.assertLessEqual(f['geometry'].bounds[2],100)
   if f['properties'].get('route_ref')=='TRT':self.assertGreaterEqual(f['geometry'].bounds[0],200)

class SourceJunctionTests(unittest.TestCase):
 def fixtures(self,gap=0,**branch_props):
  road=feature([(0,0),(200,0)],'Forest Road','OpenStreetMap','osm',**{'class':'track'})
  survey=feature([(0,7),(200,7)],'Forest Road','USFS','survey',**{'class':'track','kind':'forest_road'})
  branch=feature([(100,7+gap),(100,100)],'Branch','USFS','branch',**branch_props)
  return road,survey,branch
 def test_known_agency_junction_survives_reference_replacement(self):
  road,survey,branch=self.fixtures()
  for additions in ([survey,branch],[branch,survey]):
   result=conflate([road],additions);retained=next(f for f in result if f['properties']['id']=='branch')
   self.assertTrue(retained['geometry'].covers(branch['geometry']))
   self.assertLess(retained['geometry'].distance(road['geometry']),.001)
   self.assertEqual(retained['properties']['junction_basis'],'matched_source_junction')
   self.assertTrue(next(f for f in result if f['properties']['id']=='osm')['geometry'].equals(road['geometry']))
 def test_nearby_unconnected_endpoint_is_not_extended(self):
  road,survey,branch=self.fixtures(gap=2)
  retained=next(f for f in conflate([road],[survey,branch]) if f['properties']['id']=='branch')
  self.assertTrue(retained['geometry'].equals(branch['geometry']))
  self.assertNotIn('junction_basis',retained['properties'])
 def test_grade_separated_branch_is_not_connected(self):
  road,survey,branch=self.fixtures(is_bridge=True)
  retained=next(f for f in conflate([road],[survey,branch]) if f['properties']['id']=='branch')
  self.assertTrue(retained['geometry'].equals(branch['geometry']))
 def test_original_osm_gap_is_not_changed(self):
  road,survey,branch=self.fixtures();branch['properties']['agency']='OpenStreetMap'
  result=conflate([road,branch],[survey])
  self.assertTrue(next(f for f in result if f['properties']['id']=='branch')['geometry'].equals(branch['geometry']))

class SurveySpikeTests(unittest.TestCase):
 def test_real_short_excursions_do_not_become_false_spurs(self):
  from pathlib import Path
  from shapely.geometry import shape,Point
  from trail_matching import lines
  fixtures=json.loads((Path(__file__).parent/'fixtures/tahoe-junction-spikes.json').read_text())
  for row in fixtures:
   for f in row['reference']+row['additions']:f['geometry']=shape(f['geometry'])
   result=conflate(row['reference'],row['additions']);segments=[(f,g) for f in result for g in lines(f['geometry'])]
   original_ends=[Point(c) for f in row['additions'] for g in lines(f['geometry']) for c in (g.coords[0],g.coords[-1])]
   for i,(f,g) in enumerate(segments):
    if f['properties'].get('agency')!='USFS':continue
    for c in (g.coords[0],g.coords[-1]):
     p=Point(c)
     if any(p.distance(q)<.01 for q in original_ends):continue
     self.assertTrue(any(i!=j and p.distance(other)<1 for j,(_,other) in enumerate(segments)),row['name']+' has a newly disconnected end')

class TerminalOffsetTests(unittest.TestCase):
 def test_known_junction_terminal_offset_does_not_create_reverse_spur(self):
  from shapely.geometry import box
  from trail_matching import preserve_source_junctions
  road=feature([(0,0),(100,0)],'Road','OpenStreetMap','osm')
  original_branch=feature([(0,5),(50,5)],'Branch','USFS','branch')
  parent=feature([(50,5),(50,100)],'Parent','USFS','parent')
  stub={**original_branch,'geometry':LineString([(50,0),(50,5)])}
  match=(parent['geometry'],box(49,4.5,51,100),road['geometry'],15.01,('USFS','parent'),parent['properties'])
  result=preserve_source_junctions([road,stub],[original_branch,parent],[match])
  self.assertTrue(result[1]['geometry'].is_empty)
  self.assertTrue(result[0]['geometry'].equals(road['geometry']))
 def test_actual_short_branch_with_two_original_ends_is_retained(self):
  from shapely.geometry import box
  from trail_matching import preserve_source_junctions
  road=feature([(0,0),(100,0)],'Road','OpenStreetMap','osm')
  branch=feature([(50,0),(50,5)],'Branch','USFS','branch')
  parent=feature([(50,5),(50,100)],'Parent','USFS','parent')
  match=(parent['geometry'],box(49,4.5,51,100),road['geometry'],15.01,('USFS','parent'),parent['properties'])
  result=preserve_source_junctions([road,branch],[branch,parent],[match])
  self.assertTrue(result[1]['geometry'].covers(branch['geometry']))
 def test_duplicate_terminal_records_do_not_authorize_a_new_connection(self):
  from shapely.geometry import box
  from trail_matching import preserve_source_junctions
  road=feature([(45,0),(45,100)],'Road','OpenStreetMap','osm')
  branch=feature([(50,5),(50,100)],'Branch','USFS','branch')
  duplicate=feature([(50,5),(50,100)],'Survey copy','USFS','copy')
  match=(duplicate['geometry'],box(40,0,55,105),road['geometry'],15.01,('USFS','copy'),duplicate['properties'])
  result=preserve_source_junctions([road,branch],[branch,duplicate],[match])
  self.assertTrue(result[1]['geometry'].equals(branch['geometry']))
  self.assertNotIn('junction_basis',result[1]['properties'])

class RetainedPartnerJunctionTests(unittest.TestCase):
 def test_real_source_junctions_follow_the_retained_partner_near_a_trimmed_mask(self):
  from pathlib import Path
  from shapely.geometry import shape,Point
  from shapely.ops import unary_union
  from trail_matching import preserve_source_junctions
  rows=json.loads((Path(__file__).parent/'fixtures/sierra-retained-junctions.json').read_text())
  for row in rows:
   result=[{**f,'geometry':shape(f['geometry'])} for f in row['result']]
   additions=[{**f,'geometry':shape(f['geometry'])} for f in row['additions']]
   matches=[(shape(g),shape(mask),shape(target),limit,tuple(key),props) for g,mask,target,limit,key,props in row['matches']]
   updated=preserve_source_junctions(result,additions,matches);point=Point(row['point'])
   subject=unary_union([f['geometry'] for f in updated if f['properties']['id']==row['subjectId']])
   self.assertLess(subject.distance(point),.001,row['name'])
   self.assertGreater(subject.boundary.distance(point),.05,row['name']+' retains a dangling original junction')
   for old,new in zip(result,updated):
    self.assertLess(old['geometry'].difference(new['geometry'].buffer(.000001)).length,.000001,row['name']+' removed retained source geometry')
    if old['properties'].get('agency')=='OpenStreetMap':self.assertTrue(old['geometry'].equals(new['geometry']))
 def test_real_collapsed_three_vertex_excursion_does_not_become_an_out_and_back(self):
  from pathlib import Path
  from shapely.geometry import shape,Point
  from shapely.ops import unary_union
  from trail_matching import lines
  row=json.loads((Path(__file__).parent/'fixtures/sierra-mar-det.json').read_text())
  for f in row['reference']+row['additions']:f['geometry']=shape(f['geometry'])
  result=conflate(row['reference'],row['additions']);segments=[(f,g) for f in result for g in lines(f['geometry'])];focus=Point(row['point'])
  original_ends=[Point(c) for f in row['additions'] for g in lines(f['geometry']) for c in (g.coords[0],g.coords[-1])]
  for index,(f,g) in enumerate(segments):
   if f['properties'].get('agency')!='USFS':continue
   for c in (g.coords[0],g.coords[-1]):
    p=Point(c)
    if p.distance(focus)>10 or any(p.distance(q)<.01 for q in original_ends):continue
    self.assertTrue(any(index!=j and p.distance(other)<1 for j,(_,other) in enumerate(segments)),'collapsed excursion creates a false spur')
  before=unary_union([f['geometry'] for f in row['reference']]);after=unary_union([f['geometry'] for f in result if f['properties'].get('agency')=='OpenStreetMap'])
  self.assertLess(before.hausdorff_distance(after),.000001);self.assertAlmostEqual(before.length,after.length,places=5)

class UnnamedSurveyTests(unittest.TestCase):
 def test_unnamed_component_refines_without_absorbing_other_components(self):
  from shapely.geometry import MultiLineString
  from shapely.ops import unary_union
  base=feature([(0,0),(600,0)],agency='OpenStreetMap')
  base['geometry']=MultiLineString([[(0,0),(600,0)],[(0,1000),(3000,1000)]])
  incoming=feature([(0,20),(80,20),(100,1),(180,1),(210,35),(600,35)],'Survey','USFS','two',kind='trail')
  result=conflate([base],[incoming])
  self.assertTrue(unary_union([f['geometry'] for f in result]).equals(base['geometry']))
  other=[f for f in result if f['geometry'].bounds[1]>500]
  self.assertTrue(other)
  self.assertTrue(all(not f['properties'].get('name') for f in other))
 def test_distinct_trail_numbers_do_not_get_wide_refinement(self):
  base=feature([(0,0),(600,0)],agency='OpenStreetMap',ref='17E05')
  incoming=feature([(0,20),(80,20),(100,1),(180,1),(210,35),(600,35)],'Spur','USFS','two',kind='trail',ref='17E05A')
  result=conflate([base],[incoming])
  self.assertGreater(sum(f['geometry'].length for f in result if f['properties']['agency']=='USFS'),350)
 def test_unnamed_parallel_paths_and_short_junctions_remain(self):
  for coords in [[(0,20),(600,20)],[(0,1),(40,1),(60,20),(600,20)]]:
   result=conflate([feature([(0,0),(600,0)],agency='OpenStreetMap')],[feature(coords,'Survey','USFS','two',kind='trail')])
   self.assertGreater(sum(f['geometry'].length for f in result if f['properties']['agency']=='USFS'),500)
 def test_cathedral_sources_preserve_osm_and_reduce_duplicate_main_trail(self):
  from pathlib import Path
  from shapely.geometry import shape
  from shapely.ops import unary_union
  rows=json.loads((Path(__file__).parent/'fixtures/cathedral-trail-alignment.json').read_text())
  for row in rows:
   for f in row['reference']+row['additions']:f['geometry']=shape(f['geometry'])
   result=conflate(row['reference'],row['additions'])
   original=unary_union([f['geometry'] for f in row['reference']])
   retained=unary_union([f['geometry'] for f in result if f['properties'].get('agency')=='OpenStreetMap'])
   self.assertLess(original.difference(retained.buffer(.000001)).length,.001)
   self.assertLess(retained.difference(original.buffer(.000001)).length,.001)
   remaining=sum(f['geometry'].length for f in result if f['properties'].get('agency')=='USFS' and f['properties'].get('name')=='CATHEDRAL TRAIL')
   self.assertLess(remaining,350,row['name'])
   # The spur has no sustained tight alignment: proximity is insufficient.
   spur=unary_union([f['geometry'] for f in row['additions'] if f['properties'].get('name')=='CATHEDRAL SPUR'])
   kept=unary_union([f['geometry'] for f in result if f['properties'].get('name')=='CATHEDRAL SPUR'])
   self.assertLess(spur.difference(kept.buffer(.01)).length,1)

class SignedRouteSurveyTests(unittest.TestCase):
 def test_signed_survey_offset_requires_tight_seed_and_shared_identity(self):
  from trail_matching import refine_signed_route_match,overlap_mask
  base=feature([(0,0),(1000,0)],'Pacific Crest Trail',agency='OpenStreetMap',route_ref='PCT',ref='2000')
  survey=feature([(0,0),(100,0),(250,70),(750,70),(900,0),(1000,0)],'PCT Section','USFS','survey',kind='trail',route_ref='PCT',ref='PC2000')
  g,h=survey['geometry'],base['geometry'];seed=overlap_mask(g,h,survey['properties'],base['properties'])
  matched=refine_signed_route_match(g,h,survey['properties'],base['properties'],seed)
  self.assertLess(g.difference(matched).length,.01)
  for ref in ['', 'TRT']:
   props={**survey['properties'],'route_ref':ref}
   self.assertIs(refine_signed_route_match(g,h,props,base['properties'],seed),seed)
  parallel=LineString([(0,70),(1000,70)])
  self.assertTrue(refine_signed_route_match(parallel,h,survey['properties'],base['properties'],seed).equals(seed))
 def test_real_pct_reports_keep_only_reference_trace_near_report(self):
  import math
  from pathlib import Path
  from shapely.geometry import shape,Point
  from shapely.ops import unary_union
  from national_trails import route_ref
  rows=json.loads((Path(__file__).parent/'fixtures/pct-signed-route-alignment.json').read_text())
  targets={'PCT 14/2724/6267':(2724,6267,-120.126022,38.897893,350),'PCT 14/2805/6511':(2805,6511,-118.348933,34.602795,130)}
  for row in rows:
   for f in row['reference']+row['additions']:f['geometry']=shape(f['geometry'])
   for f in row['additions']:f['properties']['route_ref']=route_ref(f['properties'].get('name'))
   result=conflate(row['reference'],row['additions'])
   original=unary_union([f['geometry'] for f in row['reference']]);kept=unary_union([f['geometry'] for f in result if f['properties']['agency']=='OpenStreetMap'])
   self.assertLess(original.difference(kept.buffer(.000001)).length,.001)
   self.assertLess(kept.difference(original.buffer(.000001)).length,.001)
   if row['name'] not in targets:continue
   x,y,lon,lat,radius=targets[row['name']];n=16384;scale=40075016.68557849*math.cos(math.atan(math.sinh(math.pi*(1-2*(y+.5)/n))))
   point=Point(((lon+180)/360-x/n)*scale,((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2-y/n)*scale)
   traces=[f for f in result if f['properties'].get('route_ref')=='PCT' and f['geometry'].intersects(point.buffer(radius))]
   self.assertTrue(traces)
   self.assertTrue(all(f['properties']['agency']=='OpenStreetMap' for f in traces),row['name'])

class CanonicalPCTSourceTests(unittest.TestCase):
 def inputs(self):
  base=feature([(0,0),(1200,0)],'Pacific Crest Trail','OpenStreetMap','osm',ref='2000',route_ref='PCT')
  survey=feature([(0,0),(150,0),(400,180),(800,180),(1050,0),(1200,0)],'PACIFIC CREST TRAIL','USFS','usfs',ref='PC2000',route_ref='PCT',kind='trail')
  pcta=feature([(0,0),(1200,0)],'Pacific Crest Trail','PCTA','pcta',route_ref='PCT',kind='long_distance_trail')
  return base,survey,pcta
 def test_canonical_route_keeps_osm_and_strict_survey_metadata(self):
  from shapely.ops import unary_union
  base,survey,pcta=self.inputs();result=conflate([base],[pcta,survey])
  self.assertTrue(unary_union([f['geometry'] for f in result]).equals(base['geometry']))
  self.assertTrue(any('usfs' in f['properties'].get('source_records','') for f in result))
 def test_pcta_supplies_main_route_without_osm(self):
  from shapely.ops import unary_union
  base,survey,pcta=self.inputs();result=conflate([],[pcta,survey])
  self.assertTrue(unary_union([f['geometry'] for f in result]).equals(pcta['geometry']))
  self.assertTrue(all(f['properties']['agency']=='PCTA' for f in result))
 def test_absent_pcta_keeps_agency_fallback(self):
  base,survey,pcta=self.inputs();result=conflate([],[survey])
  self.assertEqual(len(result),1);self.assertTrue(result[0]['geometry'].equals(survey['geometry']))
 def test_catalogue_availability_survives_clip_edges_but_empty_catalogue_does_not(self):
  base,survey,pcta=self.inputs()
  self.assertEqual(conflate([],[survey],canonical_routes={'PCT'}),[])
  result=conflate([],[survey],canonical_routes=set())
  self.assertEqual(len(result),1);self.assertTrue(result[0]['geometry'].equals(survey['geometry']))
 def test_other_paths_and_branches_are_not_selected_out(self):
  for name,route in [('Pacific Crest Spur','PCT'),('Pacific Crest Alternate','PCT'),('Pacific Crest Connector','PCT'),('PCT ALT','PCT'),('PCT Access','PCT'),('PCT Approach','PCT'),('Other Trail',''),('Pacific Crest Trail','OTHER')]:
   base,survey,pcta=self.inputs();survey['properties'].update(name=name,route_ref=route)
   result=conflate([],[pcta,survey])
   self.assertTrue(any(f['properties']['agency']=='USFS' for f in result),(name,route))
 def test_real_twin_peaks_viewport_has_no_second_usfs_main_route(self):
  from pathlib import Path
  from shapely.geometry import shape
  from shapely.ops import unary_union
  rows=json.loads((Path(__file__).parent/'fixtures/pct-twin-peaks-corroboration.json').read_text())
  for row in rows:
   reference=[{**f,'geometry':shape(f['geometry'])} for f in row['reference']]
   additions=[{**f,'geometry':shape(f['geometry'])} for f in row['additions']]
   result=conflate(reference,additions)
   self.assertFalse(any(f['properties']['agency']=='USFS' and f['properties'].get('route_ref')=='PCT' for f in result),row['name'])
   original=unary_union([f['geometry'] for f in reference]);kept=unary_union([f['geometry'] for f in result if f['properties']['agency']=='OpenStreetMap'])
   self.assertLess(original.difference(kept.buffer(.000001)).length,.01)
   self.assertLess(kept.difference(original.buffer(.000001)).length,.01)
   # Source selection introduces no new PCT geometry or long connector: only
   # the same OSM+PCTA network as if the generalized USFS main survey were absent.
   canonical=conflate(reference,[f for f in additions if not (f['properties']['agency']=='USFS' and f['properties'].get('route_ref')=='PCT')])
   a=unary_union([f['geometry'] for f in result if f['properties'].get('route_ref')=='PCT'])
   b=unary_union([f['geometry'] for f in canonical if f['properties'].get('route_ref')=='PCT'])
   self.assertLess(a.difference(b.buffer(.000001)).length,.01)
   self.assertLess(b.difference(a.buffer(.000001)).length,.01)
