#!/usr/bin/env python3
"""Verify the local simulated demo against NetBox; never collect real hardware."""
import argparse
import json
import ipaddress
from pathlib import Path
import re
import subprocess

import requests

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--skip-runs', action='store_true', help='Only inspect already-populated NetBox')
args = parser.parse_args()
credentials = json.loads((ROOT / 'private/netbox.json').read_text())
session = requests.Session()
session.headers['Authorization'] = 'Bearer ' + credentials['netbox_token']

def records(endpoint, **params):
    response = session.get(credentials['netbox_url'] + '/api/' + endpoint + '/', params={'limit': 1000, **params}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    assert payload['next'] is None, 'Demo verification expects fewer than 1000 records'
    return payload['results']

def snapshot():
    endpoints = ['dcim/devices', 'dcim/interfaces', 'dcim/mac-addresses', 'dcim/inventory-items', 'ipam/ip-addresses', 'dcim/sites', 'dcim/device-roles', 'dcim/manufacturers', 'dcim/device-types', 'extras/custom-fields', 'extras/tags', 'core/object-changes']
    return {endpoint: records(endpoint) for endpoint in endpoints}

name = 'netbox-demo-ubuntu'
[device] = records('dcim/devices', name=name)
expected_fields = {
    'os_version': 'Ubuntu 24.04', 'bios_version': '2.1a', 'bmc_firmware': '1.74',
    'motherboard_part_number': 'MBD-X13DEI-B', 'motherboard_serial': 'DEMO-MB-0001',
}
for field, value in expected_fields.items():
    assert device['custom_fields'][field] == value, field
assert 'simulated-hardware' in [tag['name'] for tag in device['tags']]
assert device['oob_ip']['address'] == '192.0.2.50/32'
expected_components = {
    'DDR5 DIMM_A1': ('M321R4GA0BB0-CQK', 'DEMO-DDR5-0001'),
    'DDR5 DIMM_B1': ('M321R4GA0BB0-CQK', 'DEMO-DDR5-0002'),
    'DDR5 DIMM_C1': ('M321R4GA0BB0-CQK', 'DEMO-DDR5-0003'),
    'DDR5 DIMM_D1': ('M321R4GA0BB0-CQK', 'DEMO-DDR5-0004'),
    'DDR5 DIMM_SHARED [CPU0_BANK]': ('M321R4GA0BB0-CQK', 'DEMO-DDR5-0005'),
    'DDR5 DIMM_SHARED [CPU1_BANK]': ('M321R4GA0BB0-CQK', 'DEMO-DDR5-0006'),
    'NVMe /dev/nvme0n1': ('MZQL23T8HCLS-00A07', 'DEMO-NVME-0001'),
    'NVMe /dev/nvme1n1': ('MZQL23T8HCLS-00A07', 'DEMO-NVME-0002'),
    'NVMe /dev/nvme2n1': ('MZQL23T8HCLS-00A07', 'DEMO-NVME-0003'),
    'NVMe /dev/nvme3n1': ('MZQL23T8HCLS-00A07', 'DEMO-NVME-0004'),
}
items = {item['name']: item for item in records('dcim/inventory-items', device=name)}
assert set(items) == set(expected_components), 'Unexpected/empty memory slot component'
for item_name, (part, serial) in expected_components.items():
    item = items[item_name]
    assert (item['part_id'], item['serial']) == (part, serial), item_name
    assert item['description'].startswith('SIMULATED fixture:'), item_name
    assert not item['custom_fields'], 'No storage/memory firmware or IP custom fields expected'
interfaces = {interface['name']: interface for interface in records('dcim/interfaces', device=name)}
assert set(interfaces) == {'eth0', 'lo', 'bmc'}
addresses = {address['address']: address for address in records('ipam/ip-addresses', device=name)}
assert addresses['192.0.2.50/32']['assigned_object']['name'] == 'bmc'
assert interfaces['eth0']['primary_mac_address'] is not None
assert interfaces['lo']['primary_mac_address'] is None

if not args.skip_runs:
    fact_dir = ROOT / 'private' / 'verification-facts'
    fact_result = subprocess.run([str(ROOT.parent / '.venv/bin/ansible'), '-i', 'inventory.yml', 'bootstrap_servers', '-m', 'ansible.builtin.setup', '--tree', str(fact_dir)], cwd=ROOT, capture_output=True, text=True)
    assert fact_result.returncode == 0, 'SSH fact gathering failed'
    facts = json.loads((fact_dir / '127.0.0.1').read_text())['ansible_facts']
    assert device['primary_ip4']['address'].split('/')[0] == facts['ansible_eth0']['ipv4']['address']
    assert device['name'] == facts['ansible_hostname']
    assert device['custom_fields']['os_version'] == facts['ansible_distribution'] + ' ' + facts['ansible_distribution_version']
    for interface_name in facts['ansible_interfaces']:
        observed = facts['ansible_' + interface_name.replace('-', '_')]
        mac = observed.get('macaddress', '')
        if mac and mac != '00:00:00:00:00:00':
            assert interfaces[interface_name]['primary_mac_address']['mac_address'].upper() == mac.upper()
        observed_addresses = ([observed['ipv4']] if 'ipv4' in observed else []) + observed.get('ipv4_secondaries', []) + observed.get('ipv6', [])
        for address in observed_addresses:
            canonical = str(ipaddress.ip_interface(address['address'] + '/' + str(address['prefix'])))
            assert addresses[canonical]['assigned_object']['name'] == interface_name
    before = snapshot()
    executable = str(ROOT.parent / '.venv/bin/ansible-playbook')
    modes = {'repeat-apply': [], 'preview': ['--check'], 'facts-only': ['--tags', 'facts'], 'compare-only': ['--tags', 'compare']}
    for label, flags in modes.items():
        result = subprocess.run([executable, '-i', 'inventory.yml', 'bootstrap.yml', *flags], cwd=ROOT, capture_output=True, text=True)
        (ROOT / 'private' / (label + '-verification.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, label + ' failed; inspect its private log'
        assert re.search(r'changed=0\s+unreachable=0\s+failed=0', result.stdout), label + ' was not clean'
        assert snapshot() == before, label + ' changed NetBox inventory or its change log'
print('Verified simulated hardware mappings and labels.' if args.skip_runs else 'Verified simulated hardware mappings, repeat apply, and no-write preview/facts/compare modes.')
