# Current FHS NetBox playbooks

This directory is the current, self-contained bundle adapted from the public
[SKA FHS development branch](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/tree/development/playbooks/development).
Copy its contents into that repository's `playbooks/development/` directory.
Keep `tasks/`, `filter_plugins/`, and `library/` beside the entrypoint playbooks;
no Prototype Infra checkout or absolute development-machine path is required.
Do not copy generated `output/` files or private credentials into Git.

## Setup and entrypoints

Use the existing provisioning container/controller environment and inventory.
From the SKA repository root install these additional collections in its existing
collection path, then install controller dependencies in its controller venv:

```sh
ansible-galaxy collection install -r playbooks/development/requirements.yml -p collections
python -m pip install -r playbooks/development/requirements.txt
ansible-playbook -i inventory/dev_env playbooks/development/netbox_import.yml --check --diff
ansible-playbook -i inventory/dev_env playbooks/development/netbox_import.yml
ansible-playbook -i inventory/dev_env playbooks/development/netbox_import_nexus.yml --check
ansible-playbook -i inventory/dev_env playbooks/development/bifrost_export.yml --check
```

Default credential vars files remain `/provision/files.d/credentials/netbox.yml`
and `/provision/files.d/credentials/redfish.yml`. Override `netbox_credentials_file`
and `redfish_credentials_file` outside the container. These files supply the
existing `netbox_url`, `netbox_token`, and `redfish_credentials` schema; never put
actual credentials in this bundle. Run server discovery only against Linux hosts
(use an inventory/limit); the Nexus playbook targets the `nexus` group and needs
network CLI access. The existing SKA root `ansible.cfg` can remain unchanged.
Ansible discovers adjacent library/filter directories automatically.

Working server defaults are retained: MDA, FPGA_HOST_SERVER, BittWare,
TeraBox1501b, `/opt/venvs/fhs`, `/usr/share/bittware-sdk`, and
`bw_card_list -v -i USB`. `BWSDK_ROOT` and venv PATH are supplied per SDK command;
no activate shell or SDK installation is needed. Fleet values and commands are
ordinary play/inventory overrides. The actual output patterns are top-level vars
and are used by the parser. Default patterns accept the working source grammar: variable indentation, index-line suffixes, and complete alphanumeric serial identifiers. Missing required fields are reported by name within each card block, without dumping command output.

## SDK output debugging

Enable `bootstrap_bittware_debug: true` (or pass `-e bootstrap_bittware_debug=true`) to print the SDK command exit code, stdout/stderr lines, argv and configured patterns immediately before parsing. This opt-in output includes hardware serials, so review it before sharing. It does not dump credential variables. A failed SDK exit stops before normalization; error-only output with a zero exit still must pass identity validation. The SDK retains the target's existing PATH after the venv prefixes, matching the working source.

If an error still says only “Incomplete FPGA card record; review SDK output and patterns,” the controller is loading an older filter: the current parser reports missing field names. Recopy `filter_plugins/fhs_inventory.py`, `tasks/fpga.yml`, and `netbox_import.yml` together, and run a fresh Ansible process. Check any configured duplicate filter-plugin directories if the old wording persists.

## FPGA modules and ports

Each discovered card has one module bay (`FPGA CARD <actual index>`), a BittWare
module type using the reported part number, a serial, board/BMC versions and
optional PCI endpoint JSON. Three module-type interface templates generate the
source's names `C<index>-QSFP0`, `C<index>-QSFP1`, `C<index>-QSFP2`; the source's
400G QSFP-DD interface type is retained and configurable with
`bootstrap_fpga_interface_type`. Indices are actual USB indices, not list order.
**FPGA QSFP transceivers are not automatically imported.** Nexus retains its
separate PSU/fan/transceiver inventory behavior.

Set `bootstrap_bittware_pci_map` when the card-to-BDF mapping is known. Empty
mapping omits observations and preserves existing PCI data; product names alone
cannot establish a card's serial association. For example (replace addresses):

```yaml
bootstrap_bittware_pci_map:
  0:
    - {address: '0000:01:00.0', function: Arkville}
    - {address: '0000:02:00.0', function: Altera}
```

Existing server interfaces are adopted without changing their IDs, cables, IPs,
enabled flags, or existing type. An interface already owned by another module
blocks the operation. Legacy FPGA inventory items are neither deleted nor
migrated automatically. DDR/NVMe legacy inventory discovery remains. Existing legacy NIC inventory items are retained; newly discovered supported NICs use modules.

NetBox 4.3/4.4 REST APIs lack the UI module adoption switches. The small local
`fhs_fpga_sync` Ansible module therefore creates new cards with a shared,
**template-free staging type**, attaches the three interfaces in place, and
updates to the reported module type. The real type keeps all three templates.
The staging type must stay empty; failed runs can be safely rerun. No object is
deleted. This narrowly scoped helper uses the same mapping and reconciliation
for check mode and normal apply.

## NIC modules

NIC discovery now combines `ethtool -i <interface>` with the working source's
`lspci -vv -s <BDF>` VPD command. It records physical card part/serial from VPD,
and driver, driver version, firmware and exact PCI address from ethtool. Plain
ethtool adds observed speed, duplex and link state to per-function metadata.
Those observations do not change interface enablement, link settings or type.
The firmware PSID in ethtool is retained as metadata, not guessed to be a part
number. `ethtool -m` describes a plugged optic/DAC and is deliberately not called.

