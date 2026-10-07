import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_csv


class BuildCsvTests(unittest.TestCase):
    def test_builds_device_components_interfaces_and_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "raw", root / "csv"
            source.mkdir()
            document = {
                "short_hostname": "server01",
                "system": {"Manufacturer": "Acme", "Product Name": "Compute 2U", "Serial Number": "SYS1"},
                "bios": {"Vendor": "Acme", "Version": "1.2.3"},
                "baseboards": [{"Manufacturer": "Acme", "Product Name": "Board", "Serial Number": "MB1"}],
                "memory": [{"Locator": "DIMM_A1", "Manufacturer": "Micron", "Part Number": "MEM1",
                            "Serial Number": "RAM1", "Size": "32 GB", "Type": "DDR5"}],
                "bmc": [{"Device ID": "32", "Firmware Revision": "4.5"}],
                "fru": [],
                "network_interfaces": [{"name": "eno1", "mac_address": "00:11:22:33:44:55",
                    "enabled": True, "driver": "mlx5_core", "firmware": "28.40", "bus_info": "0000:17:00.0",
                    "addresses": ["192.0.2.10/24"],
                    "pci": {"manufacturer": "Mellanox", "part_id": "MCX123", "serial": "NIC1"},
                    "transceiver": {"manufacturer": "FiberCo", "part_id": "QSFP1", "serial": "OPT1"}}],
                "custom_probes": [{"name": "FPGA 1", "category": "fpga", "command": "fpga-info"}],
                "warnings": [],
            }
            (source / "server01.json").write_text(json.dumps(document), encoding="utf-8")
            with patch.object(sys, "argv", ["build_csv.py", str(source), str(output),
                                             "--primary-interface", "eno1"]):
                build_csv.main()

            def read(name):
                with (output / name).open(newline="", encoding="utf-8") as stream:
                    return list(csv.DictReader(stream))

            self.assertEqual(read("Devices.csv")[0]["serial"], "SYS1")
            self.assertEqual(read("MACAddresses.csv")[0]["address"], "00:11:22:33:44:55")
            self.assertEqual(read("IPAddresses.csv")[0]["primary"], "true")
            items = read("InventoryItems.csv")
            self.assertTrue(any(row["serial"] == "RAM1" for row in items))
            self.assertTrue(any(row["serial"] == "NIC1" for row in items))
            self.assertTrue(any(row["serial"] == "OPT1" for row in items))
            self.assertTrue(any(row["name"] == "FPGA 1" for row in items))


if __name__ == "__main__":
    unittest.main()
