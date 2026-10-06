"""Verify explicitly synthetic items in the dedicated NetBox demo; no writes."""
import argparse
import json
from pathlib import Path
import requests

parser = argparse.ArgumentParser()
parser.add_argument('--credentials', default='private/netbox.json')
parser.add_argument('--snapshot')
parser.add_argument('--compare-snapshot')
args = parser.parse_args()
credentials = json.loads(Path(args.credentials).read_text())
token = credentials['netbox_token']
response = requests.get(credentials['netbox_url'].rstrip('/') + '/api/dcim/inventory-items/',
                        params={'device': 'netbox-demo-ubuntu', 'limit': 1000},
                        headers={'Authorization': ('Bearer ' if token.startswith('nbt_') else 'Token ') + token},
                        verify=credentials.get('netbox_validate_certs', False), timeout=30)
response.raise_for_status()
items = {item['name']: item for item in response.json()['results']}
expected = {'FPGA card 0': ('SIM-FPGA-0001', 'SIM-1.2.3', ['0000:21:00.0', '0000:65:00.0']),
            'FPGA card 1': ('SIM-FPGA-0002', 'SIM-4.5.6', ['0000:42:00.0', '0000:87:00.0']),
            'NIC 0000:a1:00.0': ('SIM-NIC-0001', None, ['0000:a1:00.0'])}
snapshot = {}
for name, (serial, firmware, bdfs) in expected.items():
    item = items[name]
    assert item['serial'] == serial, name
    assert item['custom_fields'].get('fpga_bmc_firmware') == firmware, name
    assert [e['address'] for e in item['custom_fields']['pci_endpoints']] == bdfs, name
    assert all('vendor_id' in e and 'device_id' in e and e['label'] for e in item['custom_fields']['pci_endpoints']), name
    snapshot[name] = item
if args.compare_snapshot:
    assert snapshot == json.loads(Path(args.compare_snapshot).read_text()), 'Repeat changed inventory items'
if args.snapshot:
    Path(args.snapshot).write_text(json.dumps(snapshot, sort_keys=True))
print('Synthetic FPGA serials, per-card firmware and separate NIC PCI metadata verified.')
