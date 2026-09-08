# NetBox workbook import

This create-only Python tool reads an inventory workbook or a directory of CSV
files and adds missing
objects to an existing NetBox instance through `pynetbox`. It does not deploy
NetBox, update existing objects, delete objects, or export data.

## Use it

From the repository root:

```sh
export NETBOX_URL=https://netbox.lab.internal
export NETBOX_TOKEN=your-api-token
./tools/netbox/csv-import/import.sh tools/netbox/csv-import/example --dry-run
./tools/netbox/csv-import/import.sh path/to/inventory-csv-directory
```

The first run creates a local virtual environment and installs dependencies.
For Excel, pass an `.xlsx` workbook instead of a directory.

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
| `Devices` | `name`, `device_type`, `role`, `site` | `rack`, `position`, `face`, `status`, `serial`, `description` |
| `Interfaces` | `device`, `name` | `type`, `enabled`, `description` |
| `MACAddresses` | `address`, `device`, `interface` | `primary`, `description` |
| `InventoryItems` | `device`, `name` | `manufacturer`, `part_id`, `serial`, `parent`, `role`, `description` |
| `VLANs` | `vid`, `name` | `site`, `status` |
| `Prefixes` | `prefix` | `site`, `status`, `description` |
| `IPAddresses` | `address` | `device`, `interface`, `status`, `primary` |

References use names (or a device type's model). Inventory item parents must
appear earlier in the same sheet than their children. Include a row for each
referenced manufacturer, role, device type, site, rack, or device in the same
workbook. That row may resolve to an object already in NetBox. Unrecognized
sheets are ignored; missing sheets and blank rows are skipped. An IP address's
interface defaults to `eth0`; `true`, `yes`, or `1` marks it as the device's
primary IPv4 address. Regenerate the template after schema changes with:

For CSV input, create a directory with one file per desired object type, named
exactly like the sheet names in the table (for example `Sites.csv` and
`Devices.csv`). The same columns and dependency order apply; omitted files are
skipped. Copy [`example/`](example/) as a starting point.

```sh
.venv/bin/python make_template.py
```

The importer looks up each object by its implemented natural key and creates it
only when absent. It never modifies a matching object. Row errors are collected
and reported at the end. The current device role field targets NetBox 4.x;
NetBox 3.x requires changing `DEVICE_ROLE_FIELD` in `netbox_import/sync.py`.

## Test

```sh
cd tools/netbox/csv-import
.venv/bin/pip install pytest
PYTHONPATH=. .venv/bin/python -m pytest tests -v
```

Tests use an in-memory fake and do not contact NetBox.

Keep credentials out of workbooks and the repository. Use a narrowly scoped
token with the required `dcim` and `ipam` permissions.
