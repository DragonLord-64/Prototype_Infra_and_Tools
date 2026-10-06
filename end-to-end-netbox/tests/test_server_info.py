"""Exercise the real metadata tasks locally without contacting NetBox or SSH."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAY = yaml.safe_load((ROOT / 'bootstrap.yml').read_text())[0]
READ = next(t for t in PLAY['tasks'] if t['name'] == 'Read provisioning metadata from the server')
CONFLICT = next(t for t in PLAY['tasks'] if t['name'].startswith('Reject conflicting locations'))

class ServerInfoTests(unittest.TestCase):
    def run_case(self, content, success, check=False, second=None):
        with tempfile.TemporaryDirectory(prefix='server-info-test-') as directory:
            directory = Path(directory)
            inventory = {'all': {'hosts': {}}}
            for host, contents in [('one', content)] + ([('two', second)] if second is not None else []):
                fixture = directory / (host + '.yaml')
                if contents is not None:
                    fixture.write_text(contents)
                inventory['all']['hosts'][host] = {'ansible_connection': 'local', 'metadata_path': str(fixture)}
                if success:
                    parsed = yaml.safe_load(contents) if contents else {}
                    inventory['all']['hosts'][host]['expected_metadata'] = {key: value.strip() for key, value in parsed.items()}
            tasks = copy.deepcopy([READ, CONFLICT])
            tasks[0]['block'][0]['ansible.builtin.stat']['path'] = '{{ metadata_path }}'
            tasks[0]['block'][2]['ansible.builtin.slurp']['src'] = '{{ metadata_path }}'
            tasks.append({'name': 'Check normalized metadata', 'ansible.builtin.assert': {'that': ['server_info == expected_metadata']}, 'when': 'expected_metadata is defined'})
            tasks.append({'name': 'Check effective site and role', 'ansible.builtin.assert': {'that': ["netbox_site == (server_info.site | default('Bootstrap Lab'))", "netbox_role == (server_info.role | default('Server'))"]}})
            playbook = [{'hosts': 'all', 'gather_facts': False, 'vars': {k: PLAY['vars'][k] for k in ['netbox_site', 'netbox_role']}, 'tasks': tasks}]
            (directory / 'play.yml').write_text(yaml.safe_dump(playbook))
            (directory / 'inventory.yml').write_text(yaml.safe_dump(inventory))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / 'local'), ANSIBLE_REMOTE_TEMP=str(directory / 'remote'), ANSIBLE_NOCOLOR='1', ANSIBLE_FORKS='1')
            command = [str(ROOT.parent / '.venv/bin/ansible-playbook'), '-i', str(directory / 'inventory.yml'), str(directory / 'play.yml')]
            if check:
                command += ['--check']
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_valid_metadata_and_whitespace(self):
        self.run_case('site: " Lab "\nrole: " Compute "\nrack: R1\nlocation: Room\n', True)

    def test_missing_file_preserves_defaults(self):
        self.run_case(None, True)

    def test_check_mode_reads_metadata(self):
        self.run_case('site: Lab\nrole: Compute\nrack: R1\nlocation: Room\n', True, check=True)

    def test_invalid_metadata(self):
        for content in ['', '[]', 'site: [Lab]\nrole: Compute\nrack: R1\nlocation: Room\n', 'site: Lab\nrole: Compute\nrack: R1\n', 'site: Lab\nrole: Compute\nrack: " "\nlocation: Room\n', 'site: Lab\nrole: Compute\nrack: R1\nlocation: Room\nextra: no\n', 'site: [broken']:
            with self.subTest(content=content):
                self.run_case(content, False)

    def test_shared_rack_conflict(self):
        self.run_case('site: Lab\nrole: Compute\nrack: R1\nlocation: Room A\n', False, second='site: Lab\nrole: Compute\nrack: R1\nlocation: Room B\n')

    def test_same_rack_name_across_sites(self):
        self.run_case('site: Lab A\nrole: Compute\nrack: R1\nlocation: Room A\n', True, second='site: Lab B\nrole: Storage\nrack: R1\nlocation: Room B\n')

if __name__ == '__main__':
    unittest.main()
