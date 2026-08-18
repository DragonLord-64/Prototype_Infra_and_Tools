import unittest

from netbox_import.sync import run_sync
from netbox_import.workbook import SHEET_ORDER

from .fakes import FakeNetbox


SAMPLE_SHEETS = {
    "Manufacturers": [{"name": "Dell"}],
    "DeviceRoles": [{"name": "Server"}],
    "DeviceTypes": [{"manufacturer": "Dell", "model": "PowerEdge R740"}],
    "Sites": [{"name": "Lab"}],
    "Racks": [{"name": "Rack1", "site": "Lab"}],
    "Devices": [
        {
            "name": "srv01",
            "device_type": "PowerEdge R740",
            "role": "Server",
            "site": "Lab",
            "rack": "Rack1",
            "position": 10,
        }
    ],
    "VLANs": [{"vid": 100, "name": "servers", "site": "Lab"}],
    "Prefixes": [{"prefix": "10.0.0.0/24", "site": "Lab"}],
    "IPAddresses": [
        {"address": "10.0.0.10/24", "device": "srv01", "interface": "eth0", "primary": "true"}
    ],
}


class RunSyncTests(unittest.TestCase):
    def test_creates_everything_in_dependency_order(self):
        nb = FakeNetbox()
        stats = run_sync(nb, SAMPLE_SHEETS)

        self.assertEqual(stats.errors, [])
        self.assertEqual(len(nb.dcim.manufacturers.objects), 1)
        self.assertEqual(len(nb.dcim.device_types.objects), 1)
        self.assertEqual(len(nb.dcim.sites.objects), 1)
        self.assertEqual(len(nb.dcim.racks.objects), 1)
        self.assertEqual(len(nb.dcim.devices.objects), 1)
        self.assertEqual(len(nb.dcim.interfaces.objects), 1)
        self.assertEqual(len(nb.ipam.vlans.objects), 1)
        self.assertEqual(len(nb.ipam.prefixes.objects), 1)
        self.assertEqual(len(nb.ipam.ip_addresses.objects), 1)

        device = nb.dcim.devices.objects[0]
        rack = nb.dcim.racks.objects[0]
        self.assertEqual(device.rack, rack.id)
        self.assertEqual(device.device_role, nb.dcim.device_roles.objects[0].id)

        ip = nb.ipam.ip_addresses.objects[0]
        self.assertEqual(device.primary_ip4, ip.id)
        self.assertTrue(device.saved)

    def test_rerun_is_idempotent(self):
        nb = FakeNetbox()
        run_sync(nb, SAMPLE_SHEETS)
        stats = run_sync(nb, SAMPLE_SHEETS)

        self.assertEqual(stats.created, 0)
        self.assertGreater(stats.existing, 0)
        self.assertEqual(len(nb.dcim.devices.objects), 1)  # no duplicate

    def test_dry_run_writes_nothing(self):
        nb = FakeNetbox()
        stats = run_sync(nb, SAMPLE_SHEETS, dry_run=True)

        self.assertEqual(stats.errors, [])
        self.assertGreater(stats.created, 0)
        for endpoint in list(vars(nb.dcim).values()) + list(vars(nb.ipam).values()):
            self.assertEqual(endpoint.objects, [])

    def test_unknown_reference_is_reported_not_raised(self):
        nb = FakeNetbox()
        sheets = {
            "Sites": [{"name": "Lab"}],
            "Racks": [{"name": "Rack1", "site": "Nonexistent"}],
        }
        stats = run_sync(nb, sheets)

        self.assertEqual(len(stats.errors), 1)
        self.assertIn("Nonexistent", stats.errors[0])
        self.assertEqual(nb.dcim.racks.objects, [])

    def test_missing_sheet_is_skipped(self):
        nb = FakeNetbox()
        stats = run_sync(nb, {"Sites": [{"name": "Lab"}]})

        self.assertEqual(stats.errors, [])
        self.assertEqual(len(nb.dcim.sites.objects), 1)
        self.assertEqual(len(nb.dcim.devices.objects), 0)

    def test_sheet_order_covers_all_sample_sheets(self):
        self.assertEqual(set(SHEET_ORDER), set(SAMPLE_SHEETS))


if __name__ == "__main__":
    unittest.main()
