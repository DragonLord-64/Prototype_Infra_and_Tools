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
