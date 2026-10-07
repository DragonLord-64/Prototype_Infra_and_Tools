import importlib.util
import os
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
for ancestor in ROOT.parents:
 for path in [ancestor/'collections',ancestor/'.ansible/collections']:
  if (path/'ansible_collections/netbox/netbox/plugins/inventory/nb_inventory.py').exists():sys.path.insert(0,str(path))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
plugin=load('fhs_inventory',ROOT/'inventory_plugins/fhs_nb_inventory.py')
setup=load('fhs_inventory_setup',ROOT/'setup_module_inventory.py')
MODULES=[dict(id=11,module_bay={'name':'FPGA CARD 0'},module_type={'model':'DEMO-FPGA'},serial='DEMO-FPGA0',custom_fields={'fpga_bmc_firmware':'1.1'}),dict(id=12,module_bay={'name':'FPGA CARD 1'},module_type={'model':'DEMO-FPGA'},serial='DEMO-FPGA1',custom_fields={}),dict(id=31,module_bay={'name':'NIC demo'},module_type={'model':'DEMO-NIC'},serial='DEMO-NIC0',custom_fields={'nic_firmware':'20.31'}),dict(id=41,module_bay={'name':'Power Supply 1'},module_type={'model':'DEMO-PSU'},serial='UNUSED-PSU')]
INTERFACES=[dict(id=21,name='C0-QSFP0',module={'id':11}),dict(id=22,name='eth-demo0',module={'id':31})]
class TestMapping(unittest.TestCase):
 def test_modules_serial_aliases_and_verified_port_join(self):
  variables=plugin.module_variables(MODULES,INTERFACES)
  self.assertEqual(variables['fpga_card0_sn'],'DEMO-FPGA0');self.assertEqual(variables['fpga_card1_sn'],'DEMO-FPGA1');self.assertEqual(variables['terabox_nic0_sn'],'DEMO-NIC0');self.assertEqual(len(variables['fhs_modules']),3)
  self.assertEqual(variables['fhs_nic_modules'][0]['interfaces'][0]['name'],'eth-demo0')
  self.assertNotIn('fpga_card0_bdf_ark',variables);self.assertNotIn('terabox_nic0_bdf',variables)
 def test_missing_data_and_ambiguous_nic_do_not_invent_alias(self):
  variables=plugin.module_variables([],[]);self.assertNotIn('fpga_card0_sn',variables)
  modules=MODULES+[dict(id=32,module_bay={'name':'NIC second'},module_type={},serial='DEMO-NIC1')]
  variables=plugin.module_variables(modules,[]);self.assertNotIn('terabox_nic0_sn',variables);self.assertTrue(variables['fhs_inventory_warnings'])
 def test_setup_preserves_vault_and_defaults_idempotently(self):
  import tempfile
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'inventory/dev_env').mkdir(parents=True)
   token="token:\n  type: Token\n  value: !vault |\n    $ANSIBLE_VAULT;1.1;AES256\n    SYNTHETIC-ENCRYPTED-TEXT\n"
   original='plugin: netbox.netbox.nb_inventory\napi_endpoint: https://example.invalid/netbox/\nconfig_context: true\nuse_extra_vars: true\nflatten_custom_fields: true\nquery_filters:\n  - status: active\ndevice_query_filters:\n  - has_primary_ip: true\ngroup_by:\n  - device_roles\n'+token
   path=root/'inventory/dev_env/netbox-inv.yml';path.write_text(original);(root/'ansible.cfg').write_text('[defaults]\nroles_path = ./roles\n')
   self.assertTrue(setup.update(root));changed=path.read_text();self.assertIn(token,changed);self.assertIn('api_endpoint: https://example.invalid/netbox/',changed);self.assertIn('group_by:\n  - device_roles',changed);self.assertFalse(setup.update(root))