Top-level variables are `bootstrap_nic_enabled`, `bootstrap_nic_manufacturer`
(default Mellanox), `bootstrap_nic_drivers` (default mlx5_core),
`bootstrap_nic_ethtool_argv`, `bootstrap_nic_vpd_argv`,
`bootstrap_nic_collect_link` and the VPD part/serial patterns. Install ethtool and
pciutils through the existing provisioning setup; a missing command/identity is
reported and existing NIC data is preserved. Commands are read-only and run in
check mode. A normal `--tags nic` applies the NIC module portion to an already
imported server; `--check --diff --tags nic` previews it. Copy the whole bundle,
including the new `tasks/nic.yml`, shared library and filter, before running.

Only PCI-backed host interfaces are candidates. An explicit sysfs `physfn` parent
excludes SR-IOV VFs; known VF/SF representor physical-port names (including the port-prefixed convention) are excluded too. See the [Linux representor identification reference](https://docs.kernel.org/networking/representors.html#how-are-representors-identified).
If ethtool's BDF disagrees with host facts, the port is not imported. Unknown or
unsupported drivers and absent card part/serial produce diagnostics rather than
invented physical cards. Virtual/representor detection is limited to those explicit
sysfs signals; unusual drivers or naming schemes need verified samples before
expanding scope.

Ports are grouped only when VPD reports the same part AND serial. Adjacent PCI
functions or similar Linux names do not prove one physical NIC. The new module
bay starts with its lowest observed BDF; a later partial observation reuses an
existing uniquely matched NIC module's bay. Existing interface IDs, IPs, cables,
enablement and types are preserved. No unseen ports or port types are invented.
Unlike the fixed FPGA three-port layout, NIC interfaces use actual Linux names
and are attached explicitly; no per-host-name module-type templates are created.

Module fields `nic_driver`, `nic_firmware`, `nic_functions` and `pci_endpoints`
retain card-level and per-interface/function metadata. Partial discovery merges
known function fields and endpoints, preserving missing observations and existing
ports. It does not delete removed hardware or migrate old inventory items. The
same reconciler supplies check plans and normal apply, including safe staging-type
adoption. Hardware replacements/moves and pruning require separate review.

## Preview, scopes, and host changes

Read-only SDK/VPD probes run during check mode, with `changed_when: false`.
FPGA/NIC synchronization reads NetBox, computes creates/updates, and returns a plan
and `--diff` without POST/PATCH in check mode or `--tags compare`.
`--tags fpga` applies only the FPGA module portion to an already imported server;
use `--check --tags fpga` to preview it. A missing server is represented in a
check plan; actual apply requires the parent device. `--tags apply` runs the full
original prerequisite/discovery/apply pipeline. Tags `nic`, `resources`, `bios`,
`bmc`, `ddr`, `nvme`, and `facts` retain their discovery scope. Resource discovery
no longer unintentionally includes SDK/NIC work.

For other server objects and Nexus, check mode still displays desired/current
records and skips NetBox writes. This is **not** a complete module-native diff for
those objects, especially when parent site/device/type objects do not exist.
Their mapping isn't duplicated into a separate check playbook. Missing optional
hardware observations preserve existing values. Manual edits to fields managed
by import (site/role/type/primary IP) can be overwritten on apply; choose field
ownership before using this as an automatic refresh service.

The user-approved nvme-cli apt setup remains in discovery: a normal NVMe or
compare run may install it on a Debian-family target. Check mode runs apt's
preview and does not install packages; it may report that installation is needed.
This pipeline must not be described as entirely free of host changes on normal
runs. BittWare is enabled by the fleet default; disable explicitly on non-FPGA
hosts with `bootstrap_bittware_enabled: false`.

## Bifrost handoff

The export selects TeraBox1501b by default (same as import), validates provisioning
interface tags, out-of-band IP and Redfish credentials, and writes private YAML
to `playbooks/development/output/baremetal.yml` (mode 0600). This directory is
ignored. Check mode validates without writing. Existing enrollment schema, explicit
root disk criteria and default UEFI capability are retained. The source default
`size: '> 900'` is only a criterion and may match more than one disk; define a
unique root-device hint in NetBox before deployment if the server has multiple
eligible disks. The playbook does not enroll, deploy, reboot or select disks itself.

The SKA compose consumer mounts `bifrost-infra/inventory/terabox1501b_inventory.yaml`
into Bifrost. Export does not automatically replace that active inventory. Either
review/copy the generated file to the intended consumer or explicitly override
`bifrost_output` to that destination when ready. Credentials in the generated
inventory must remain outside Git.

## Verification

`tests/` contains parser boundary/missing-field tests, per-function VPD enrichment,
FPGA/NIC check/apply/idempotence/interface-adoption tests, and Nexus parser/task tests.
The portability test copies this directory into SKA's exact `playbooks/development`
topology and runs actual FPGA and NIC discovery/helper tasks against synthetic SDK output
and a temporary loopback API, without live credentials. Run in the controller venv:

```sh
python -m unittest discover -s playbooks/development/tests -v
```

The published SDK/QSFP samples were inspected: card metadata uses four-space indentation and alphanumeric serials; QSFP output has three ports including an empty port. The published sample repeats a serial across distinct USB indices; that relationship is retained in fixtures and reported as a caveat, while module identity stays device-plus-bay. Sanitized fixtures preserve those shapes. FPGA optic modules remain disabled.

Synthetic tests do not certify the physical fleet or exact installed NetBox
permissions/version. A physical read-only smoke test and reviewed check plan
remain necessary before live application. No live systems were changed while
building this bundle.
