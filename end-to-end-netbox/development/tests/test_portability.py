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
  api=API()
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
    sdk=root/'synthetic-sdk.py';sdk.write_text('print('+repr(TEXT)+')')
    # Keep adjacent filter/library discovery, relative includes and all working defaults.
    primary=yaml.safe_load((bundle/'netbox_import.yml').read_text())[0]
    primary['hosts']='localhost';primary['connection']='local';primary.pop('vars_files')
    primary['vars'].update(netbox_url='http://127.0.0.1:'+str(server.server_port),netbox_token='synthetic-only',ansible_python_interpreter=sys.executable,
                           bootstrap_bittware_card_list_argv=[sys.executable,str(sdk)],facts={'hostname':'host'})
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
    run('--check','--diff');self.assertFalse(api.writes)
    run();self.assertEqual(len(api.data['dcim/modules/']),2);self.assertEqual(len(api.data['dcim/interfaces/']),6)
    self.assertIn('changed=0',run())
  finally:server.shutdown();server.server_close();worker.join(timeout=3)
if __name__=='__main__':unittest.main()