class TestInventoryCLI(unittest.TestCase):
 def test_real_inventory_plugin_with_vault_and_filtered_modules(self):
  import copy,json,shutil,subprocess,tempfile,threading
  from http.server import BaseHTTPRequestHandler,HTTPServer
  from ansible.parsing.vault import VaultLib,VaultSecret
  requests=[]
  role=dict(id=1,name='FPGA_HOST_SERVER',slug='fpga-host-server')
  site=dict(id=1,name='Demo',slug='demo',region=None,group=None,time_zone=None,facility='',prefix_count=0)
  dtype=dict(id=1,model='TeraBox1501b',slug='terabox1501b',manufacturer={'id':1})
  device=dict(id=1,name='demo-server',site={'id':1},role={'id':1},device_type={'id':1},tenant=None,platform=None,rack=None,location=None,tags=[],serial='DEMO-SERVER',asset_tag='',status={'value':'active','label':'Active'},primary_ip={'id':10,'address':'192.0.2.1/24'},primary_ip4={'id':10,'address':'192.0.2.1/24'},primary_ip6=None,virtual_chassis=None,cluster=None,config_context={'example':True},custom_fields={'cpu_arch':'x86_64'})
  interfaces=[dict(value,device={'id':1},count_ipaddresses=0,tags=[]) for value in INTERFACES]
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    from urllib.parse import urlsplit,parse_qs
    parsed=urlsplit(self.path);query=parse_qs(parsed.query);requests.append((parsed.path,query,self.headers.get('Authorization')))
    if parsed.path=='/api/status/':body={'netbox-version':'4.3.0'}
    elif parsed.path=='/api/schema/':body={'info':{'version':'4.3.0'},'paths':{path:{'get':{'parameters':[{'name':name} for name in ['status','has_primary_ip']]}} for path in ['/api/dcim/devices/','/api/virtualization/virtual-machines/']}}
    else:
     values={'/api/dcim/devices/':[device],'/api/dcim/sites/':[site],'/api/dcim/device-roles/':[role],'/api/dcim/device-types/':[dtype],'/api/dcim/manufacturers/':[dict(id=1,name='BittWare',slug='bittware')],'/api/dcim/interfaces/':interfaces,'/api/dcim/modules/':MODULES}.get(parsed.path,[])
     body=dict(count=len(values),results=values,next=None)
    data=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  server=HTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  try:
   with tempfile.TemporaryDirectory(prefix='fhs-inventory-cli-') as temp:
    root=Path(temp);bundle=root/'playbooks/development';shutil.copytree(ROOT,bundle)
    (root/'inventory/dev_env').mkdir(parents=True);inventory=root/'inventory/dev_env/netbox-inv.yml'
    vault=VaultLib([('default',VaultSecret(b'fixture-password'))]);encrypted=vault.encrypt(b'synthetic-read-only').decode()
    inventory.write_text('plugin: netbox.netbox.nb_inventory\napi_endpoint: http://127.0.0.1:'+str(server.server_port)+'\nvalidate_certs: false\nconfig_context: true\nuse_extra_vars: true\nflatten_custom_fields: true\nquery_filters:\n  - status: active\ndevice_query_filters:\n  - has_primary_ip: true\ngroup_by:\n  - device_roles\ntoken:\n  type: Token\n  value: !vault |\n'+''.join('    '+line+'\n' for line in encrypted.splitlines()))
    (root/'ansible.cfg').write_text('[defaults]\ninventory = ./inventory/dev_env\n')
    setup.update(root);password=root/'password';password.write_text('fixture-password')
    collections=next(path for ancestor in ROOT.parents for path in [ancestor/'collections',ancestor/'.ansible/collections'] if (path/'ansible_collections/netbox/netbox').exists())
    env=dict(os.environ,ANSIBLE_CONFIG=str(root/'ansible.cfg'),ANSIBLE_LOCAL_TEMP=str(root/'tmp'),ANSIBLE_COLLECTIONS_PATH=str(collections))
    result=subprocess.run([str(Path(sys.executable).with_name('ansible-inventory')),'-i',str(inventory),'--vault-password-file',str(password),'--list'],cwd=root,env=env,capture_output=True,text=True,timeout=30)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertNotIn('Failed to parse inventory',result.stderr,result.stdout+result.stderr)
    data=json.loads(result.stdout)
    def decoded(value):
     if isinstance(value,dict):
      if set(value)=={'__ansible_unsafe'}:return value['__ansible_unsafe']
      return {key:decoded(child) for key,child in value.items()}
     if isinstance(value,list):return [decoded(child) for child in value]
     return value
    data=decoded(data);self.assertIn('demo-server',data['_meta']['hostvars'],result.stderr)
    host=data['_meta']['hostvars']['demo-server'];self.assertEqual(host['fpga_card0_sn'],'DEMO-FPGA0');self.assertEqual(host['fpga_card1_sn'],'DEMO-FPGA1');self.assertEqual(host['terabox_nic0_sn'],'DEMO-NIC0')
    self.assertEqual(host['ansible_host'],'192.0.2.1');self.assertEqual(host['cpu_arch'],'x86_64');self.assertEqual(host['config_context'],[{'example':True}])
    self.assertTrue(any(name.startswith('device_roles_') and 'demo-server' in group.get('hosts',[]) for name,group in data.items() if isinstance(group,dict)))
    self.assertNotIn('synthetic-read-only',result.stdout)
    selected=[query for path,query,auth in requests if path=='/api/dcim/devices/'];self.assertEqual(selected[0]['status'],['active']);self.assertEqual(selected[0]['has_primary_ip'],['True'])
    module_requests=[query for path,query,auth in requests if path=='/api/dcim/modules/'];self.assertEqual(module_requests[0]['device_id'],['1']);self.assertTrue(all(auth=='Token synthetic-read-only' for path,query,auth in requests))
  finally:server.shutdown();server.server_close();worker.join(timeout=3)

if __name__=='__main__':unittest.main()

