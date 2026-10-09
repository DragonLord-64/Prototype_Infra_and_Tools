"""Offline mapping and generated-script behavior; no hardware is touched."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('poap_filters', ROOT / 'filter_plugins/poap.py')
filters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(filters)


class PoapTests(unittest.TestCase):
    def setUp(self):
        self.device = dict(serial='EXAMPLE001', name='nexus-example')
        self.interface = dict(primary_mac_address=dict(mac_address='02:00:00:00:00:01'))
        self.addresses = [dict(address='192.0.2.50/24')]
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(ROOT / 'templates'),
                                      undefined=jinja2.StrictUndefined,
                                      trim_blocks=True, lstrip_blocks=True,
                                      keep_trailing_newline=True)
        self.env.filters.update(filters.FilterModule().filters())
        self.env.filters['to_json'] = json.dumps
        self.settings = yaml.safe_load((ROOT / 'defaults.yml').read_text())

    def record(self):
        return filters.switch_record(self.device, self.interface, self.addresses, '192.0.2.1')

    def test_modern_and_legacy_mac_and_ipv4_selection(self):
        self.assertEqual(self.record()['mac'], '02:00:00:00:00:01')
        self.interface = dict(mac_address='02:00:00:00:00:02')
        self.addresses.append(dict(address='2001:db8::1/64'))
        self.assertEqual(self.record()['address'], '192.0.2.50/24')

    def test_missing_ambiguous_invalid_data_rejected(self):
        for addresses in ([], self.addresses * 2):
            with self.assertRaises(ValueError):
                filters.switch_record(self.device, self.interface, addresses, '192.0.2.1')
        for gateway in ('', '198.51.100.1', '192.0.2.50', '192.0.2.255'):
            with self.assertRaises(ValueError):
                filters.switch_record(self.device, self.interface, self.addresses, gateway)
        for mac in ('', '00:00:00:00:00:00', '01:00:00:00:00:01', 'not-a-mac'):
            with self.assertRaises(ValueError):
                filters.switch_record(self.device, dict(mac_address=mac), self.addresses, '192.0.2.1')

    def test_duplicate_ip_with_different_prefix_rejected(self):
        first = self.record()
        second = dict(first, serial='EXAMPLE002', name='second', mac='02:00:00:00:00:02', address='192.0.2.50/25')
        with self.assertRaises(ValueError):
            filters.validate_switches([first, second])

    def test_cli_injection_rejected(self):
        for value in ('admin; reload', 'admin\ncommand', '"admin"', ''):
            with self.assertRaises(ValueError):
                filters.cli_token(value)

    def test_tested_dnsmasq_format(self):
        self.settings.update(poap_switches=[self.record()], poap_bootfile='boot.example/poap.py')
        self.assertEqual(self.env.get_template('dhcp-hosts.j2').render(self.settings),
                         '02:00:00:00:00:01,set:real-nexus-poap\n')
        self.assertEqual(self.env.get_template('dhcp-options.j2').render(self.settings),
                         'tag:real-nexus-poap,67,boot.example/poap.py\n')

    def test_generated_script_checksum_and_serial_selection(self):
        self.settings['poap_switch'] = self.record()
        config = self.env.get_template('nxos.cfg.j2').render(self.settings)
        self.assertIn('ip address 192.0.2.50/24', config)
        self.assertIn('username admin password 0 admin role network-admin', config)
        self.assertIn('feature ssh', config)
        self.settings['poap_configurations'] = {'EXAMPLE001': config}
        with tempfile.TemporaryDirectory() as directory:
            self.settings['poap_switch_config_directory'] = directory
            script = self.env.get_template('poap_script.py.j2').render(self.settings)
            lines = script.splitlines(keepends=True)
            header = next(line for line in lines if line.startswith('#md5sum='))
            payload = ''.join(line for line in lines if not line.startswith('#md5sum='))
            self.assertIn(hashlib.md5(payload.encode()).hexdigest(), header)
            namespace = {'__name__': 'test_bootstrap'}
            exec(compile(script, 'rendered_poap.py', 'exec'), namespace)
            commands = []
            cli_module = types.ModuleType('cli')
            cli_module.cli = commands.append
            destination = Path(directory) / self.settings['poap_switch_config_filename']
            with patch.dict(sys.modules, {'cli': cli_module}), patch.dict(os.environ, {'POAP_SERIAL': 'UNKNOWN'}):
                with self.assertRaises(ValueError):
                    namespace['main']()
            self.assertFalse(destination.exists())
            self.assertEqual(commands, [])
            with patch.dict(sys.modules, {'cli': cli_module}), patch.dict(os.environ, {'POAP_SERIAL': 'EXAMPLE001'}):
                namespace['main']()
            self.assertEqual(destination.read_text(), config)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(commands, ['copy bootflash:netbox-poap.cfg scheduled-config'])


if __name__ == '__main__':
    unittest.main()
