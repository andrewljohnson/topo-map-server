import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from prepare_us import prepare

class PreparationDiagnosticsTest(unittest.TestCase):
    def test_import_failure_survives_a_subsequent_retry(self):
        with tempfile.TemporaryDirectory() as d:
            data=Path(d);folder=data/'osm-source';folder.mkdir()
            (folder/'us-latest.osm.pbf').write_bytes(b'fixture')
            with patch('osm_bulk.import_pbf',side_effect=ValueError('invalid source fixture')),patch('prepare_us.traceback.print_exc'):
                with self.assertRaises(ValueError):prepare(data)
            report=json.loads((folder/'import-error.json').read_text())
            self.assertEqual(report['type'],'ValueError')
            self.assertIn('invalid source fixture',report['traceback'])
            with patch('osm_bulk.import_pbf'):prepare(data)
            self.assertEqual(json.loads((folder/'import-error.json').read_text()),report)
