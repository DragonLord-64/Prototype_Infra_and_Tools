"""Run actual copied FPGA tasks/module with synthetic SDK and local API only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
import yaml
from test_fhs import API,TEXT
ROOT=Path(__file__).resolve().parents[1]
class TestPortability(unittest.TestCase):
 def test_same_ska_topology_check_apply_repeat(self):
  api=API();api.data['dcim/interfaces/'][0]['name']='C0-QSFP0'
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def serve(self):
    from urllib.parse import urlsplit,parse_qs
    parsed=urlsplit(self.path);params={k:v[0] for k,v in parse_qs(parsed.query).items()}
    length=int(self.headers.get('Content-Length',0));data=json.loads(self.rfile.read(length)) if length else None
    result=api.request(self.command,'http://local'+parsed.path,params=params,json=data)
    payload=json.dumps(result.json()).encode();self.send_response(result.status_code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
   do_GET=serve;do_POST=serve;do_PATCH=serve
  server=HTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  try:
   with tempfile.TemporaryDirectory(prefix='fhs-copy-') as temp:
    root=Path(temp);bundle=root/'ska-mid-cbf-fhs-baremetal/playbooks/development';shutil.copytree(ROOT,bundle)
    sdk=root/'synthetic-sdk.py';sdk.write_text('print('+repr((ROOT/'tests/fixtures/bw_card_list.txt').read_text())+')')
    # Keep adjacent filter/library discovery, relative includes and all working defaults.
    primary=yaml.safe_load((bundle/'netbox_import.yml').read_text())[0]
    primary['hosts']='localhost';primary['connection']='local';primary.pop('vars_files')
    primary['vars'].update(netbox_url='http://127.0.0.1:'+str(server.server_port),netbox_token='synthetic-only',ansible_python_interpreter=sys.executable,
                           bootstrap_bittware_card_list_argv=[sys.executable,str(sdk)],bootstrap_bittware_debug=True,facts={'hostname':'host'})
    helper=next(t for t in yaml.safe_load((bundle/'tasks/apply.yml').read_text()) if 'fhs_fpga_sync' in t)
    helper.pop('tags');helper['fhs_fpga_sync']['preview']='{{ ansible_check_mode }}'
    primary['tasks']=[{'ansible.builtin.import_tasks':'tasks/fpga.yml'},helper]
    (bundle/'synthetic.yml').write_text(yaml.safe_dump([primary],sort_keys=False))
    env=dict(os.environ,ANSIBLE_LOCAL_TEMP=str(root/'local'),ANSIBLE_REMOTE_TEMP=str(root/'remote'),ANSIBLE_COLLECTIONS_PATH=str(root/'empty-collections'))
    def run(*args):
     result=subprocess.run([str(Path(sys.executable).with_name('ansible-playbook')),'-i','localhost,',str(bundle/'synthetic.yml'),*args],env=env,capture_output=True,text=True,timeout=60)
     self.assertEqual(result.returncode,0,result.stdout+result.stderr);return result.stdout
    # Remove unused collection action group so custom module test has no hidden collections.
    primary['module_defaults'].pop('group/netbox.netbox.netbox');(bundle/'synthetic.yml').write_text(yaml.safe_dump([primary],sort_keys=False))
    preview=run('--check','--diff');self.assertIn('stdout_lines',preview);self.assertIn('stderr_lines',preview);self.assertIn('900AAAA',preview);self.assertFalse(api.writes)
    run();self.assertEqual(len(api.data['dcim/modules/']),2);self.assertEqual(len(api.data['dcim/interfaces/']),6)
    self.assertIn('changed=0',run())
    # A failing SDK command must stop before parsing or any API write.
    sdk.write_text('import sys; print("synthetic SDK failure", file=sys.stderr); sys.exit(7)')
    before=len(api.writes)
    result=subprocess.run([str(Path(sys.executable).with_name('ansible-playbook')),'-i','localhost,',str(bundle/'synthetic.yml'),'--check'],env=env,capture_output=True,text=True,timeout=60)
    self.assertNotEqual(result.returncode,0);self.assertIn('exit 7',result.stdout);self.assertIn('synthetic SDK failure',result.stdout);self.assertNotIn('Normalize actual card output',result.stdout);self.assertEqual(len(api.writes),before)
    # Exercise the NIC tasks and same installed module helper from the copied layout.
    ports=[dict(interface='eth-demo0',address='0000:01:00.0'),dict(interface='eth-demo1',address='0000:01:00.1')]
    nic_tasks=yaml.safe_load((bundle/'tasks/nic.yml').read_text())
    for task in nic_tasks[0]['block']:
     if task['name'] in ['Check explicit SR-IOV virtual-function parent','Read physical-port names to exclude known representors']:
      name=task['name'];key='nic_vf_probes' if 'virtual-function' in name else 'nic_port_name_probes'
      task.clear();task.update(name=name,**{'ansible.builtin.set_fact':{key:{'results':[dict(item=port,stat={'exists':False}) for port in ports] if key=='nic_vf_probes' else []}}})
     if task.get('become'):task['become']=False
    (bundle/'tasks/nic.yml').write_text(yaml.safe_dump(nic_tasks))
    nic_sdk=root/'synthetic-ethtool.py'
    driver=(ROOT/'tests/fixtures/ethtool-driver.txt').read_text();link=(ROOT/'tests/fixtures/ethtool-link.txt').read_text();vpd=(ROOT/'tests/fixtures/nic-vpd.txt').read_text()
    nic_sdk.write_text('import sys\nDRIVER='+repr(driver)+'\nLINK='+repr(link)+'\nVPD='+repr(vpd)+'\nif sys.argv[1]=="vpd": print(VPD)\nelif sys.argv[1]=="-i": print(DRIVER.replace("0000:01:00.0", "0000:01:00.1" if sys.argv[2]=="eth-demo1" else "0000:01:00.0"))\nelse: print(LINK)\n')
    primary['vars'].update(bootstrap_nic_ethtool_argv=[sys.executable,str(nic_sdk)],bootstrap_nic_vpd_argv=[sys.executable,str(nic_sdk),'vpd'],facts=dict(hostname='host',interfaces=[port['interface'] for port in ports],**{port['interface']:{'pciid':port['address']} for port in ports}))
    nic_helper=next(task for task in yaml.safe_load((bundle/'tasks/apply.yml').read_text()) if task.get('fhs_fpga_sync',{}).get('kind')=='NIC')
    primary['tasks']=[{'ansible.builtin.import_tasks':'tasks/nic.yml'},nic_helper]
    (bundle/'synthetic.yml').write_text(yaml.safe_dump([primary],sort_keys=False))
    api.data['dcim/interfaces/'].append(dict(id=80,device=1,name='eth-demo0',module=None,type='other',enabled=False,cable=88))
    before=len(api.writes);run('--check','--diff');self.assertEqual(len(api.writes),before)
    run();self.assertEqual(len(api.data['dcim/modules/']),3);self.assertEqual(len(api.data['dcim/interfaces/']),8)
    adopted=next(port for port in api.data['dcim/interfaces/'] if port['name']=='eth-demo0');self.assertEqual(adopted['id'],80);self.assertEqual(adopted['cable'],88);self.assertFalse(adopted['enabled'])
    self.assertIn('changed=0',run())
    # Actual manufacturer helper resolves and returns a vendor ID in the copied bundle.
    primary['tasks']=[{'name':'Ensure actual reported optic vendor','fhs_manufacturers':{'netbox_url':'{{ netbox_url }}','netbox_token':'{{ netbox_token }}','validate_certs':False,'names':['Finisar Corp']},'register':'vendors'}, {'ansible.builtin.assert':{'that':["vendors.manufacturers['Finisar Corp'] is defined"]}}]
    (bundle/'synthetic.yml').write_text(yaml.safe_dump([primary],sort_keys=False))
    before=len(api.writes);run('--check');self.assertEqual(len(api.writes),before)
    run();self.assertEqual(len([v for v in api.data['dcim/manufacturers/'] if v['name']=='Finisar Corp']),1)
    self.assertIn('changed=0',run())
  finally:server.shutdown();server.server_close();worker.join(timeout=3)
if __name__=='__main__':unittest.main()
