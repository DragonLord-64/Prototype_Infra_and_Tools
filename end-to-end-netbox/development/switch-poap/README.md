# NetBox to Bifrost DHCP and Cisco POAP

This starter reads selected switches from NetBox and renders three files: a
dnsmasq DHCP hosts file, a DHCP options file, and one shared Cisco POAP Python
script. It does not write to NetBox or contact switches. Copy this entire folder
alongside the [portable NetBox playbooks](../README.md); use their requirements
files for Ansible and `netbox.netbox.nb_lookup` dependencies.

## Configure and run

Copy [site-vars.example.yml](site-vars.example.yml) outside the repository and
replace its serial, gateway, bootfile and served-directory placeholders. Every
setting is exposed in [defaults.yml](defaults.yml), including output paths,
permissions, DHCP tag/option number, management interface/VRF, credentials,
additional NX-OS configuration, script staging paths and CLI import module.
Use `-e @...` to override defaults. Credentials follow the existing imports:
`netbox_url` and `netbox_token` in the file selected by `netbox_credentials_file`.
TLS verification defaults to enabled and can be overridden by
`netbox_validate_certs` in that credential file.

```sh
ansible-playbook netbox_switch_poap.yml \
  -e netbox_credentials_file=/path/to/netbox.yml \
  -e @/path/to/site-vars.yml --check

# First render to a local scratch directory for review.
ansible-playbook netbox_switch_poap.yml \
  -e netbox_credentials_file=/path/to/netbox.yml \
  -e @/path/to/site-vars.yml \
  -e poap_become=false \
  -e poap_hosts_file=/tmp/poap-preview/hosts/cisco-poap-host \
  -e poap_options_file=/tmp/poap-preview/options/cisco-poap-opts \
  -e poap_script_file=/tmp/poap-preview/poap_script.py
```

Run from this folder, inside the Bifrost container when installing its files.
Remove preview path overrides to install at configured paths. Check mode reads
and validates NetBox but does not create outputs or reload dnsmasq. It is most
useful after the destination directories exist; for a first-run preview, render
to scratch as above. Do not request script diffs: it embeds the login password.
Real serials, MACs, IP mappings and generated scripts belong outside Git.

## Source data and generated files

Provide `poap_serials` as a list of device chassis serials. Each must match one
NetBox device, with one enabled interface named by `poap_management_interface`
(default `mgmt0`). The primary MAC is read from `primary_mac_address.mac_address`,
with legacy `mac_address` fallback. Exactly one IPv4 address must be assigned to
that interface; its prefix length is retained. Device `primary_ip4` is not used.
Provide `poap_gateway` or override individual serials in
`poap_gateways_by_serial`. Gateways must be usable addresses in that interface's
subnet. Missing/ambiguous records and duplicate serials, names, MACs or IPs abort
before output files are written. IPv6 records are ignored for address selection.

The templates preserve the tested forms:

```text
<management-mac>,set:<poap_dhcp_tag>
tag:<poap_dhcp_tag>,<poap_dhcp_option>,<poap_bootfile>
```

These are DHCP host tags and bootfile options, not DNS A records or static DHCP
reservations. Existing DHCP ranges, routers, DNS servers and HTTP/TFTP service
remain prerequisites. `poap_bootfile` is emitted verbatim: supply the exact
server/script value already tested, including a scheme if required by your
NX-OS version. `poap_script_file` is the local served file; its path is configured
separately from the bootfile advertised over DHCP.

Each run replaces only the two configured managed files and the script. Other
Ironic files are left alone. Removing a serial from the input removes it from
these generated files. The complete switch set should therefore be supplied on
every run. The script is published first; writes across all three files are not
a single transaction. DNS service reload is disabled by default. Set
`poap_reload_dnsmasq: true` and a nonempty `poap_dnsmasq_reload_argv` list only
after identifying the correct service/container command. Check that the Bifrost
dnsmasq configuration actually loads both directories. A script-only change
does not need a DHCP reload.

## Switch initialization

The generated script reads the NX-OS `POAP_SERIAL` environment variable, selects
its embedded configuration, writes a mode-0600 staging file, and invokes
`copy <config_path> scheduled-config`. An unknown serial exits unsuccessfully
before any file write or CLI operation. NX-OS handles scheduled configuration
replay in its POAP lifecycle. This starter performs no image upgrades and issues
no erase or reload command. Keep the filesystem staging path and CLI path
variables consistent when changing them. Set `poap_cli_import_module: cisco`
for releases whose CLI API is `cisco.cli` instead of `cli.cli`.

The [NX-OS template](templates/nxos.cfg.j2) sets hostname, management IP/prefix,
VRF route, SSH, and the requested `admin/admin` network-admin login. It disables
password strength checking by default to accommodate that initial password.
All are configurable. CLI token validation deliberately excludes whitespace,
quotes, semicolons and other command separators; extend the template if your
credential format requires different escaping. Additional configuration lines
are operator-supplied trusted NX-OS commands. The script gets a Cisco-style
embedded MD5 header computed over its rendered contents excluding that header;
editing the generated file invalidates it.

This is a bootstrap for switches already entering POAP, not a mechanism for
resetting configured switches. Exact model and NX-OS version remain unprovided.
Local tests verify mapping/rendering/checksum and mocked serial selection; they
do not establish password acceptance, SSH key readiness, DHCP delivery, or
scheduled-config replay/persistence on hardware. Test one switch and verify
SSH login and its resulting startup configuration before provisioning the fleet.

Implementation references: Cisco's [POAP overview](https://developer.cisco.com/docs/nx-os/poap/),
[POAP example script](https://github.com/datacenter/nexus9000/blob/master/nx-os/poap/poap.py)
(serial environment, checksum and CLI imports), and
[Nexus 9000 POAP troubleshooting](https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/105x/configuration/troubleshooting/cisco-nexus-9000-series-nx-os-troubleshooting-guide-105x/m-troubleshooting-poweron-auto-provisioning.html)
(scheduled configuration replay).

## Local validation

```sh
python3 -m unittest discover -s tests -v
ansible-playbook netbox_switch_poap.yml --syntax-check
# Also exercise the actual NetBox lookup plugin against a local HTTP fixture:
POAP_RUN_ANSIBLE_TESTS=1 python3 -m unittest discover -s tests -v
```

The opt-in test requires Ansible, pynetbox and the NetBox collection installed.
It verifies check mode, first render, an unchanged second run, the rendered MD5
header, exact lookup filters, and failure before writes for a missing serial.
