import base64
import copy
import unittest
from unittest.mock import patch
from test_fhs import filters,sync,API,ROOT
DRIVER=(ROOT/'tests/fixtures/ethtool-driver.txt').read_text()
LINK=(ROOT/'tests/fixtures/ethtool-link.txt').read_text()
VPD=(ROOT/'tests/fixtures/nic-vpd.txt').read_text()
PN=r'\[PN\]\s+Part number:\s*(\S+)';SN=r'\[SN\]\s+Serial number:\s*(\S+)'
PORTS=[dict(interface='eth-demo0',address='0000:01:00.0'),dict(interface='eth-demo1',address='0000:01:00.1')]
def discovery(ports=PORTS,identity=None,driver=None):
    dp=[dict(item=p,rc=0,stdout=(driver or DRIVER).replace('0000:01:00.0',p['address'])) for p in ports]
    ip=[dict(item=p,rc=0,stdout=(identity or {}).get(p['address'],VPD)) for p in ports]
    lp=[dict(item=p,rc=0,stdout=LINK) for p in ports]
    return filters.nic_cards(ports,dp,lp,ip,['mlx5_core'],PN,SN)
class TestNIC(unittest.TestCase):
 def test_actual_ethtool_fields_and_multi_function_grouping(self):
    result=discovery();self.assertEqual(len(result['cards']),1);card=result['cards'][0]
    self.assertEqual(card['driver'],'mlx5_core');self.assertEqual(card['firmware'],'20.31.1014 (MT_0000000223)')
    self.assertEqual(len(card['interfaces']),2);self.assertEqual(len(card['pci_endpoints']),2)
    self.assertEqual(card['functions'][0]['speed'],'200000Mb/s');self.assertEqual(card['functions'][0]['driver_version'],'6.8.0-139-generic')
 def test_adjacent_functions_do_not_prove_one_card(self):
    result=discovery(identity={'0000:01:00.1':VPD.replace('SAMPLE-CARD01','SAMPLE-CARD02')});self.assertEqual(len(result['cards']),2)
    result=discovery(identity={'0000:01:00.1':''});self.assertEqual(len(result['cards']),1);self.assertEqual(len(result['cards'][0]['interfaces']),1);self.assertTrue(result['warnings'])
 def test_mismatched_bus_info_and_virtual_ports_skipped(self):
    result=discovery(driver=DRIVER.replace('0000:01:00.0','0000:09:00.0'));self.assertFalse(result['cards'])
    ports=PORTS+[dict(interface='rep',address='0000:01:00.0'),dict(interface='rep-port-prefixed',address='0000:01:00.0')]
    vfs=[dict(item=PORTS[1],stat={'exists':True})]
    names=[dict(item=ports[-2],content=base64.b64encode(b'pf0vf7').decode()),dict(item=ports[-1],content=base64.b64encode(b'p0pf1vf2').decode())]
    self.assertEqual([p['interface'] for p in filters.nic_candidates(ports,vfs,names)],['eth-demo0'])
 def test_check_apply_repeat_adoption_and_missing_value_preservation(self):
    api=API();api.data['dcim/interfaces/'][0]['name']='eth-demo0'
    params=dict(netbox_url='http://test.invalid',netbox_token='synthetic',validate_certs=False,device='host',cards=discovery()['cards'],kind='NIC',manufacturer='Mellanox')
    with patch.object(sync.requests,'Session',return_value=api):
      self.assertTrue(sync.synchronize(params,True));self.assertFalse(api.writes)
      sync.synchronize(params,False);self.assertEqual(len(api.data['dcim/modules/']),1);self.assertEqual(len(api.data['dcim/interfaces/']),2)
      interface=api.data['dcim/interfaces/'][0];self.assertEqual(interface['id'],9);self.assertEqual(interface['cable'],77);self.assertFalse(interface['enabled']);self.assertEqual(interface['type'],'other')
      module=api.data['dcim/modules/'][0];old_bay=module['module_bay'];self.assertEqual(len(module['custom_fields']['nic_functions']),2)
      self.assertEqual(sync.synchronize(params,False),[])
      partial=discovery(ports=PORTS[1:],driver=DRIVER.replace('firmware-version: 20.31.1014 (MT_0000000223)','firmware-version: '))['cards']
      params['cards']=partial;sync.synchronize(params,False)
      self.assertEqual(len(api.data['dcim/modules/']),1);self.assertEqual(module['module_bay'],old_bay)
      self.assertEqual(module['custom_fields']['nic_firmware'],'20.31.1014 (MT_0000000223)');self.assertEqual(len(module['custom_fields']['nic_functions']),2)
      self.assertEqual(len(module['custom_fields']['pci_endpoints']),2)
if __name__=='__main__':unittest.main()
