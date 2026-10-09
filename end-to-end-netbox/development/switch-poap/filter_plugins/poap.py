"""Strict normalization for the read-only NetBox switch POAP export."""
import hashlib
import ipaddress
import re


def cli_token(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.@!+:/=-]+', value):
        raise ValueError('NX-OS configuration values must be nonempty single safe tokens')
    return value


def switch_record(device, interface, addresses, gateway):
    primary = interface.get('primary_mac_address') or {}
    mac = primary.get('mac_address') or interface.get('mac_address') or ''
    mac = mac.lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac):
        raise ValueError('Management interface needs a valid primary MAC in NetBox')
    if mac == '00:00:00:00:00:00' or int(mac[:2], 16) & 1:
        raise ValueError('Management MAC must be a nonzero unicast address')
    ipv4 = []
    for record in addresses:
        parsed = ipaddress.ip_interface(record['address'])
        if parsed.version == 4:
            ipv4.append(parsed)
    if len(ipv4) != 1:
        raise ValueError('Management interface needs exactly one assigned IPv4 address')
    address = ipv4[0]
    gateway_ip = ipaddress.IPv4Address(gateway)
    if gateway_ip not in address.network or gateway_ip == address.ip:
        raise ValueError('Management gateway must be in the interface subnet and differ from its IP')
    for ip in (address.ip, gateway_ip):
        if ip.is_multicast or ip.is_unspecified or ip == address.network.broadcast_address or ip == address.network.network_address:
            raise ValueError('Management IP and gateway must be usable host addresses')
    name = device.get('name', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise ValueError('NetBox device name must be a safe NX-OS hostname')
    return dict(serial=cli_token(device['serial']), name=name, mac=mac,
                address=str(address), gateway=str(gateway_ip))


def validate_switches(records):
    if not records:
        raise ValueError('No switches selected')
    for key in ('serial', 'name', 'mac', 'address'):
        values = [record[key] for record in records]
        if len(values) != len(set(values)):
            raise ValueError('Selected switches have duplicate ' + key)
    ips = [str(ipaddress.ip_interface(record['address']).ip) for record in records]
    if len(ips) != len(set(ips)):
        raise ValueError('Selected switches have duplicate management IPs')
    return sorted(records, key=lambda record: record['serial'])


def checksum(body):
    # Cisco verifies MD5 over script bytes excluding the #md5sum line.
    body = body.rstrip('\n') + '\n'
    digest = hashlib.md5(body.encode('utf-8')).hexdigest()
    first, rest = body.split('\n', 1)
    return first + '\n#md5sum="' + digest + '"\n' + rest


class FilterModule:
    def filters(self):
        return dict(poap_cli_token=cli_token, poap_switch_record=switch_record,
                    poap_validate_switches=validate_switches, poap_checksum=checksum)
