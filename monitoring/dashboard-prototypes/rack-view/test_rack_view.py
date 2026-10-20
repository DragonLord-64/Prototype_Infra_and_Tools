import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import exporter

class RackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        shutil.copytree(exporter.ROOT/'inventory',self.root/'inventory')
        shutil.copy(exporter.ROOT/'mock-health.json',self.root/'mock-health.json')
    def tearDown(self):self.temp.cleanup()
    def test_missing_health_keeps_position(self):
        body=exporter.render(self.root)
        self.assertIn('server_rack_info{server_id="server-b06"',body)
        self.assertNotIn('rack_server_health{server_id="server-b06"',body)
        self.assertEqual(len(exporter.inventory(self.root)),16)
    def test_health_does_not_change_inventory(self):
        original=exporter.inventory(self.root)
        (self.root/'mock-health.json').write_text('{"server-a01":1}')
        self.assertEqual(original,exporter.inventory(self.root))
        self.assertIn('rack_server_health{server_id="server-a01"} 1',exporter.render(self.root))
    def test_bounds_rejected(self):
        p=self.root/'inventory/server-a01.prom'
        p.write_text(p.read_text().replace('position_u="1"','position_u="42"'))
        with self.assertRaises(ValueError):exporter.inventory(self.root)
    def test_overlap_rejected(self):
        p=self.root/'inventory/server-a02.prom'
        p.write_text(p.read_text().replace('position_u="3"','position_u="1"'))
        with self.assertRaises(ValueError):exporter.inventory(self.root)
    def test_boolean_health_rejected(self):
        (self.root/'mock-health.json').write_text('{"server-a01":true}')
        with self.assertRaises(ValueError):exporter.render(self.root)
    def test_dashboard_fallback_and_dimensions(self):
        d=json.loads((exporter.ROOT/'grafana/dashboards/rack-view.json').read_text())
        canvas=d['panels'][1]
        self.assertEqual(len(canvas['targets']),16)
        for q in canvas['targets']:
            self.assertIn('up{job="rack-view-demo"}',q['expr'])
            self.assertIn('or on(server_id)',q['expr'])
        for record in exporter.inventory(self.root):
            el=next(e for e in canvas['options']['root']['elements'] if e['name']==record['server_id']+' body')
            self.assertEqual(el['placement']['height'],int(record['height_u'])*11-1)
            self.assertEqual(el['placement']['top'],36+(43-int(record['position_u'])-int(record['height_u']))*11)

if __name__=='__main__':unittest.main()
