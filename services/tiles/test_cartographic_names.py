import unittest
from cartographic_names import display_name
class DisplayNames(unittest.TestCase):
 def test_agency_uppercase_is_readable_without_losing_codes(self):
  self.assertEqual(display_name('FALLEN LEAF CG SPUR C'),'Fallen Leaf Campground Spur C')
  self.assertEqual(display_name('USFS ROAD 12N42'),'USFS Road 12N42')
  self.assertEqual(display_name('MT. ROSE PEAK'),'Mt. Rose Peak')
  self.assertEqual(display_name('PCT CONNECTOR'),'PCT Connector')
 def test_existing_case_and_route_codes_survive(self):
  for name in ["McDonald's Path",'TRT','12N42','',"O'NEILL TRAIL"]:
   self.assertEqual(display_name(name),"O'Neill Trail" if name=="O'NEILL TRAIL" else name)
if __name__=='__main__':unittest.main()
