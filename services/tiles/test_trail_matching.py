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
  result=conflate([base],[agency]);self.assertEqual(len(result),2);self.assertGreater(result[1]['geometry'].length,400)
 def test_service_lane_does_not_get_rural_alignment_expansion(self):
  base=feature([(0,0),(500,0)],'Campground Loop A',**{'class':'service'})
  agency=feature([(0,1),(200,1),(250,6),(500,6)],'Campground Loop B','USFS','two',kind='forest_road',**{'class':'track'})
  result=conflate([base],[agency]);self.assertEqual(len(result),2);self.assertGreater(result[1]['geometry'].length,200)

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
  self.assertEqual(len(result),2);self.assertGreater(result[1]['geometry'].length,500)
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
