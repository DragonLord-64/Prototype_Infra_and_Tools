# FHS module-aware NetBox inventory

This is an inventory-only extension of the pinned `netbox.netbox.nb_inventory`
plugin. It retains its API endpoint, token/Vault handling, active/primary-IP
filters, role groups, config context, custom-field flattening, extra vars and
primary-IP host selection. It adds read-only module GETs for selected devices and
uses native interface module IDs to attach known ports. No hardware commands,
PSU discovery, BDF updates, provisioning or NetBox writes are performed.

## Copy and configure

Copy the current `development/` bundle into the FHS repository's
`playbooks/development/`. Keep the existing `inventory/dev_env/netbox-inv.yml`
and its token; do not replace it with a copied secret from another repository.
Run the configuration updater on the **host repository**, before entering the
Bifrost container (its ansible.cfg may be mounted read-only):

```sh
python3 playbooks/development/setup_module_inventory.py .
```

The updater switches just the inventory plugin to `fhs_nb_inventory`, enables
interfaces, scopes interface fetching to selected hosts, and adds
`./playbooks/development/inventory_plugins` to the existing ansible.cfg plugin
path. It preserves the current endpoint, filters, role grouping and Vault block.
It is safe to run again. The example YAML is for fresh setups using the native
`NETBOX_API`/`NETBOX_TOKEN` environment options; the updater uses your existing
configuration instead.

Use the existing controller venv/collection setup. The controller dependency
manifest now includes `pytz`, which the native inventory plugin requires. From
inside the Bifrost container, with your existing Vault password mechanism:

```sh
cd /provision
ansible-inventory -i inventory/dev_env/netbox-inv.yml --list
ansible-inventory -i inventory/dev_env/netbox-inv.yml --host SERVER_NAME
```

If needed, supply your existing `--vault-password-file` option; no new password
file or token format is introduced. Inventory listing includes hardware serials
and host data but does not expose the inventory token.

## Variables

- `fhs_fpga_modules`: FPGA modules whose bays use the import format `FPGA CARD N`.
- `fhs_nic_modules`: NIC modules whose bays use the import format `NIC ...`.
- `fhs_modules`: those FPGA/NIC lists combined; unrelated PSU/fan/optic modules
  are excluded from this FHS view.
- `fpga_card0_sn` and `fpga_card1_sn`: existing BIST consumer names, from modules
  explicitly labelled card0/card1. No ordinal guessing from query order.
- `terabox_nic0_sn`: existing BIST consumer name, populated only when one NIC
  module is available. Multiple NICs produce a warning and omit that ambiguous
  alias; structured records remain available.
- `fhs_inventory_warnings`: ambiguous legacy serial mapping, when present.

Each structured module has its NetBox ID, bay, model, serial, available vendor
information, known custom fields and verified attached interfaces. Part number is
included only if returned by the API. Partial/missing module data leaves aliases
absent rather than inventing serials or port mappings.

No `fpga_card*_bdf_*`, `terabox_nic0_bdf`, or PSU variables are generated. Existing
BDF role defaults and static NIC interface choices remain unchanged. Existing
`host_vars` serial entries can override dynamic inventory under Ansible precedence;
remove those duplicate serial definitions deliberately if NetBox should supply
them. Role vars such as the current static `terabox_nic0_iface` also retain their
existing precedence and behavior. External BIST templates are not changed.

The extension requires the module-bay naming produced by this bundle. Manually
named hardware can still be viewed in NetBox; it is not guessed into FHS card
indices or legacy aliases. Native API errors and permission warnings remain visible; missing observations do
not produce invented serials. Review those diagnostics before provisioning.

## Verified

Targeted tests run actual `ansible-inventory` against a temporary loopback API
with synthetic Vault-encrypted auth. They verify filters, role groups, primary IP,
config context/custom fields, module-ID interface joins, serial aliases and token
non-disclosure. Unit cases cover missing/ambiguous modules and an idempotent
config update preserving the Vault text. No live cluster or provisioning was run.
