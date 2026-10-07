import importlib
import json
import os
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import threading
import yaml
from http.server import BaseHTTPRequestHandler,HTTPServer
import unittest
from unittest.mock import patch
from test_fhs import ROOT,API,FakeResponse,load,sync
helper=load('fhs_module_types',ROOT/'library/fhs_module_types.py')
class StrictAPI(API):
 def __init__(self):super().__init__();self.queries=[]
 def request(self,method,url,params=None,json=None,timeout=None):
  if method=='GET' and '/api/dcim/module-types/' in url:
   self.queries.append(dict(params or {}))
   if str((params or {}).get('manufacturer','')).isdigit():
    return FakeResponse({'manufacturer':['Select a valid choice. 5 is not one of the available choices.']},400)
  return super().request(method,url,params=params,json=json,timeout=timeout)
class TestModuleTypeContract(unittest.TestCase):
 def test_real_collection_lookup_uses_slug_filter_for_numeric_id(self):
  # Resolve the controller's declared collection from standard project paths.
  candidates=[Path(value) for value in os.environ.get('ANSIBLE_COLLECTIONS_PATH','').split(os.pathsep) if value]
  for parent in ROOT.parents:candidates.extend([parent/'collections',parent/'.ansible/collections'])
  collection=next((path for path in candidates if (path/'ansible_collections/netbox/netbox/plugins/module_utils/netbox_utils.py').exists()),None)
  if collection is None:self.skipTest('Declared netbox.netbox collection is not installed on this test controller')
  sys.path.insert(0,str(collection))
  actual=importlib.import_module('ansible_collections.netbox.netbox.plugins.module_utils.netbox_utils')
  builder=object.__new__(actual.NetboxModule);builder.api_version='4.3';builder.endpoint='module_types'
  query=builder._build_query_params('module_type',dict(manufacturer=5,model='SAMPLE'),['manufacturer','model'])
  self.assertEqual(query,dict(manufacturer=5,model='SAMPLE'))
  api=StrictAPI();response=api.request('GET','http://local/api/dcim/module-types/',params=query);self.assertEqual(response.status_code,400)
 def test_installed_module_uses_collection_default_id_filters(self):
  candidates=[]
  for parent in ROOT.parents:candidates.extend([parent/'collections',parent/'.ansible/collections'])
  collection=next((path for path in candidates if (path/'ansible_collections/netbox/netbox/plugins/module_utils/netbox_utils.py').exists()),None)
  if collection is None:self.skipTest('Declared collection not installed')
  sys.path.insert(0,str(collection));actual=importlib.import_module('ansible_collections.netbox.netbox.plugins.module_utils.netbox_utils')
  builder=object.__new__(actual.NetboxModule);builder.api_version='4.3';builder.endpoint='modules'
  tasks=[child for task in yaml.safe_load((ROOT/'netbox_import_nexus.yml').read_text())[0]['tasks'] for child in task.get('block',[])]
  installed=next(task for task in tasks if 'netbox.netbox.netbox_module' in task)
  query=builder._build_query_params('module',dict(device=1,module_bay=2,module_type=3),installed.get('query_params'))
  self.assertEqual(query,dict(device_id=1,module_bay_id=2,module_type_id=3))
 def test_correct_id_filter_create_repeat_and_preview(self):
  api=StrictAPI();params=dict(netbox_url='http://local',netbox_token='synthetic',validate_certs=False,manufacturers={'Cisco':5,'Finisar Corp':7},types=[dict(manufacturer='Cisco',model='SAME',part='SAME'),dict(manufacturer='Finisar Corp',model='SAME',part='SAME')])
  with patch.object(sync.requests,'Session',return_value=api):
   ids,plan=helper.synchronize(params,True);self.assertTrue(plan);self.assertFalse(api.writes)
   ids,plan=helper.synchronize(params,False);self.assertTrue(plan);self.assertEqual(len(ids),2);self.assertNotEqual(ids[json.dumps(['Cisco','SAME'])],ids[json.dumps(['Finisar Corp','SAME'])])
   self.assertTrue(all('manufacturer_id' in query and 'manufacturer' not in query for query in api.queries))
   self.assertTrue(all(isinstance(body['manufacturer'],int) for method,path,body in api.writes if path=='dcim/module-types/'))
   again,plan=helper.synchronize(params,False);self.assertFalse(plan);self.assertEqual(again,ids)
 def test_actual_helper_copied_layout(self):
  api=StrictAPI()
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def serve(self):
    from urllib.parse import urlsplit,parse_qs
    parsed=urlsplit(self.path);params={k:v[0] for k,v in parse_qs(parsed.query).items()};length=int(self.headers.get('Content-Length',0));body=json.loads(self.rfile.read(length)) if length else None
    response=api.request(self.command,'http://local'+parsed.path,params=params,json=body);payload=json.dumps(response.json()).encode();self.send_response(response.status_code);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
   do_GET=serve;do_POST=serve;do_PATCH=serve
  server=HTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  try:
   with tempfile.TemporaryDirectory(prefix='module-type-copy-') as temp:
    root=Path(temp);bundle=root/'ska/playbooks/development';shutil.copytree(ROOT,bundle)
    play=[dict(hosts='localhost',gather_facts=False,vars={'ansible_python_interpreter':sys.executable},tasks=[{'fhs_module_types':dict(netbox_url='http://127.0.0.1:'+str(server.server_port),netbox_token='synthetic',validate_certs=False,manufacturers={'Cisco':5,'Finisar Corp':7},types=[dict(manufacturer='Cisco',model='SAME',part='SAME'),dict(manufacturer='Finisar Corp',model='SAME',part='SAME')]),'register':'result'},{'ansible.builtin.assert':{'that':["result.module_types | length == 2"]}}])]
    path=bundle/'contract.yml';path.write_text(yaml.safe_dump(play));env=dict(os.environ,ANSIBLE_LOCAL_TEMP=str(root/'local'),ANSIBLE_REMOTE_TEMP=str(root/'remote'))
    def run(*args):
     result=subprocess.run([str(Path(sys.executable).with_name('ansible-playbook')),'-i','localhost,','-c','local',str(path),*args],env=env,capture_output=True,text=True,timeout=30);self.assertEqual(result.returncode,0,result.stdout+result.stderr);return result.stdout
    run('--check');self.assertFalse(api.writes)
    run();self.assertEqual(len(api.data['dcim/module-types/']),2);self.assertIn('changed=0',run())
    self.assertTrue(all('manufacturer_id' in query and 'manufacturer' not in query for query in api.queries))
  finally:server.shutdown();server.server_close();worker.join(timeout=3)
if __name__=='__main__':unittest.main()
