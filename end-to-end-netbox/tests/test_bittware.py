"""Synthetic SDK parsing and association tests; no vendor hardware exercised."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discovery', ROOT / 'scripts/discover_bittware.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class BittwareTests(unittest.TestCase):
    def setUp(self):
        example = yaml.safe_load((ROOT / 'bittware-simulation.example.yml').read_text())
        self.config = {k: example['bootstrap_bittware_' + k] for k in ['bmc_display_argv', 'pci_list_argv', 'serial_pattern', 'firmware_pattern', 'cards']}
        self.config['pci_keywords'] = ['Arkville', 'Altera', 'NVIDIA', 'Mellanox']
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'SIMULATION').touch()
        (root / 'fixtures').symlink_to(ROOT / 'test-target/fixtures')
        self.env = dict(os.environ, BW_SIMULATION_ROOT=str(root), BW_SDK_ROOT=str(root))
        self.config['bmc_display_argv'][0] = str(ROOT / 'test-target/stubs/bw-sdk-simulator')
        self.config['pci_list_argv'][0] = self.config['bmc_display_argv'][0]

    def discover(self):
        with patch.dict(os.environ, self.env):
            return module.discover(self.config)

    def test_two_physical_cards_four_endpoints_and_separate_nic(self):
        result = self.discover()
        self.assertEqual([c['serial'] for c in result['cards']], ['SIM-FPGA-0001', 'SIM-FPGA-0002'])
        self.assertEqual([c['bmc_firmware'] for c in result['cards']], ['SIM-1.2.3', 'SIM-4.5.6'])
        self.assertEqual([len(c['pci_endpoints']) for c in result['cards']], [2, 2])
        self.assertEqual(result['cards'][0]['pci_endpoints'][1]['vendor_id'], '1172')
        self.assertEqual([p['address'] for p in result['unassociated_pci_endpoints']], ['0000:a1:00.0'])

    def test_missing_configured_endpoint_fails(self):
        self.config['cards'][0]['pci_endpoints'][0]['address'] = '0000:ff:00.0'
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.discover()

    def test_duplicate_endpoint_fails(self):
        self.config['cards'][1]['pci_endpoints'][0]['address'] = '0000:21:00.0'
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.discover()

    def test_missing_output_match_fails(self):
        self.config['serial_pattern'] = '^Nonexistent: (.+)$'
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.discover()

    def test_write_commands_rejected(self):
        for args in [['bmc-display', '-c', '0', 'upgrade'], ['bmc-display', '-c', '0', 'display', '--write'], ['bmc-display', '-c', '2', 'display']]:
            result = subprocess.run([self.config['bmc_display_argv'][0]] + args, env=self.env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_marker_and_sdk_environment_required(self):
        for env in [dict(self.env, BW_SIMULATION_ROOT='/nonexistent'), dict(self.env, BW_SDK_ROOT='')]:
            result = subprocess.run(self.config['pci_list_argv'], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__':
    unittest.main()
