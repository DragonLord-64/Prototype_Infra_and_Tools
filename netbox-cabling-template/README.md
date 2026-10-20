# NetBox cable connection template

Open [the Excel template](NetBox-Cable-Template.xlsx). The **Connections** sheet contains six synthetic examples using NetBox cable CSV column names. The **Guide** sheet explains what to enter, where to find each value, and how to import the result. A [matching CSV example](netbox-cables-examples.csv) is included.

The examples cover a server NIC, a second interface on the same server, two breakout child interfaces, a BMC management Ethernet interface, and a switch-to-switch uplink. They do not describe your real inventory. Replace the demo names with the exact NetBox device and interface Name fields. `dcim.interface` identifies an interface object; it is not a port speed or switchport mode.

1. Confirm both devices and their interfaces already exist in NetBox.
2. Replace the six example rows, or add reviewed connections. Record each pair once. Yellow cells identify the device/interface names to edit.
3. Export only **Connections** as **CSV UTF-8**, retaining the first-row headers.
4. Open NetBox's **Cables > Import** action and compare its **CSV Field Options** with the template before importing.
5. Import and inspect one connection, then import the remaining reviewed rows. Existing cables should not be duplicated.

The required endpoint columns are `side_a_device`, `side_a_type`, `side_a_name`, `side_b_device`, `side_b_type`, and `side_b_name`. `label` and `description` are optional cable attributes. NetBox device names are used rather than IP addresses, serial numbers or role labels. If device names are ambiguous across sites, add `side_a_site` and `side_b_site` with exact NetBox site names.

This template covers ordinary single-termination network-interface connections. Breakout examples show separate child-interface pairs. Full multi-termination cable assemblies and patch-panel front/rear ports need the appropriate schema for the installed NetBox version.

Headers were checked against the [NetBox 4.4 CableImportForm](https://github.com/netbox-community/netbox/blob/v4.4.0/netbox/dcim/forms/bulk_import.py#L1270) and [NetBox 4.5 CableImportForm](https://github.com/netbox-community/netbox/blob/v4.5.0/netbox/dcim/forms/bulk_import.py#L1302). See the [bulk-import documentation](https://netbox.readthedocs.io/en/stable/getting-started/populating-data/). The workbook was rendered and inspected, and its six rows, CSV values, table filters, frozen headings and type validation were checked after export. No live NetBox import was performed.
