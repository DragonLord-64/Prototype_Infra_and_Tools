# FHS NetBox import

Portable first implementation adapted from the
[SKA FHS development playbooks](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/tree/development/playbooks/development).

## Setup

Copy this entire directory into FHS Baremetal's `playbooks/development/`, including
`tasks/`, `filter_plugins/`, `library/`, `module_utils/`, and both requirements files.
Run Ansible inside the existing Bifrost container against that mounted copy.
From the FHS repository root:

```sh
ansible-galaxy collection install -r playbooks/development/requirements.yml -p collections
python -m pip install -r playbooks/development/requirements.txt
```

Credential defaults are `/provision/files.d/credentials/netbox.yml` and
`/provision/files.d/credentials/redfish.yml`. They supply `netbox_url`, `netbox_token`
and `redfish_credentials`. Override their paths with `netbox_credentials_file`
and `redfish_credentials_file`; keep credentials outside Git.

## Run

Preview one server, one Nexus switch, or the Bifrost export with these commands.
Remove `--check` to apply or write the export.

```sh
ansible-playbook -i inventory/dev_env playbooks/development/netbox_import.yml --limit ONE_SERVER --check --diff

ansible-playbook -i inventory/dev_env playbooks/development/netbox_import_nexus.yml --limit ONE_SWITCH --check

ansible-playbook -i inventory/dev_env playbooks/development/bifrost_export.yml --check
```

Set `bootstrap_site` and `bootstrap_role` in inventory/group vars. Server defaults
are MDA and FPGA_HOST_SERVER; device defaults are BittWare/TeraBox1501b.
Server `/etc/server-info.yaml` supplies site, role, rack and location when present.
Nexus defaults to Bootstrap Lab/Network switch and preserves its existing rack
and location; `bootstrap_site` must match that location's site. Set `ansible_user`
on the Nexus group/host and use `--ask-pass` for password authentication.

Other explicit play variables, including SDK/NIC commands and flags, need `-e`
to override them. BittWare uses the installed `/opt/venvs/fhs` environment,
`/usr/share/bittware-sdk`, and `bw_card_list -v -i USB`. Use
`-e bootstrap_bittware_enabled=false` for non-FPGA hosts, or
`-e bootstrap_bittware_debug=true` to print SDK diagnostics before parsing.
NIC discovery needs ethtool and pciutils on the server; NVMe discovery can install
nvme-cli during a normal run.

For an already imported server, add `--tags fpga` or `--tags nic` to update only
those modules. FPGA cards have three QSFP interfaces; NIC ports are grouped by
verified VPD part/serial and adopted in place. FPGA optic and DAC imports are not
performed. Check mode returns module plans; other server/Nexus objects show
observations rather than a complete write diff.

Imports update managed placement, identity, hardware and server interface type/MTU
fields while retaining interface IDs, IP attachments and cable connections. They
do not remove old records. Reported manufacturers are created when missing.
Run imports sequentially against the same NetBox;
transient API errors get bounded retries and loop items are paced.

## Bifrost export

Export writes private `playbooks/development/output/baremetal.yml` with mode 0600.
Review it before copying to the compose consumer's
`bifrost-infra/inventory/terabox1501b_inventory.yaml`, or override `bifrost_output`
explicitly. It validates inventory only; it does not enroll or deploy machines.
Set a unique root-device hint in NetBox if multiple disks match the default size
criterion. Keep generated inventories outside Git.

Nexus module types use the explicit `manufacturer_id` lookup filter with numeric manufacturer IDs in creation payloads. The collection's generic `manufacturer` query parameter expects a slug and must not receive an ID. Installed modules use the collection's default ID filters for device, bay and type. Regression tests exercise the installed collection query builder and a strict isolated HTTP contract; earlier recording-module tests did not cover that query behavior.

[Module-aware dynamic inventory](MODULE_INVENTORY.md) preserves the existing FHS inventory authentication, filters and groups while supplying FPGA/NIC module serials.
