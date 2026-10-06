#!/usr/bin/env python3
"""Read-only BMC display adapter; real commands and output patterns are user supplied."""
import argparse
import json
import re
import subprocess

BDF = re.compile(r'^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$')

def run(argv):
    return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=30).stdout

def extract(text, pattern, field):
    matches = re.findall(pattern, text, re.MULTILINE)
    if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0].strip():
        raise ValueError(f'{field} pattern must capture exactly one nonempty value')
    return matches[0].strip()

def parse_pci(text, keywords):
    endpoints = []
    for line in text.splitlines():
        address, _, label = line.partition(' ')
        if not BDF.fullmatch(address):
            continue
        ids = re.findall(r'\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]', label)
        endpoint = {'address': address.lower(), 'label': label.strip(), 'matches_keywords': any(k.lower() in label.lower() for k in keywords)}
        if ids:
            endpoint.update(vendor_id=ids[-1][0].lower(), device_id=ids[-1][1].lower())
        endpoints.append(endpoint)
    return endpoints

def discover(config):
    pci = parse_pci(run(config['pci_list_argv']), config['pci_keywords'])
    cards, assigned = [], set()
    for mapping in config['cards']:
        index = mapping['index']
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError('Card index must be a nonnegative integer')
        argv = [str(arg).replace('{card}', str(index)) for arg in config['bmc_display_argv']]
        output = run(argv)
        endpoints = []
        for entry in mapping.get('pci_endpoints', []):
            address = entry['address'].lower()
            if not BDF.fullmatch(address) or address in assigned:
                raise ValueError('PCI endpoint must be a unique full domain:bus:device.function')
            observed = next((p for p in pci if p['address'] == address), None)
            if observed is None:
                raise ValueError('Configured PCI endpoint absent from current PCI inventory: ' + address)
            assigned.add(address)
            endpoints.append(dict(observed, function=entry['function'], association='configured-card-index'))
        cards.append({'name': mapping.get('name', 'card ' + str(index)), 'card_index': index,
                      'serial': extract(output, config['serial_pattern'], 'serial'),
                      'bmc_firmware': extract(output, config['firmware_pattern'], 'firmware'),
                      'part': mapping.get('part', ''), 'pci_endpoints': endpoints})
    if len({c['card_index'] for c in cards}) != len(cards) or len({c['serial'] for c in cards}) != len(cards):
        raise ValueError('Duplicate card serial or index')
    return {'cards': cards, 'unassociated_pci_endpoints': [p for p in pci if p['address'] not in assigned and p['matches_keywords']]}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-json', required=True)
    args = parser.parse_args()
    print(json.dumps(discover(json.loads(args.config_json))))
