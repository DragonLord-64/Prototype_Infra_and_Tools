# NetBox → Bifrost YAML export

`export-bifrost.yml` uses the official `netbox.netbox.nb_lookup` lookup plugin to read inventory from NetBox and generates Bifrost's node-name-keyed YAML. There is no second hand-maintained Bifrost inventory. `bifrost-export.example.yml` contains optional shared selector/file-path settings only; copying it is not required. The generated `private/baremetal.yml` is the inventory output, not an input settings file.

## Authentication and invocation

All three lookup calls receive `netbox_validate_certs | default(true) | bool` directly. Lookup plugins do not inherit Ansible module defaults. Set `netbox_validate_certs: false` in your shared NetBox login file for an explicitly trusted self-signed development instance. This controls NetBox HTTPS, separately from the BMC’s `redfish_verify_ca`.

The exporter loads the same `private/netbox.json` vars file as the bootstrap by default. Choose your existing YAML/JSON/Vault file with `netbox_credentials_file`; it must define `netbox_url` and `netbox_token`. Supply Redfish credentials separately in ignored `private/redfish.yml` (or another chosen Vault file):

```yaml
redfish_credentials:
  defaults:
    redfish_username: YOUR_USER
    redfish_password: YOUR_SECRET
  devices: {}  # Optional per-NetBox-name overrides of username/password/auth_type.
```

From this folder, preview then export:

```bash
../.venv/bin/ansible-playbook -i localhost, export-bifrost.yml -e bifrost_device_type=YOUR_MODEL --check
../.venv/bin/ansible-playbook -i localhost, export-bifrost.yml -e bifrost_device_type=YOUR_MODEL
# For your existing login YAML and a separate encrypted Redfish secrets file:
../.venv/bin/ansible-playbook -i localhost, export-bifrost.yml -e bifrost_device_type=YOUR_MODEL -e netbox_credentials_file=private/netbox.yml -e redfish_credentials_file=private/redfish.vault.yml --ask-vault-pass
```

## NetBox is the inventory owner

- Select the NetBox **device type** (hardware model) with `bifrost_device_type`. Every server of that type is exported. A string is the exact model name; a YAML integer is the type ID, e.g. `-e '{"bifrost_device_type":42}'`. Ambiguous model names fail; use an ID in that case. This is a device type, not a role, tag or module type.
- Tag only provisioning interfaces with slug `bifrost-provisioning` (override `bifrost_provisioning_tag`). Names and MACs come from those NetBox interfaces. Management-only and disabled ports are rejected.
- Store the HTTPS endpoint in device custom field `redfish_address`. Alternatively set boolean custom field `redfish_enabled: true` and the exporter derives HTTPS from the native `oob_ip`, which bootstrap already populates for the motherboard BMC. An IP alone does not prove Redfish support.
- Optional device custom field `redfish_system_id` holds the actual ComputerSystem path when needed; no `/Systems/1` assumption. Optional `redfish_verify_ca` holds a trusted CA path (on the eventual conductor); verification defaults on.
- Optional JSON custom field `bifrost` holds explicitly managed Bifrost settings such as `uuid`, `properties` (including `root_device`), `instance_info` (image), boot/interface choices and network settings. These are absent from ordinary discovered hardware facts; populate them in NetBox if deployment needs them. Do not put passwords in this field. The exporter validates allowed top-level fields and does not guess a boot disk from all NVMe drives.

Only the chosen type, provisioning-port tag and file-path settings live in repository YAML; server names, endpoints, ports, properties and intended image settings come from NetBox. Redfish auth secrets live in Ansible/Vault. Keep names stable; preserve an existing Ironic UUID in `bifrost.uuid` when available. Without one, Ironic assigns a UUID on enrollment; hardware serials are not Ironic UUIDs. This exporter does not create custom fields or update NetBox.

Output is ignored `private/baremetal.yml` (directory 0700, file 0600) and contains credentials. Preview reads/validates but writes no inventory; normal task output and diffs suppress secrets. Do not use `-vvvv` or higher with credential-bearing runs: the upstream lookup plugin logs its token at that verbosity. Missing/invalid/duplicate MACs, unnamed or simulated devices, and incomplete/ambiguous API records fail before writing. The lookup plugin’s pynetbox client follows all API pagination for devices and interfaces; duplicate records fail before writing. The Ubuntu simulator cannot generate deployable inventory.

Bifrost consumes this file through `BIFROST_INVENTORY_SOURCE` and its inventory adapter, not directly as standard Ansible YAML inventory. Export never installs Bifrost, enrolls, deploys, changes power or writes NetBox. Enrollment/reimaging remain deliberate separate actions; this file by itself cannot prevent a downstream enrollment workflow from cleaning disks.

Dependencies are the existing `netbox.netbox` collection and controller virtual environment with pynetbox. Run using that virtual environment from this folder so `ansible.cfg` finds the installed collection. Its pynetbox version supports both legacy Token and NetBox v2 Bearer tokens automatically.

Compatibility: validated against upstream Bifrost master inventory parser and current Ironic Redfish contract. Your installed version is unknown; confirm its enabled drivers/interfaces and enrollment/network/image field support. Validation checks shape, not BMC connectivity or image bootability.

Sources: [Bifrost example](https://github.com/openstack/bifrost/blob/master/playbooks/inventory/baremetal.yml.example), [inventory parser](https://github.com/openstack/bifrost/blob/master/bifrost/inventory.py), [Redfish contract](https://docs.openstack.org/ironic/latest/admin/drivers/redfish.html).
