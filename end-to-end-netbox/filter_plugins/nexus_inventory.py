"""Normalize NX-OS show-command JSON; no device or NetBox writes."""
import json
import re
from ansible.errors import AnsibleFilterError


def clean(value):
    value = str(value or '').strip().strip('"').strip()
    return '' if value.lower() in ('n/a', 'unknown', 'not available', 'none') else value


def rows(body, table, row):
    value = body.get(table, {}).get(row, [])
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise AnsibleFilterError('Unexpected NX-OS table: ' + table)
    return value


def nexus_inventory(outputs):
    try:
        inventory, version, optics = [json.loads(v) if isinstance(v, str) else v for v in outputs]
        if not all(isinstance(v, dict) for v in (inventory, version, optics)):
            raise ValueError('Expected three JSON objects')
        if 'TABLE_inv' not in inventory or 'TABLE_interface' not in optics:
            raise ValueError('Missing inventory/transceiver table; check NX-OS command output')
        items = rows(inventory, 'TABLE_inv', 'ROW_inv')
        chassis = [v for v in items if clean(v.get('name')).lower() == 'chassis']
        if len(chassis) != 1:
            raise ValueError('Expected exactly one chassis inventory record')
        chassis = chassis[0]
        model, serial = clean(chassis.get('productid')), clean(chassis.get('serialnum'))
        os_version = clean(version.get('nxos_ver_str') or version.get('kickstart_ver_str'))
        hostname = clean(version.get('host_name'))
        if model != 'N9K-C9332D-GX2B' or not all((serial, hostname, os_version)):
            raise ValueError('Expected N9K-C9332D-GX2B with serial, hostname and NX-OS version')
        modules, bays, fans, skipped = [], set(), set(), []
        for item in items:
            name = clean(item.get('name'))
            if not re.match(r'(?i)^(?:power supply|psu|fan)\s*\d+', name):
                continue
            if re.match(r'(?i)^fan\s*\d+', name):
                fans.add(name)
            bays.add(name)
            part = clean(item.get('productid'))
            if not part:
                skipped.append(name + ': no product ID')
                continue
            modules.append(dict(bay=name, model=part, part=part, manufacturer='Cisco',
                                serial=clean(item.get('serialnum')), description=clean(item.get('desc'))))
        for item in rows(optics, 'TABLE_interface', 'ROW_interface'):
            interface = clean(item.get('interface'))
            if not re.fullmatch(r'Ethernet\d+/\d+(?:/\d+)?', interface):
                continue
            # Breakout lanes share one physical pluggable cage.
            bay = '/'.join(interface.split('/')[:2])
            bays.add(bay)
            present = clean(item.get('sfp') or item.get('qsfp') or item.get('qsfp_or_cfp')).lower()
            if present in ('not present', 'absent', 'not applicable'):
                continue
            part = clean(item.get('partnum') or item.get('vendor_part_no') or item.get('cisco_product_id'))
            if not part:
                skipped.append(interface + ': no part number; no module created')
                continue
            description = clean(item.get('type'))
            if re.search(r'(?i)(?:\bDAC\b|\bCR\d*\b|copper|twinax|CU\d)', description + ' ' + part + ' ' + clean(item.get('cisco_product_id'))):
                description += '; DAC local end only; remote termination not discovered'
            module = dict(bay=bay, model=part, part=part,
                          manufacturer=clean(item.get('name')) or 'Unknown',
                          serial=clean(item.get('serialnum') or item.get('vendor_serial_no')),
                          description=description)
            previous = next((v for v in modules if v['bay'] == bay), None)
            if previous and previous != module:
                raise ValueError('Conflicting breakout transceiver records for ' + bay)
            if not previous:
                modules.append(module)
        if len({v['bay'] for v in modules}) != len(modules):
            raise ValueError('Duplicate module bays in inventory')
        fields = dict(os_version=os_version, operating_system='Cisco NX-OS')
        bios = clean(version.get('bios_ver_str'))
        if bios:
            fields['bios_version'] = bios
        if fans:
            fields['fan_count'] = len(fans)
        else:
            skipped.append('No fan inventory records; fan count preserved')
        return dict(name=hostname, model=model, serial=serial, custom_fields=fields,
                    bays=sorted(bays), modules=modules, omissions=skipped)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise AnsibleFilterError('NX-OS inventory: ' + str(exc)) from exc


class FilterModule:
    def filters(self):
        return {'nexus_inventory': nexus_inventory}
