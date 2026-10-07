import importlib.util
from pathlib import Path
import copy
import yaml
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
import ansible.module_utils
ansible.module_utils.__path__.append(str(ROOT/'module_utils'))
filters=load('fhs_filters',ROOT/'filter_plugins/fhs_inventory.py')
sync=load('fhs_sync',ROOT/'library/fhs_fpga_sync.py')
TEXT='''IA-860M 123456
  Index : 2
  Part Number : IA-860M-PN
  Version : 4
  BMC Version : 2.5
IA-860M 654321
  Index : 4
  Part Number : IA-860M-PN
  Version : 4
  BMC Version : 2.6
'''
PATTERNS=[r'^\s*Index\s*:\s*(\d+)$',r'^IA-860M (\d+)$',r'^  Part Number\s+:\s+(.+)$',r'^  Version\s+:\s+(.+)$',r'^  BMC Version\s+:\s+(.+)$']
class FakeResponse:
    def __init__(self,data,status=200):self.data=data;self.status_code=status;self.ok=status<400
    def json(self):return copy.deepcopy(self.data)
class API:
    def __init__(self):
        self.headers={};self.verify=True;self.writes=[];self.next=100
        self.data={'dcim/devices/':[dict(id=1,name='host')], 'dcim/interfaces/':[dict(id=9,device=1,name='C2-QSFP0',module=None,type='other',enabled=False,custom_fields={},cable=77)]}
    def request(self,method,url,params=None,json=None,timeout=None):
        path=url.split('/api/',1)[1];parts=path.rstrip('/').split('/');ident=None
        if parts[-1].isdigit():ident=int(parts.pop());path='/'.join(parts)+'/'
        records=self.data.setdefault(path,[])
        if method=='GET':
            def matches(r):
                for k,v in (params or {}).items():
                    if k=='limit':continue
                    key=k[:-3] if k.endswith('_id') else k
                    if str(sync.scalar(r.get(key)))!=str(v):return False
                return True
            result=[r for r in records if matches(r)]
            return FakeResponse({'count':len(result),'results':result})
        self.writes.append((method,path,copy.deepcopy(json)))
        if method=='POST':
            self.next+=1;record=dict(json,id=self.next);records.append(record)
            if path=='dcim/modules/':
                # Staging type is empty: automatic replication must never collide.
                templates=[t for t in self.data.get('dcim/interface-templates/',[]) if t.get('module_type')==json['module_type']]
                assert not templates,'New module would duplicate existing template interfaces'
            return FakeResponse(record,201)
        assert method=='PATCH','No deletes allowed'
        record=next(r for r in records if r['id']==ident);record.update(json);return FakeResponse(record)
class Tests(unittest.TestCase):
    def cards(self):return filters.modules(filters.cards(TEXT,*PATTERNS,{2:[{'address':'0000:01:00.0','function':'Arkville'}]})['cards'],'400gbase-x-qsfpdd')
    def test_block_boundaries_and_actual_indices(self):
        cards=self.cards();self.assertEqual(cards[0]['interfaces'][0]['name'],'C2-QSFP0');self.assertEqual(cards[1]['interfaces'][2]['name'],'C4-QSFP2')
        self.assertEqual(cards[0]['pci_endpoints'][0]['address'],'0000:01:00.0')
        with self.assertRaises(Exception):filters.cards(TEXT.replace('  BMC Version : 2.5\n',''),*PATTERNS,{})
    def test_packaged_patterns_match_working_source_whitespace(self):
        variables=yaml.safe_load((ROOT/'netbox_import.yml').read_text())[0]['vars']
        patterns=[variables['bootstrap_bittware_'+name+'_pattern'] for name in ['index','serial','part','version','bmc_firmware']]
        text=TEXT.replace('  ', '    ').replace('Index : 2', 'Index : 2   (USB)').replace('Index : 4', 'Index : 4   ')
        records=filters.cards(text,*patterns,{})['cards']
        self.assertEqual([record['card_index'] for record in records],[2,4])
        self.assertEqual(records[0]['bmc_firmware'],'2.5')
        with self.assertRaisesRegex(Exception,'missing or unmatched fields: BMC Version'):
            filters.cards(text.replace('    BMC Version : 2.5\n',''),*patterns,{})

    def test_actual_sample_shape_preserves_full_alphanumeric_serial(self):
        variables=yaml.safe_load((ROOT/'netbox_import.yml').read_text())[0]['vars']
        patterns=[variables['bootstrap_bittware_'+name+'_pattern'] for name in ['index','serial','part','version','bmc_firmware']]
        text=(ROOT/'tests/fixtures/bw_card_list.txt').read_text()
        parsed=filters.cards(text,*patterns,{})
        self.assertTrue(parsed['warnings'])
        records=parsed['cards']
        self.assertEqual([record['serial'] for record in records],['900AAAA','900AAAA'])
        self.assertEqual([record['card_index'] for record in records],[0,1])
        self.assertEqual([record['bmc_firmware'] for record in records],['1.1.2-3','1.1.2-3'])
        self.assertEqual(len(filters.modules(records,'400gbase-x-qsfpdd')[0]['interfaces']),3)

    def test_vpd_multiple_functions_preserves_missing(self):
        records=[{'name':'NIC a','part':'existing','serial':'old'},{'name':'NIC b','part':'','serial':''}]
        probes=[{'nic_item':records[0],'stdout':'[SN] Serial number: A'}, {'nic_item':records[1],'stdout':'[PN] Part number: B\n[SN] Serial number: BB'}]
        result=filters.vpd(records,probes);self.assertEqual(result[0]['part'],'existing');self.assertEqual(result[1]['serial'],'BB')
    def test_check_apply_repeat_and_adoption(self):
        api=API();params=dict(netbox_url='http://test.invalid',netbox_token='synthetic',validate_certs=False,device='host',cards=self.cards())
        with patch.object(sync.requests,'Session',return_value=api):
            plan=sync.synchronize(params,True);self.assertTrue(plan);self.assertFalse(api.writes)
            sync.synchronize(params,False)
            iface=api.data['dcim/interfaces/'][0];self.assertEqual(iface['id'],9);self.assertEqual(iface['cable'],77);self.assertFalse(iface['enabled']);self.assertEqual(iface['type'],'other');self.assertIsNotNone(iface['module'])
            self.assertEqual(len(api.data['dcim/modules/']),2);self.assertEqual(len(api.data['dcim/interfaces/']),6);self.assertEqual(len(api.data['dcim/interface-templates/']),3)
            self.assertEqual(sync.synchronize(params,False),[])
            params['cards'][0]['bmc_firmware']='new'
            before=len(api.writes);plan=sync.synchronize(params,True);self.assertEqual(len(api.writes),before);self.assertTrue(any(x['action']=='update' for x in plan))
    def test_refuses_foreign_module_without_writes(self):
        api=API();api.data['dcim/interfaces/'][0]['module']=99
        params=dict(netbox_url='http://test.invalid',netbox_token='synthetic',validate_certs=False,device='host',cards=self.cards())
        with patch.object(sync.requests,'Session',return_value=api):
            with self.assertRaises(ValueError):sync.synchronize(params,False)
        self.assertFalse(api.writes)
if __name__=='__main__':unittest.main()
