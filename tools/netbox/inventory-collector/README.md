# NetBox hardware inventory collector

This collector runs read-only probes on multiple Linux servers and emits a
directory of relational CSV files accepted by the adjacent
[`csv-import`](../csv-import/) tool. It currently discovers system identity,
OS/kernel, BIOS, system boards, populated DIMMs, local IPMI BMC information,
network interfaces, MAC/IP addresses, NIC driver/firmware data, and readable
pluggable-transceiver EEPROM data. Raw JSON is retained so later parser
improvements do not require another server visit.

## Run

Create an inventory group containing the eight servers:

```ini
[netbox_inventory_servers]
server01 ansible_host=192.0.2.11
server02 ansible_host=192.0.2.12
```

From `automation/ansible`, copy and edit the example variables, especially the
site name, primary management interface, and FPGA commands:

```sh
cp netbox-inventory-vars.example.yml netbox-inventory-vars.yml
ansible-playbook -i inventory.ini playbooks/collect-netbox-inventory.yml \
  -e @netbox-inventory-vars.yml
```

The targets need Python 3. Accurate DMI data normally requires privilege
escalation. Install `dmidecode`, `iproute2`, `ethtool`, and `ipmitool` for the
corresponding probes. Missing tools and unsupported EEPROM reads are warnings,
not fatal errors. Inspect:

- `output/<run-id>/raw/<host>.json` for all collected and custom-probe output;
- `output/<run-id>/csv/collection-warnings.txt` for probes that need attention;
- `output/<run-id>/csv/*.csv` before importing.

Then preview and import:

```sh
./tools/netbox/csv-import/import.sh \
  tools/netbox/inventory-collector/output/<run-id>/csv --dry-run
./tools/netbox/csv-import/import.sh \
  tools/netbox/inventory-collector/output/<run-id>/csv
```

The importer is create-only. It will not overwrite existing NetBox records.
The generated CSV files contain no credentials, but hardware serial numbers
may still be sensitive; the output directory is gitignored.

## Vendor-specific hardware

`netbox_extra_probes` accepts a name, category, shell command, and optional
timeout. Commands run as root on each target. FPGA placeholders are included in
the example. Their output remains in raw JSON and generates an InventoryItem
placeholder. Once representative command output is available, add a parser to
`build_csv.py` to populate manufacturer, part ID, serial, firmware, FPGA slot,
and child QSFP items precisely.

QSFP EEPROM access is attempted with `ethtool -m <interface>`. Some FPGA-attached
QSFPs are invisible to Linux networking and must use the FPGA vendor command as
an extra probe.
