# NetBox → Bifrost YAML export

`export-bifrost.yml` reads only explicitly selected NetBox devices and interfaces. It writes a node-name-keyed Bifrost inventory with `driver: redfish`, `driver_info`, and `nics: [{mac: ...}]`. It does not enroll, deploy, install Bifrost, change power, or write to NetBox.

Copy `bifrost-export.example.yml` to `private/bifrost-export.yml`, replace placeholders, and supply a separate private/Vault file containing `bifrost_credentials`, keyed by the same device names. Existing `private/netbox.json` supplies `netbox_url` and `netbox_token`. From this folder:

```bash
../.venv/bin/ansible-playbook -i localhost, export-bifrost.yml -e @private/netbox.json -e @private/bifrost-export.yml -e @private/bifrost-credentials.yml --check
../.venv/bin/ansible-playbook -i localhost, export-bifrost.yml -e @private/netbox.json -e @private/bifrost-export.yml -e @private/bifrost-credentials.yml
```

Add `--ask-vault-pass` for encrypted credentials. Output defaults to ignored `private/baremetal.yml` (directory 0700, file 0600); it contains BMC credentials. Check mode reads/validates but writes no inventory; task output and diffs suppress secrets. Refresh the export while NetBox is reachable and protect any off-machine copy.

Select provisioning ports explicitly; management-only and disabled ports are rejected. Missing/invalid/duplicate MACs, absent devices, and devices tagged `simulated-hardware` fail before writing. The existing Ubuntu hardware simulator therefore cannot generate deployable inventory. Endpoint and credentials are explicit inputs: a discovered BMC IP alone cannot establish Redfish support or a ComputerSystem resource. HTTPS verification defaults on; CA paths must exist on the eventual Ironic conductor.

Name is the stable lookup key: keep it unchanged, and preserve an existing Ironic UUID in `extra.uuid` when available. Renaming a device requires updating this mapping. Without a supplied UUID, Ironic assigns one on enrollment. Hardware serial numbers are not treated as Ironic UUIDs. Optional `extra` properties, root-device hints, image/boot/network settings pass through explicitly; we never infer a boot disk from all discovered NVMe drives. Configure these before actual deployment. `automated_clean: false` is an explicit example setting, not a promise that downstream workflows cannot erase disks.

Bifrost consumes this file through `BIFROST_INVENTORY_SOURCE` and its inventory adapter, rather than as a standard `-i baremetal.yml` Ansible inventory. Enrollment and reimaging remain separate, deliberate workflows.

Compatibility: researched upstream Bifrost master inventory parser/example and current Ironic Redfish docs; your installed Bifrost version is unknown. Confirm its enrollment role, enabled drivers/interfaces, network/image requirements, and field support before consuming the file. Export validation checks data shape, not BMC connectivity or image bootability.

Sources: [Bifrost example](https://github.com/openstack/bifrost/blob/master/playbooks/inventory/baremetal.yml.example), [inventory parser](https://github.com/openstack/bifrost/blob/master/bifrost/inventory.py), [Redfish driver contract](https://docs.openstack.org/ironic/latest/admin/drivers/redfish.html).
