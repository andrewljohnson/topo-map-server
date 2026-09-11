import unittest
from shapely.geometry import LineString
from recommend_reviews import compare,choose

def stat(length=1000,spacing=10,novel=0,turns=0):return {'lengthM':length,'medianVertexSpacingM':spacing,'outside50mM':novel,'sharpReversalsPerKm':turns}
class Recommendations(unittest.TestCase):
 def test_near_identical_does_not_keep_both(self):
  m=compare(LineString([(0,0),(1000,0)]),LineString([(0,3),(1000,3)]));self.assertEqual(choose(m,[stat(),stat(spacing=30)])[:2],('prefer',0))
 def test_displaced_parallel_paths_abstain(self):
  m=compare(LineString([(0,0),(1000,0)]),LineString([(0,80),(1000,80)]));self.assertEqual(choose(m,[stat(),stat()])[0],'uncertain')
 def test_unique_extension_requests_partial_review(self):
  m=compare(LineString([(0,0),(1000,0)]),LineString([(0,0),(1400,0)]));self.assertEqual(choose(m,[stat(),stat(length=1400,novel=350)])[0],'partial')
 def test_detail_alone_does_not_override_length_inflation(self):
  m={'coverage':[[.75,.8,.9],[.7,.8,.85]],'p90OffsetM':[30,35]};self.assertEqual(choose(m,[stat(length=1800,spacing=3,turns=8),stat(spacing=30)])[0],'uncertain')
 def test_density_does_not_override_reversal_warning(self):
  m={'coverage':[[.75,.8,.9],[.7,.8,.85]],'p90OffsetM':[30,35]};self.assertEqual(choose(m,[stat(spacing=3,turns=8),stat(spacing=30)])[0],'uncertain')
if __name__=='__main__':unittest.main()
