# Nexus 9332D-GX2B to NetBox

`bootstrap-nexus.yml` is a small, separate NX-OS SSH discovery playbook.
It targets the reported product ID `N9K-C9332D-GX2B`; it does not configure,
upgrade, reload, or install software on the switch. NX-OS 10.3 command schemas
are the reference; real switch output has not yet been smoke-tested.

Install the controller dependencies from the repository root:

```sh
.venv/bin/pip install -r end-to-end-netbox/nexus-requirements.txt
.venv/bin/ansible-galaxy collection install -r end-to-end-netbox/nexus-requirements.yml -p .ansible/collections
```

Copy `nexus-inventory.example.yml` to an ignored private inventory and supply
SSH authentication through your existing keys or Vault. The user needs access
to the show commands. Reuse the existing NetBox credentials file:

```sh
cd end-to-end-netbox
../.venv/bin/ansible-playbook -i private/nexus-inventory.yml bootstrap-nexus.yml --check
../.venv/bin/ansible-playbook -i private/nexus-inventory.yml bootstrap-nexus.yml
```

Override `netbox_credentials_file` for another YAML/JSON/Vault file containing
`netbox_url`, `netbox_token`, and optionally `netbox_validate_certs`. Certificate
validation defaults to disabled for consistency with the local lab; enable it
for a verified NetBox TLS endpoint. `bootstrap_site` and `bootstrap_role`
come from inventory because switches do not have the server's local YAML file.
`--tags facts` and `--tags compare` show discovered desired inventory without
NetBox writes; compare is a discovery preview, not a current-NetBox diff.
`--check` also skips every NetBox write. These modes still execute read-only
show commands. NetBox modules run on the controller.

## Mapping

| Discovered fact | NetBox record |
| --- | --- |
| Chassis product ID, serial, hostname | Device type model/part number; device serial/name |
| NX-OS release | Device `operating_system` and `os_version` custom fields |
| BIOS release | Device `bios_version` custom field when reported |
| EPLD versions | Device `epld_version` long-text field, preserving the full component report |
| Fan inventory records | Device `fan_count` (installed fan modules, excluding PSU-internal fans); fan modules with reported IDs |
| PSU product ID and serial | Module type and installed module in the named PSU bay |
| Every reported Ethernet transceiver port | Physical port module bay, including empty reported cages |
| Populated QSFP/SFP | Module type using reported vendor/part; installed module with serial |

The three JSON commands are editable in `nexus_commands` near the top.
`nexus_epld_command` defaults to `show version module 1 epld`; unsupported
output is omitted, preserving the existing field. Set it to an empty string
to skip. A missing BIOS value is also omitted. Empty serials do not overwrite
existing module serials. No identifiers or installed fan counts are invented.
Missing module part IDs are reported and skipped. Existing/stale modules are
not removed when a port becomes empty. Breakout lanes share a physical bay;
conflicting identities stop before writes. No interface types/speeds are guessed.

DACs are treated as the locally reported pluggable module/cable end, including
part and serial. No NetBox Cable object or remote termination is inferred.
To model a whole DAC later, supply verified endpoints and reconcile the
local module records explicitly; a cable serial alone does not prove topology.
The discovery covers every port in the command's output, including the SFP+
ports, rather than assuming only 32 QSFP-DD cages.

Custom fields are small shared schema prerequisites. This playbook creates or
reconciles the listed definitions; review existing definitions with these names
before using a NetBox instance with a different schema. Names must be unique
in their scope; this is not a topology reconciliation or hardware-move tool.

## Verification and sources

Synthetic parser and isolated Ansible-task tests cover two PSUs, six fans, optical and DAC modules,
empty ports, singleton JSON tables, missing values, breakout deduplication,
and rejected malformed identity/output. Recording modules verify write payloads,
read-only preview modes, and repeat-run behavior without contacting NetBox.
These tests do not establish real switch or NetBox API compatibility:

```sh
../.venv/bin/python -m unittest discover -s tests -p 'test_nexus*.py'
```

