import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml
from test_fhs import ROOT,filters
MACMODULE='''from ansible.module_utils.basic import AnsibleModule
from pathlib import Path
import os
m=AnsibleModule(argument_spec=dict(data=dict(type="dict",required=True)))
p=Path(os.environ["RETRY_COUNT"]);attempt=int(p.read_text())+1 if p.exists() else 1;p.write_text(str(attempt))
failures=int(os.environ["RETRY_FAILURES"]);status=int(os.environ["RETRY_STATUS"])
if failures<0 or attempt<=failures:m.fail_json(msg="HTTP "+str(status)+" "+("Service Unavailable" if status==503 else "Bad Request"),status=status)
m.exit_json(changed=False)
'''
class TestRetries(unittest.TestCase):
 def test_transient_classifier_preserves_permanent_errors(self):
  for status in [502,503,504]:self.assertTrue(filters.netbox_transient(dict(failed=True,status=status)))
  for status in [400,401,403,404,500]:self.assertFalse(filters.netbox_transient(dict(failed=True,status=status)))
  self.assertTrue(filters.netbox_transient(dict(failed=True,msg='Service temporarily unavailable')))
  self.assertFalse(filters.netbox_transient(dict(failed=True,msg={'status':400,'detail':'Service temporarily unavailable'})))
  self.assertFalse(filters.netbox_transient(dict(failed=True,msg={'manufacturer':['Service unavailable is not a valid value']})))
 def run_case(self,status,failures,success,expected):
  with tempfile.TemporaryDirectory(prefix='fhs-retries-') as temp:
   root=Path(temp);modules=root/'collections/ansible_collections/netbox/netbox/plugins/modules';modules.mkdir(parents=True);(modules/'netbox_mac_address.py').write_text(MACMODULE)
   task=next(c for t in yaml.safe_load((ROOT/'tasks/apply.yml').read_text()) for c in t.get('block',[]) if c['name']=='Ensure MAC objects (NetBox 4.2+)')
   play=[dict(hosts='localhost',gather_facts=False,vars=dict(facts={'hostname':'synthetic'},discovered_interfaces=[dict(name='synthetic-port',mac='02:00:00:00:00:01')],netbox_api_retries=2,netbox_api_retry_delay=0,netbox_api_loop_pause=0),tasks=[copy.deepcopy(task)])]
   path=root/'play.yml';path.write_text(yaml.safe_dump(play));count=root/'count'
   env=dict(os.environ,ANSIBLE_LOCAL_TEMP=str(root/'local'),ANSIBLE_REMOTE_TEMP=str(root/'remote'),ANSIBLE_COLLECTIONS_PATH=str(root/'collections'),ANSIBLE_FILTER_PLUGINS=str(ROOT/'filter_plugins'),RETRY_COUNT=str(count),RETRY_STATUS=str(status),RETRY_FAILURES=str(failures))
   result=subprocess.run([str(Path(sys.executable).with_name('ansible-playbook')),'-i','localhost,','-c','local',str(path)],env=env,capture_output=True,text=True,timeout=30)
   self.assertEqual(result.returncode==0,success,result.stdout+result.stderr);self.assertEqual(int(count.read_text()),expected)
 def test_503_then_success(self):self.run_case(503,2,True,3)
 def test_exhaustion_is_bounded(self):self.run_case(503,-1,False,3)
 def test_permanent_400_attempted_once(self):self.run_case(400,-1,False,1)
if __name__=='__main__':unittest.main()
