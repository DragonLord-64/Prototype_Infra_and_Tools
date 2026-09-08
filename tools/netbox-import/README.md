# NetBox workbook import

This create-only Python tool reads an inventory workbook and adds missing
objects to an existing NetBox instance through `pynetbox`. It does not deploy
NetBox, update existing objects, delete objects, or export data.

## Use it

From the repository root:

```sh
cd tools/netbox-import
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp template/inventory-template.xlsx my-inventory.xlsx

export NETBOX_URL=https://netbox.lab.internal
export NETBOX_TOKEN=your-api-token
.venv/bin/python -m netbox_import.cli my-inventory.xlsx --dry-run
.venv/bin/python -m netbox_import.cli my-inventory.xlsx
```

You can pass `--url` and `--token` instead of environment variables. Dry-run
performs lookups and reports predicted creates without sending writes. Because
predicted objects have no NetBox IDs, it is a preview rather than full
validation of dependent rows.

## Workbook

The template has one optional sheet per object type. Rows are processed in this
dependency order:

| Sheet | Required columns | Optional columns |
| --- | --- | --- |
| `Manufacturers` | `name` | `slug` |
| `DeviceRoles` | `name` | `slug`, `color` (hex without `#`) |
| `DeviceTypes` | `manufacturer`, `model` | `slug`, `u_height` |
| `Sites` | `name` | `slug`, `status` |
| `Racks` | `name`, `site` | `status`, `u_height` |
| `Devices` | `name`, `device_type`, `role`, `site` | `rack`, `position`, `face`, `status`, `serial` |
| `VLANs` | `vid`, `name` | `site`, `status` |
| `Prefixes` | `prefix` | `site`, `status`, `description` |
| `IPAddresses` | `address` | `device`, `interface`, `status`, `primary` |

References use names (or a device type's model). Include a row for each
referenced manufacturer, role, device type, site, rack, or device in the same
workbook. That row may resolve to an object already in NetBox. Unrecognized
sheets are ignored; missing sheets and blank rows are skipped. An IP address's
interface defaults to `eth0`; `true`, `yes`, or `1` marks it as the device's
primary IPv4 address. Regenerate the template after schema changes with:

```sh
.venv/bin/python make_template.py
```

The importer looks up each object by its implemented natural key and creates it
only when absent. It never modifies a matching object. Row errors are collected
and reported at the end. The current device role field targets NetBox 4.x;
NetBox 3.x requires changing `DEVICE_ROLE_FIELD` in `netbox_import/sync.py`.

## Test

```sh
cd tools/netbox-import
.venv/bin/pip install pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

Tests use an in-memory fake and do not contact NetBox.

Keep credentials out of workbooks and the repository. Use a narrowly scoped
token with the required `dcim` and `ipam` permissions.
