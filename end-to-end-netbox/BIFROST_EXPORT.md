# NetBox → Bifrost YAML export

`export-bifrost.yml` uses the official `netbox.netbox.nb_lookup` lookup plugin to read inventory from NetBox and generates Bifrost's node-name-keyed YAML. There is no second hand-maintained Bifrost inventory. `bifrost-export.example.yml` contains optional shared selector/file-path settings only; copying it is not required. The generated YAML file is the inventory output, not an input settings file.

## Authentication and invocation

Reuse your existing bootstrap `vars_files` arrangement: the exporter needs the same `netbox_url` and `netbox_token` variables. No new shared credentials file or wrapper format is required. The configurable filenames below are demo defaults; replace them with your existing vars files or edit `vars_files` to match your playbook. Keep Redfish authentication in your own separate secrets/Vault vars.

Validation now reports the selected device name and actionable missing/invalid field labels without printing raw records or secret values. The native NetBox out-of-band IP supplies the controller address automatically; provisioning ports must carry the chosen tag, and username/password must be present in the secrets variables.

All three lookup calls receive `netbox_validate_certs | default(false) | bool` directly. Lookup plugins do not inherit Ansible module defaults. NetBox certificate verification defaults to false for this development setup; set `netbox_validate_certs: true` to enable it. This controls NetBox HTTPS, separately from the BMC’s `redfish_verify_ca`.

The exporter loads the same `private/netbox.json` vars file as the bootstrap by default. Choose your existing YAML/JSON/Vault file with `netbox_credentials_file`; it must define `netbox_url` and `netbox_token`. Supply Redfish credentials separately in `private/redfish.yml` by default, or any chosen YAML/JSON/Vault file:

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
- The controller address is automatically `http://` plus native device `oob_ip`, which bootstrap populates for the motherboard BMC. CIDR suffixes are removed and IPv6 addresses are bracketed. No custom endpoint or Redfish-enabled field is needed. This matches your BMC HTTP convention; the exporter does not test connectivity. Ironic expects the controller base URL, without a `/v1/redfish` suffix; the usual Redfish service root is `/redfish/v1`.
- Optional device custom field `redfish_system_id` holds the actual ComputerSystem path when needed; no `/Systems/1` assumption. Optional `redfish_verify_ca` holds a trusted CA path (on the eventual conductor); verification defaults on.
- Optional JSON custom field `bifrost` holds explicitly managed Bifrost settings such as `uuid`, `properties` (including `root_device`), `instance_info` (image), boot/interface choices and network settings. These are absent from ordinary discovered hardware facts; populate them in NetBox if deployment needs them. Do not put passwords in this field. The exporter validates allowed top-level fields and does not guess a boot disk from all NVMe drives.

Only the chosen type, provisioning-port tag and file-path settings live in repository YAML; server names, endpoints, ports, properties and intended image settings come from NetBox. Redfish auth secrets live in Ansible/Vault. Keep names stable; preserve an existing Ironic UUID in `bifrost.uuid` when available. Without one, Ironic assigns a UUID on enrollment; hardware serials are not Ironic UUIDs. This exporter does not create custom fields or update NetBox.

All paths are configurable; a `private` directory is not required. Set `bifrost_output` to any desired YAML file path, e.g. `-e bifrost_output=/srv/exports/baremetal.yml` or `-e bifrost_output=output/baremetal.yml`. Relative output paths resolve against the playbook directory (including `../`); absolute paths are preserved. The default `private/baremetal.yml` is a demo convenience. New parent directories are created with mode 0700; existing directory permissions are preserved. The output file has mode 0600 and contains credentials. Output outside the default ignored folder must be kept out of version control by your own ignore rules. Preview reads/validates but writes no inventory; normal task output and diffs suppress secrets. Do not use `-vvvv` or higher with credential-bearing runs: the upstream lookup plugin logs its token at that verbosity. Missing/invalid/duplicate MACs, unnamed or simulated devices, and incomplete/ambiguous API records fail before writing. The lookup plugin’s pynetbox client follows all API pagination for devices and interfaces; duplicate records fail before writing. The Ubuntu simulator cannot generate deployable inventory.

Bifrost consumes this file through `BIFROST_INVENTORY_SOURCE` and its inventory adapter, not directly as standard Ansible YAML inventory. Export never installs Bifrost, enrolls, deploys, changes power or writes NetBox. Enrollment/reimaging remain deliberate separate actions; this file by itself cannot prevent a downstream enrollment workflow from cleaning disks.

Dependencies are the existing `netbox.netbox` collection and controller virtual environment with pynetbox. Run using that virtual environment from this folder so `ansible.cfg` finds the installed collection. Its pynetbox version supports both legacy Token and NetBox v2 Bearer tokens automatically.

Compatibility: validated against upstream Bifrost master inventory parser and current Ironic Redfish contract. Your installed version is unknown; confirm its enabled drivers/interfaces and enrollment/network/image field support. Validation checks shape, not BMC connectivity or image bootability.

Sources: [Bifrost example](https://github.com/openstack/bifrost/blob/master/playbooks/inventory/baremetal.yml.example), [inventory parser](https://github.com/openstack/bifrost/blob/master/bifrost/inventory.py), [Redfish contract](https://docs.openstack.org/ironic/latest/admin/drivers/redfish.html).
