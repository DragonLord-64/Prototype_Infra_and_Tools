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
        missing = [name for name, valid in [('Index', index.isdigit()), ('Part Number', bool(part)), ('BMC Version', bool(firmware))] if not valid]
        if missing:
            raise AnsibleFilterError('Incomplete FPGA card record '+str(pos + 1)+'; missing or unmatched fields: '+', '.join(missing)+'; check configured output patterns')
        endpoints = pci_map.get(index, pci_map.get(int(index), []))
        for endpoint in endpoints:
            if not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]', endpoint.get('address', '')):
                raise AnsibleFilterError('Invalid explicit FPGA PCI address')
        result.append(dict(name='CARD '+index, serial=heading.group(1).strip(), card_index=int(index),
                           part=part, version=first(block, version_pattern), bmc_firmware=firmware,
                           pci_endpoints=endpoints))
    if len({c['card_index'] for c in result}) != len(result):
        raise AnsibleFilterError('Duplicate FPGA card index')
    warnings = ['SDK reports repeated serials for distinct card indices; preserving reported values and using module bays for identity'] if len({c['serial'] for c in result}) != len(result) else []
    return {'cards': result, 'warnings': warnings}


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

def nic_candidates(candidates, vf_probes, name_probes):
    import base64
    virtual={p['item']['interface'] for p in vf_probes if p.get('stat',{}).get('exists')}
    names={p['item']['interface']:base64.b64decode(p.get('content','')).decode('utf-8',errors='replace').strip() for p in name_probes}
    return [dict(p,physical_port_name=names.get(p['interface'],'')) for p in candidates
            if p['interface'] not in virtual and not re.match(r'^(?:p\d+)?(?:pf\d+)?(?:vf|sf)\d+',names.get(p['interface'],''))]


def nic_cards(ports, driver_probes, link_probes, identity_probes, drivers, part_pattern, serial_pattern):
    def observations(probes,key):
        return {p['item'][key]:p.get('stdout','') for p in probes if not p.get('skipped') and p.get('rc',1)==0}
    driver_texts=observations(driver_probes,'interface')
    links=observations(link_probes,'interface')
    identities=observations(identity_probes,'address')
    groups={};warnings=[]
    missing={'','unknown','none','n/a','unavailable','not','not_specified','000000','00000000'}
    for port in ports:
        interface=port['interface'];address=port['address'].lower();text=driver_texts.get(interface,'')
        values={key:value.strip() for key,value in re.findall(r'^([^:\n]+):[ \t]*(.*)$',text,re.MULTILINE)}
        driver=values.get('driver','')
        if not driver or drivers and driver not in drivers:
            warnings.append(interface+': driver unavailable or outside selected NIC drivers; existing data preserved');continue
        if values.get('bus-info','').lower()!=address:
            warnings.append(interface+': ethtool PCI address does not match host facts; not imported');continue
        identity=identities.get(address,'');part=first(identity,part_pattern);serial=first(identity,serial_pattern)
        if part.lower() in missing or serial.lower() in missing:
            warnings.append(interface+': physical card part/serial unavailable from VPD; no physical grouping invented');continue
        group=groups.setdefault((part,serial),dict(part=part,serial=serial,interfaces=[],functions=[]))
        group['interfaces'].append(dict(name=interface,type='other'))
        link=links.get(interface,'')
        function=dict(address=address,interface=interface,driver=driver,driver_version=values.get('version',''),firmware=values.get('firmware-version',''),physical_port_name=port.get('physical_port_name',''))
        for name,pattern in [('speed',r'^\s*Speed:\s*(.+)$'),('duplex',r'^\s*Duplex:\s*(.+)$'),('link_detected',r'^\s*Link detected:\s*(.+)$')]:
            observed=first(link,pattern)
            if observed:function[name]=observed
        group['functions'].append(function)
    cards=[]
    for group in groups.values():
        group['interfaces'].sort(key=lambda p:p['name']);group['functions'].sort(key=lambda p:(p['address'],p['interface']))
        addresses=sorted({f['address'] for f in group['functions']});position=addresses[0]
        cards.append(dict(group,bay='NIC '+position,position=position,
                          driver=', '.join(sorted({f['driver'] for f in group['functions'] if f['driver']})),
                          firmware=', '.join(sorted({f['firmware'] for f in group['functions'] if f['firmware']})),
                          pci_endpoints=[dict(address=address,function='NIC') for address in addresses]))
    return dict(cards=cards,warnings=warnings)


class FilterModule:
    def filters(self):
        return {'fhs_fpga_cards':cards,'fhs_fpga_modules':modules,'fhs_nic_vpd':vpd,'fhs_nic_candidates':nic_candidates,'fhs_nic_cards':nic_cards}
