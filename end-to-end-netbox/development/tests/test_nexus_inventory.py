"""Synthetic NX-OS JSON shaped after Cisco's published show-command schemas."""
import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('nexus_inventory', Path(__file__).resolve().parents[1] / 'filter_plugins/nexus_inventory.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    items = [{'name': '"Chassis"', 'productid': 'N9K-C9332D-GX2B', 'serialnum': 'DEMO-SW'}]
    items += [{'name': 'Power Supply ' + str(n), 'productid': 'DEMO-PSU', 'serialnum': 'DEMO-PSU-' + str(n)} for n in (1, 2)]
    items += [{'name': 'Fan ' + str(n), 'productid': 'DEMO-FAN', 'serialnum': 'DEMO-FAN-' + str(n)} for n in range(1, 7)]
    optics = [{'interface': 'Ethernet1/' + str(n), 'sfp': 'not present'} for n in range(1, 35)]
    optics[0].update(sfp='present', type='QSFP-DD-400G-LR8', partnum='DEMO-QSFP', serialnum='DEMO-OPTIC', name='Cisco')
    optics[1].update(sfp='present', type='QSFP-100G-CR4', partnum='DEMO-DAC', serialnum='DEMO-CABLE', name='Vendor')
    return [{'TABLE_inv': {'ROW_inv': items}}, {'host_name': 'DEMO-NEXUS', 'nxos_ver_str': '10.3(6)', 'bios_ver_str': '01.02'}, {'TABLE_interface': {'ROW_interface': optics}}]


class TestNexus(unittest.TestCase):
    def test_all_ports_modules_and_versions(self):
        result = module.nexus_inventory(fixture())
        self.assertEqual(result['custom_fields'], dict(os_version='10.3(6)', operating_system='Cisco NX-OS', bios_version='01.02', fan_count=6))
        self.assertEqual(len(result['bays']), 42)
        self.assertEqual(len(result['modules']), 10)
        self.assertEqual([v['serial'] for v in result['modules'][:2]], ['DEMO-PSU-1', 'DEMO-PSU-2'])
        self.assertIn('DAC local end', result['modules'][-1]['description'])

    def test_singleton_tables(self):
        data = fixture()
        data[0]['TABLE_inv']['ROW_inv'] = data[0]['TABLE_inv']['ROW_inv'][0]
        data[2]['TABLE_interface']['ROW_interface'] = data[2]['TABLE_interface']['ROW_interface'][0]
        result = module.nexus_inventory(data)
        self.assertNotIn('fan_count', result['custom_fields'])
        self.assertEqual(len(result['modules']), 1)

    def test_missing_fields_preserved(self):
        data = fixture()
        del data[1]['bios_ver_str']
        del data[2]['TABLE_interface']['ROW_interface'][0]['serialnum']
        result = module.nexus_inventory(data)
        self.assertNotIn('bios_version', result['custom_fields'])
        self.assertEqual(result['modules'][-2]['serial'], '')

    def test_breakout_deduplicated(self):
        data = fixture()
        row = data[2]['TABLE_interface']['ROW_interface'][0]
        row['interface'] = 'Ethernet1/1/1'
        lane = copy.deepcopy(row)
        lane['interface'] = 'Ethernet1/1/2'
        data[2]['TABLE_interface']['ROW_interface'].append(lane)
        self.assertEqual(len(module.nexus_inventory(data)['modules']), 10)
        lane['serialnum'] = 'DIFFERENT'
        with self.assertRaises(module.AnsibleFilterError):
            module.nexus_inventory(data)

    def test_bad_identity_or_schema_rejected(self):
        for alteration in ('model', 'serial', 'table'):
            data = fixture()
            if alteration == 'table':
                data[2] = {}
            else:
                data[0]['TABLE_inv']['ROW_inv'][0]['productid' if alteration == 'model' else 'serialnum'] = ''
            with self.assertRaises(module.AnsibleFilterError):
                module.nexus_inventory(data)

    def test_missing_optic_part_reported_not_invented(self):
        data = fixture()
        del data[2]['TABLE_interface']['ROW_interface'][0]['partnum']
        result = module.nexus_inventory(data)
        self.assertEqual(len(result['modules']), 9)
        self.assertTrue(any('no part number' in v for v in result['omissions']))


if __name__ == '__main__':
    unittest.main()
