"""Opt-in integration tests against the isolated running replay lab."""
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('EXPORT_PROMETHEUS_URL', 'http://127.0.0.1:9093').rstrip('/')


def api(path, **params):
    with urlopen(BASE + path + ('?' + urlencode(params) if params else ''), timeout=30) as response:
        value = json.load(response)
    if value.get('status') != 'success':
        raise AssertionError(value)
    return value['data']


def query(expr):
    return api('/api/v1/query', query=expr)['result']


def expand(expr):
    # Use a selected node/switch/port exactly as the dashboard does. Do not
    # replace PromQL label_replace's $1 capture references.
    substitutions = {
        'node': 'demo-server-01', 'switch': 'demo-switch-01', 'port': '1',
        'node_metric': 'node_(load.*|memory_Mem.*|filesystem_.*|network_.*)',
        '__rate_interval': '1m', '__interval': '5s', '__range': '15m',
    }
    return re.sub(r'\$\{([A-Za-z_][A-Za-z_0-9]*)(?::[^}]+)?\}|\$([A-Za-z_][A-Za-z_0-9]*)',
                  lambda match: substitutions.get(match[1] or match[2], match[0]), expr)


@unittest.skipUnless(os.environ.get('EXPORT_LIVE_TEST') == '1', 'Start run.py and set EXPORT_LIVE_TEST=1')
class LiveTests(unittest.TestCase):
    def test_three_real_scrapes_up(self):
        targets = api('/api/v1/targets')['activeTargets']
        self.assertEqual({target['labels']['job'] for target in targets},
                         {'replay-fhs', 'replay-node', 'replay-switch'})
        for target in targets:
            self.assertEqual(target['health'], 'up', target['lastError'])

    def test_all_captured_series_preserved_after_scrape(self):
        for job, expected in [('fhs-exporter', 103), ('node', 9989), ('switch-telegraf', 8641)]:
            with self.subTest(job=job):
                self.assertEqual(float(query(f'count({{job="{job}"}})')[0]['value'][1]), expected)

    def test_all_dashboard_queries_execute(self):
        count = 0
        for path in sorted(ROOT.glob('*/grafana/dashboards/*.json')):
            dashboard = json.loads(path.read_text())
            for panel in dashboard['panels']:
                for target in panel.get('targets', []):
                    if 'expr' not in target:
                        continue
                    with self.subTest(dashboard=dashboard['uid'], panel=panel['id'], ref=target['refId']):
                        expression = expand(target['expr'])
                        self.assertNotRegex(expression, r'\$[A-Za-z_{]', 'Unresolved Grafana variable')
                        query(expression)
                    count += 1
        self.assertGreater(count, 50)

    def test_exported_switch_links_and_parent_count(self):
        self.assertEqual(float(query('count(nexus_interfaces_ifIndex)')[0]['value'][1]), 62)
        self.assertEqual(float(query('count(nexus_interfaces_ifIndex{operSt="up"})')[0]['value'][1]), 35)
        self.assertEqual(float(query('count(nexus_interfaces_ifIndex{operSt="down"})')[0]['value'][1]), 27)
        overview = json.loads((ROOT / 'switch/grafana/dashboards/switch-export-backed.json').read_text())
        board = next(panel for panel in overview['panels'] if panel['type'] == 'canvas')
        topology = json.loads((ROOT / 'switch/topology.json').read_text())
        self.assertEqual(len(topology), 34)
        self.assertTrue(board['options']['root']['elements'])


if __name__ == '__main__':
    unittest.main()
