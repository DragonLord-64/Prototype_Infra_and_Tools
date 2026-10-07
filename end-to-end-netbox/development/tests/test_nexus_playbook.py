"""Exercise actual Ansible tasks with isolated recording modules (no network)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml
from test_nexus_inventory import fixture

REPO = Path(__file__).resolve().parents[1]
MODULE = '''from ansible.module_utils.basic import AnsibleModule
import json
import os
from pathlib import Path
m = AnsibleModule(argument_spec=dict(data=dict(type='dict', required=True), netbox_url=dict(type='str'), netbox_token=dict(type='str', no_log=True), validate_certs=dict(type='bool'), query_params=dict(type='list', elements='str')), supports_check_mode=True)
d = m.params['data']
kind = Path(__file__).stem
if kind == 'netbox_module':
    assert d['module_bay']['device'] == d['device']
    assert d['module_bay']['name']
    key = kind + ':' + d['device'] + ':' + d['module_bay']['name']
elif kind=='netbox_module_type':
    key=kind+':'+str(d['manufacturer'])+':'+d['model']
else:
    key = kind + ':' + str(d.get('device', '')) + ':' + str(d.get('name', d.get('model')))
p = Path(os.environ['NEXUS_RECORDS'])
state = json.loads(p.read_text()) if p.exists() else {}
changed = state.get(key) != d
state[key] = d
if not m.check_mode:
    p.write_text(json.dumps(state, sort_keys=True))
m.exit_json(changed=changed, **({'module_type': {'id': 100+sum(ord(c) for c in key)}} if kind=='netbox_module_type' else {}))
'''


class TestPlaybook(unittest.TestCase):
    def test_previews_apply_and_repeat(self):
        with tempfile.TemporaryDirectory(prefix='nexus-playbook-') as tmp:
            root = Path(tmp)
            netbox = root / 'collections/ansible_collections/netbox/netbox'
            modules = netbox / 'plugins/modules'
            modules.mkdir(parents=True)
            meta = netbox / 'meta'
            meta.mkdir()
            names = ['netbox_site', 'netbox_device_role', 'netbox_manufacturer', 'netbox_device_type', 'netbox_custom_field', 'netbox_device', 'netbox_module_bay', 'netbox_module_type', 'netbox_module']
            (meta/'runtime.yml').write_text(yaml.safe_dump({'action_groups': {'netbox': names}}))
            for name in names:
                (modules/(name+'.py')).write_text(MODULE)
            play = yaml.safe_load((REPO/'netbox_import_nexus.yml').read_text())
            play[0]['hosts'] = 'localhost'
            play[0]['connection'] = 'local'
            play[0].pop('vars_files')
            play[0]['vars'].update(netbox_url='http://unused.invalid', netbox_token='test-only', ansible_python_interpreter=shutil.which('python3'),netbox_api_retry_delay=0,netbox_api_loop_pause=0)
            for task in play[0]['tasks']:
                if task.get('register') in ('discovered', 'epld'):
                    register = task.pop('register')
                    task.pop('cisco.nxos.nxos_command')
                    for key in ('check_mode', 'changed_when', 'failed_when'):
                        task.pop(key, None)
                    data=fixture();data[2]['TABLE_interface']['ROW_interface'][0]['name']='Finisar Corp'
                    stdout = [json.dumps(v) for v in data] if register == 'discovered' else ['EPLD Versions\nIO FPGA 0x12']
                    task['ansible.builtin.set_fact'] = {register: {'stdout': stdout}}
            for task in play[0]['tasks']:
                for child in task.get('block',[]):
                    if 'fhs_manufacturers' in child:
                        child.pop('fhs_manufacturers')
                        for key in ['register','until','retries','delay']:child.pop(key,None)
                        child['ansible.builtin.set_fact']={'nexus_manufacturers':{'manufacturers':{'Cisco':1,'Vendor':2,'Finisar Corp':3}}}
            path = root/'play.yml'
            path.write_text(yaml.safe_dump(play, sort_keys=False))
            records = root/'records.json'
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root/'tmp'), ANSIBLE_REMOTE_TEMP=str(root/'remote-tmp'), ANSIBLE_COLLECTIONS_PATH=str(root/'collections'), ANSIBLE_FILTER_PLUGINS=str(REPO/'filter_plugins'), NEXUS_RECORDS=str(records))
            def run(*args):
                result = subprocess.run([str(Path(sys.executable).with_name('ansible-playbook')), '-i', 'localhost,', str(path), *args], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout
            for args in (('--check',), ('--tags', 'facts'), ('--tags', 'compare')):
                run(*args)
                self.assertFalse(records.exists(), 'Preview executed a NetBox write')
            run()
            before = records.read_text()
            state = json.loads(before)
            device = state['netbox_device::DEMO-NEXUS']
            self.assertEqual(device['serial'], 'DEMO-SW')
            self.assertEqual(device['custom_fields']['fan_count'], 6)
            self.assertEqual(device['custom_fields']['epld_version'], 'EPLD Versions\nIO FPGA 0x12')
            self.assertEqual(len([k for k in state if k.startswith('netbox_module:')]), 10)
            self.assertTrue(all(isinstance(value['manufacturer'],int) for key,value in state.items() if key.startswith('netbox_module_type:')))
            self.assertTrue(all(isinstance(value['module_type'],int) for key,value in state.items() if key.startswith('netbox_module:')))
            self.assertEqual(len([k for k in state if k.startswith('netbox_module_bay:')]), 42)
            self.assertIn('changed=0', run())
            self.assertEqual(before, records.read_text())


if __name__ == '__main__':
    unittest.main()
