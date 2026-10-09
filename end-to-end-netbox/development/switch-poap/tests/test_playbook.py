"""Opt-in execution against a strict local NetBox HTTP fixture."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('POAP_RUN_ANSIBLE_TESTS'), 'Set POAP_RUN_ANSIBLE_TESTS=1 with Ansible/NetBox collection installed')
class PlaybookTests(unittest.TestCase):
    def test_real_lookup_render_check_mode_idempotence_and_missing_serial(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                requests.append((parsed.path, query))
                if parsed.path == '/api/':
                    payload = {}
                else:
                    if parsed.path == '/api/dcim/devices/':
                        records = [dict(id=1, serial='EXAMPLE001', name='nexus-example')] if query.get('serial') == ['EXAMPLE001'] else []
                    elif parsed.path == '/api/dcim/interfaces/' and query.get('device_id') == ['1'] and query.get('name') == ['mgmt0']:
                        records = [dict(id=2, name='mgmt0', enabled=True,
                                        primary_mac_address=dict(mac_address='02:00:00:00:00:01'))]
                    elif parsed.path == '/api/ipam/ip-addresses/' and query.get('interface_id') == ['2']:
                        records = [dict(id=3, address='192.0.2.50/24')]
                    else:
                        self.send_error(400, 'Unexpected endpoint/filter')
                        return
                    payload = dict(count=len(records), next=None, previous=None, results=records)
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header('API-Version', '4.2')
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = Path(directory)
                credentials = base / 'credentials.yml'
                credentials.write_text(yaml.safe_dump(dict(netbox_url='http://127.0.0.1:' + str(server.server_port), netbox_token='dummy-test-token')))
                settings = dict(poap_serials=['EXAMPLE001'], poap_bootfile='boot.example/poap_script.py',
                                poap_gateway='192.0.2.1', poap_hosts_file=str(base / 'hosts' / 'cisco-poap-host'),
                                poap_options_file=str(base / 'options' / 'cisco-poap-opts'),
                                poap_script_file=str(base / 'scripts' / 'poap_script.py'),
                                netbox_credentials_file=str(credentials))
                config = base / 'settings.yml'
                config.write_text(yaml.safe_dump(settings))
                command = [sys.executable, '-m', 'ansible.cli.playbook', str(ROOT / 'netbox_switch_poap.yml'), '-e', '@' + str(config)]

                def run(*args, success=True):
                    result = subprocess.run(command + list(args), cwd=ROOT, capture_output=True, text=True, timeout=90)
                    self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                    return result.stdout

                # Existing directories let check mode evaluate templates without writes.
                for name in ('hosts', 'options', 'scripts'):
                    (base / name).mkdir()
                run('--check')
                self.assertFalse(Path(settings['poap_script_file']).exists())
                run()
                self.assertEqual(Path(settings['poap_hosts_file']).read_text(), '02:00:00:00:00:01,set:real-nexus-poap\n')
                self.assertEqual(Path(settings['poap_options_file']).read_text(), 'tag:real-nexus-poap,67,boot.example/poap_script.py\n')
                script = Path(settings['poap_script_file']).read_text()
                compile(script, 'generated_poap.py', 'exec')
                payload = ''.join(line for line in script.splitlines(keepends=True) if not line.startswith('#md5sum='))
                self.assertIn(hashlib.md5(payload.encode()).hexdigest(), script)
                self.assertIn('changed=0', run())
                settings['poap_serials'].append('MISSING')
                settings['poap_script_file'] = str(base / 'should-not-exist.py')
                config.write_text(yaml.safe_dump(settings))
                run(success=False)
                self.assertFalse(Path(settings['poap_script_file']).exists())
                self.assertTrue(any(path == '/api/ipam/ip-addresses/' for path, _ in requests))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
