import unittest
from publish_cloud import ordered_plans

class PublicationOrderTest(unittest.TestCase):
    def test_california_layers_precede_national_pass_without_changing_cursor_indices(self):
        plans=[('osm',7,None),('osm',14,None),('osm',14,None),('dem',13,None),('trails',14,None),('trails',14,None)]
        regions=['world','california','conus','california','california','conus']
        ordered=ordered_plans(plans,regions)
        self.assertEqual([i for i,p in ordered],[0,1,3,4,2,5])
        for i,p in ordered:self.assertIs(p,plans[i])

if __name__=='__main__':unittest.main()
