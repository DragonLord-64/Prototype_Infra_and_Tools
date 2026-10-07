"""Render-only and mocked HTTP contracts; never connect to a cluster."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

CHART = Path(__file__).resolve().parents[1] / 'charts/elasticsearch-kibana'


def render(kibana, filebeat):
    output = subprocess.check_output([
        'helm', 'template', 'logging', str(CHART), '--set',
        f'kibana.enabled={str(kibana).lower()},filebeat.enabled={str(filebeat).lower()}',
    ], text=True)
    return [item for item in yaml.safe_load_all(output) if item]


class BootstrapTests(unittest.TestCase):
    def test_component_combinations_and_secret_refs(self):
        for kibana in (False, True):
            for filebeat in (False, True):
                with self.subTest(kibana=kibana, filebeat=filebeat):
                    resources = render(kibana, filebeat)
                    jobs = [r for r in resources if r['kind'] == 'Job']
                    self.assertEqual(len(jobs), int(kibana or filebeat))
                    if not jobs:
                        continue
                    spec = jobs[0]['spec']
                    self.assertEqual(spec['activeDeadlineSeconds'], 600)
                    self.assertFalse(spec['template']['spec']['automountServiceAccountToken'])
                    container = spec['template']['spec']['containers'][0]
                    env = {e['name']: e['valueFrom']['secretKeyRef'] for e in container['env']}
                    self.assertEqual('KIBANA_PASSWORD' in env, kibana)
                    self.assertEqual('FILEBEAT_PASSWORD' in env, filebeat)
                    if filebeat:
                        self.assertEqual(env['FILEBEAT_PASSWORD'], {
                            'name': 'elastic-credentials', 'key': 'filebeat-password'})
                    subprocess.run(['bash', '-n'], input=container['args'][0], text=True, check=True)

    def run_setup(self, kibana=False, password='b' * 48, fail_first=False, always_fail=False):
        job = next(r for r in render(kibana, True) if r['kind'] == 'Job')
        script = job['spec']['template']['spec']['containers'][0]['args'][0]
        # Bound tests tightly and replace only waits; exercise actual generated API script.
        script = script.replace('seq 1 60', 'seq 1 2').replace('sleep 5', ':')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            fake = path / 'curl'
            fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ['REQUEST_LOG'])
records = json.loads(p.read_text()) if p.exists() else []
records.append({'url': sys.argv[-1], 'body': json.loads(sys.stdin.read()), 'args': sys.argv[1:]})
p.write_text(json.dumps(records))
print('response body deliberately discarded')
sys.exit(22 if os.environ.get('ALWAYS_FAIL') == '1' or (os.environ.get('FAIL_FIRST') == '1' and len(records) == 1) else 0)
''')
            fake.chmod(0o700)
            log = path / 'requests.json'
            env = dict(os.environ, PATH=f'{path}:{os.environ["PATH"]}',
                       REQUEST_LOG=str(log), ELASTIC_PASSWORD='a' * 48,
                       FILEBEAT_PASSWORD=password, KIBANA_PASSWORD='c' * 48,
                       FAIL_FIRST=str(int(fail_first)), ALWAYS_FAIL=str(int(always_fail)))
            result = subprocess.run(['bash', '-ec', script], env=env, text=True, capture_output=True)
            records = json.loads(log.read_text()) if log.exists() else []
            self.assertNotIn('a' * 48, result.stdout + result.stderr)
            self.assertNotIn(password, result.stdout + result.stderr)
            self.assertNotIn('response body', result.stdout + result.stderr)
            return result, records

    def test_publisher_role_then_user(self):
        result, records = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r['url'].split('/_security/')[1] for r in records],
                         ['role/filebeat_writer', 'user/filebeat_writer'])
        role = records[0]['body']
        self.assertEqual(role['indices'], [{'names': ['filebeat-*'],
                                           'privileges': ['auto_configure', 'create_doc']}])
        self.assertEqual(records[1]['body'], {'password': 'b' * 48, 'roles': ['filebeat_writer']})
        for record in records:
            self.assertIn('PUT', record['args'])
            self.assertIn('@-', record['args'])
            self.assertNotIn('b' * 48, record['args'])

    def test_combined_setup_and_retry(self):
        result, records = self.run_setup(kibana=True, fail_first=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(records), 4)
        self.assertTrue(records[0]['url'].endswith('kibana_system/_password'))
        self.assertTrue(records[1]['url'].endswith('kibana_system/_password'))
        self.assertTrue(records[-1]['url'].endswith('user/filebeat_writer'))

    def test_bad_password_rejected_before_http(self):
        result, records = self.run_setup(password='invalid-secret-with-quote"')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(records, [])

    def test_failed_role_never_creates_user_and_fails(self):
        result, records = self.run_setup(always_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r['url'].endswith('role/filebeat_writer') for r in records))

    def test_invalid_enable_value_rejected(self):
        result = subprocess.run(['helm', 'template', 'logging', str(CHART),
                                 '--set', 'filebeat.enabled=invalid'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
