"""Normalize observed FHS output; do not infer PCI association from product names."""
import re
from ansible.errors import AnsibleFilterError


def first(text, pattern):
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else ''


def cards(text, index_pattern, serial_pattern, part_pattern, version_pattern, firmware_pattern, pci_map):
    # Serial headings delimit records: missing fields cannot bleed into the next card.
    headings = list(re.finditer(serial_pattern, text, re.MULTILINE))
    result = []
    for pos, heading in enumerate(headings):
        block = text[heading.start():headings[pos + 1].start() if pos + 1 < len(headings) else len(text)]
        index = first(block, index_pattern)
        part = first(block, part_pattern)
        firmware = first(block, firmware_pattern)
        if not index.isdigit() or not part or not firmware:
            raise AnsibleFilterError('Incomplete FPGA card record; review SDK output and patterns')
        endpoints = pci_map.get(index, pci_map.get(int(index), []))
        for endpoint in endpoints:
            if not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]', endpoint.get('address', '')):
                raise AnsibleFilterError('Invalid explicit FPGA PCI address')
        result.append(dict(name='CARD '+index, serial=heading.group(1).strip(), card_index=int(index),
                           part=part, version=first(block, version_pattern), bmc_firmware=firmware,
                           pci_endpoints=endpoints))
    if len({c['card_index'] for c in result}) != len(result) or len({c['serial'] for c in result}) != len(result):
        raise AnsibleFilterError('Duplicate FPGA card index or serial')
    return {'cards': result}


def modules(records, interface_type):
    result = []
    for record in records:
        index = record.get('card_index', record.get('index'))
        if index is None or not str(index).isdigit():
            raise AnsibleFilterError('Every FPGA needs its actual card_index')
        if not record.get('part') or not record.get('serial'):
            raise AnsibleFilterError('FPGA module needs a discovered part and serial')
        result.append(dict(record, bay='FPGA CARD '+str(index), position=str(index),
                           interfaces=[dict(name=f'C{index}-QSFP{port}', type=interface_type) for port in range(3)]))
    if len({r['bay'] for r in result}) != len(result):
        raise AnsibleFilterError('FPGA module bays collide')
    return result


def vpd(components, probes):
    observations = {p['nic_item']['name']:p.get('stdout','') for p in probes if not p.get('skipped') and p.get('rc',0)==0}
    result=[]
    for component in components:
        item=dict(component)
        raw=observations.get(item['name'],'')
        for key, pattern in [('part',r'\[PN\]\s+Part number:\s*(\S+)'),('serial',r'\[SN\]\s+Serial number:\s*(\S+)')]:
            value=first(raw,pattern)
            if value:item[key]=value
        result.append(item)
    return result


class FilterModule:
    def filters(self):
        return {'fhs_fpga_cards':cards,'fhs_fpga_modules':modules,'fhs_nic_vpd':vpd}