Sources: [NX-OS 10.3 show command reference](https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/103x/command-reference/show/b_n9k_show_commands_103x.pdf),
[Cisco inventory JSON example](https://developer.cisco.com/docs/nx-api-cli-reference-for-the-cisco-nexus-9000-series-platform/inventory-commands/),
[Cisco transceiver JSON examples](https://developer.cisco.com/docs/nx-api-cli-reference-for-the-cisco-nexus-9000-series-platform/interface-commands/),
[Ansible NX-OS command module](https://docs.ansible.com/projects/ansible/latest/collections/cisco/nxos/nxos_command_module.html).

## DHCP, POAP SSH bootstrap, and Ansible takeover

The [switch-poap folder](development/switch-poap/) contains only three files:

- [configure_bifrost_dhcp.yml](development/switch-poap/configure_bifrost_dhcp.yml)
  writes the two Bifrost DHCP files using existing NetBox inventory variables.
- [poap_script.py](development/switch-poap/poap_script.py) is the same HTTP-served
  script for every switch: enable DHCP on mgmt0 and SSH with admin/admin.
- [configure_nexus.yml](development/switch-poap/configure_nexus.yml) connects over
  SSH and applies the NetBox hostname, physical-interface descriptions/admin
  state, optional configuration-context commands, and saves the configuration.

Assume your working `netbox.netbox.nb_inventory` source has `interfaces: true`.
It supplies `interfaces[].primary_mac_address.mac_address` (or legacy
`mac_address`), `interfaces[].ip_addresses[].address` and `ansible_host`.
Assign one IPv4 address to an enabled mgmt0 and make it the device's primary IPv4.
The default inventory group is `nexus`; use `switch_group` for your existing role
group, for example `device_roles_network_switch`. No additional NetBox requests,
credentials files, serial list, plugins, templates, or generated script are used.

Run the first playbook inside Bifrost, where `/etc/dnsmasq.d` is available:

```sh
ansible-playbook -i /path/to/netbox-inv.yml \
  development/switch-poap/configure_bifrost_dhcp.yml \
  -e switch_group=YOUR_SWITCH_GROUP \
  -e poap_url=http://YOUR_HTTP_SERVER/poap_script.py
```

Only `poap_url` is required beyond the working inventory. `dnsmasq_dir` overrides
the default path if needed. Run for the entire selected group; `--limit` would
replace the shared hosts file with only that subset. Switches are never contacted
by this playbook; writes and a dnsmasq SIGHUP run locally with privilege escalation.
It assumes a single dnsmasq service in the Bifrost container and `pkill` available.
Check mode skips the HUP command and changes; create destination directories
before a first-run check-mode preview.

The files are `bifrost.dhcp-hosts.d/cisco-poap-host` and
`bifrost.dhcp-opts.d/cisco-poap-opts`. The hosts file adds each switch's management
MAC, `id:*`, the `real-nexus-poap` tag, and its NetBox IP reservation. The options
file advertises `poap_url` in option 67. Other Ironic files are untouched. The
reservation must belong to a subnet already served by Bifrost DHCP; existing
DHCP range/router/DNS options and HTTP serving are assumed.

DHCP supplies the initial IP before downloading the script. POAP then schedules
a persistent mgmt0 DHCP/SSH configuration; reservations make that address match
Ansible inventory after POAP too. The script needs no serial-to-IP table or
NetBox access. Upload it to the HTTP repository yourself. To use a controller
key, paste an OpenSSH RSA **public** key into `SSH_PUBLIC_KEY`; no hashing or
private key is needed. admin/admin remains the initial fallback login.
After editing the script, update its Cisco checksum header before serving it:

```sh
python3 development/switch-poap/poap_script.py --checksum
ansible-playbook -i /path/to/netbox-inv.yml \
  development/switch-poap/configure_nexus.yml -e switch_group=YOUR_SWITCH_GROUP
```

The takeover playbook uses existing inventory authentication and defaults missing
username/password to admin/admin. Configure your controller private key through
inventory as usual. Management remains on reserved DHCP. Additional commands can
be stored as an `nxos_config` list in NetBox config context, including your final
admin credential configuration; both native wrapped context and flattened
context variables are supported. Interface VLAN modes, VLAN IDs, routing and
other fabric policy are not inferred; supply their commands in that context.

This replaces the earlier serial-mapping starter. Local validation covers native
inventory consumption, DHCP file rendering/check mode/idempotence, and mocked
POAP and takeover commands. DHCP delivery, exact NX-OS compatibility, SSH login,
and scheduled configuration persistence still need a one-switch hardware test.

Sources: [dnsmasq host reservations and SIGHUP](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html),
[NX-OS DHCP client configuration](https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/104x/configuration/security/cisco-nexus-9000-series-nx-os-security-configuration-guide-release-104x/m-configuring-dhcp.html),
[NX-OS SSH public key configuration](https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/7-x/security/configuration/guide/b_Cisco_Nexus_9000_Series_NX-OS_Security_Configuration_Guide_7x/b_Cisco_Nexus_9000_Series_NX-OS_Security_Configuration_Guide_7x_chapter_0111.html).
