# Optional BittWare FPGA discovery

The `fpga` block in [bootstrap.yml](bootstrap.yml) reads each configured card’s
**BMC display output** for both serial and BMC firmware. There is no card-list
probe. It creates inventory items (not modules); firmware goes into the
inventory-item text custom field `fpga_bmc_firmware`, never the server’s
motherboard `bmc_firmware`. Structured PCI metadata goes in the inventory-item
JSON custom field `pci_endpoints`.

## Real hardware configuration

Discovery is disabled by default. Editable variables are near the top of the
playbook. Supply overrides using `-e @your-bittware-vars.yml`:

- `bootstrap_bittware_enabled`: enable after completing the configuration.
- `bootstrap_bittware_contract_confirmed`: acknowledge reviewed read-only command
  arguments and output patterns on real hardware.
- `bootstrap_bittware_venv`: existing SDK virtual environment, `/opt/venv/FHS`.
- `bootstrap_bittware_python`: existing interpreter, `/opt/venv/FHS/bin/python`.
  This runs the adapter; it does not replace Ansible’s interpreter.
- `bootstrap_bittware_sdk_root`: actual SDK installation path for `BW_SDK_ROOT`.
  The spoken path’s spelling/case was unconfirmed, so no real path is guessed.
- `bootstrap_bittware_bmc_display_argv`: exact read-only display arguments with
  `{card}` substituted for each configured index. Use the venv executable’s
  absolute path if appropriate. No shell activation is needed.
- `bootstrap_bittware_serial_pattern` and `bootstrap_bittware_firmware_pattern`:
  multiline regular expressions with one capture group and exactly one match.
- `bootstrap_bittware_cards`: records with numeric `index`, stable `name`, optional
  `part`, and `pci_endpoints` containing `address` and `function` (Altera/Arkville).
- `bootstrap_bittware_pci_list_argv`: defaults to `lspci -D -nn`; install pciutils
  through normal provisioning if needed.
- `bootstrap_bittware_pci_keywords`: Arkville, Altera, BittWare, NVIDIA, Mellanox.

SDK installation and virtual-environment creation are deliberately absent:
the target already has the SDK in its existing venv. The exact real vendor
command and output remain user-supplied; no firmware update mode is executed
by the provided example.

Explicit per-card PCI mappings are verified against live PCI inventory. Each
address uses full `domain:bus:device.function` notation. Labels and vendor/device
IDs come from the observed listing. No relationship is inferred from adjacent
addresses or manufacturer labels. Without a configured endpoint mapping the
card remains unassociated; matching unassigned PCI endpoints are reported.
NVIDIA/Mellanox metadata attaches only to a discovered NIC with the exact same
PCI address, never to an FPGA by brand alone.

Manual `bootstrap_fpga_cards` still works; SDK-discovered records are appended.
Missing firmware/PCI values omit updates and preserve existing values. Duplicate
inventory names fail before writes. Failed or ambiguous parsing stops the run
before NetBox writes rather than inventing serials or firmware.

## Synthetic container verification

[bittware-simulation.example.yml](bittware-simulation.example.yml) is explicitly
synthetic: two card indices, different serials/firmware, two nonadjacent PCI
endpoints per card, and a separate NVIDIA/Mellanox endpoint. The stub rejects
all unsupported arguments, including writes, and requires a simulation marker
and `BW_SDK_ROOT`. Its command names, text labels, IDs, and addresses are fixtures,
not verified vendor output or real hardware facts.

The demo Dockerfile provides a Python venv to model an already installed SDK
execution environment. Rebuild/stage the dedicated target before testing:

```sh
../.venv/bin/python -m unittest discover -s tests -p test_bittware.py -v
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml --syntax-check
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml \
  -e @private/netbox.json -e @bittware-simulation.example.yml --tags fpga,compare --check
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml \
  -e @private/netbox.json -e @bittware-simulation.example.yml --tags fpga,apply
```

Facts/compare/check do not write NetBox. SDK reads can run in check mode; the
adapter’s transient workspace is removed afterward. Apply creates the custom
fields before inventory updates. Repeat apply should leave inventory unchanged.
The discovery adapter is [scripts/discover_bittware.py](scripts/discover_bittware.py).

## Verified results

The synthetic dedicated-container run passed read-only compare/check with zero
changes, apply populated two FPGA records and a separate NIC record, and repeat
apply made zero changes. Read-only API assertions verified both serials, distinct
per-card firmware, all configured PCI endpoints and IDs, NIC separation, and
identical inventory-item responses before/after the repeat. The parser/safety
and existing server-info regression suites passed, as did Ansible syntax and
Git whitespace checks. These results verify the simulation and NetBox mapping;
real SDK command/output compatibility remains intentionally configurable.

Run the read-only API assertions after simulation apply:

```sh
../.venv/bin/python tests/verify_bittware_demo.py
```
