# Real-server first run

The end-to-end simulation has populated NetBox and passed repeat/no-write tests.
The complete real-mode `--check` flow also passed locally without inventory
writes, using native dmidecode BIOS/memory reads; this host has DDR4. Real BMC/IPMI and NVMe execution, DDR5 hardware, and an FPGA
SDK still need a smoke test on the intended server. No other servers were contacted.

Copy `inventory.real.example.yml` to the ignored `private/` directory. Replace
the documentation IPs and SSH user/key, choose the shared site/role/type, and
keep `hardware_simulation: false`. Use one shared site/type/role per run.
Ensure SSH host keys are trusted separately. Targets need Python 3.9+, working
sudo for hardware reads, and dmidecode/ipmitool/nvme-cli for the selected blocks.
The local IPMI driver/device must already be available; this playbook does not
install packages, load drivers, pass devices through Docker, or change firmware.

Put the real NetBox URL and full API token in `private/netbox.json`, or change
the playbook's secret source to your Vault/secret store. Use trusted HTTPS for
remote NetBox. The tested combination is NetBox 4.7, netbox.netbox 3.23.0,
pynetbox 7.8 and Ansible Core 2.20.10; standalone MAC objects require NetBox 4.2+.
The token needs read/create/update access to the prerequisite and inventory
models. Existing manually maintained fields not named in the mapping are preserved.

From this folder, select one real target first:

```sh
../.venv/bin/ansible-playbook -i private/inventory.real.yml bootstrap.yml --limit YOUR_IP --tags facts
../.venv/bin/ansible-playbook -i private/inventory.real.yml bootstrap.yml --limit YOUR_IP --tags bios,bmc,ddr,nvme
../.venv/bin/ansible-playbook -i private/inventory.real.yml bootstrap.yml --limit YOUR_IP --check
```

These discovery/preview runs do not write inventory. `--check` reads the real
hardware commands, displays current and desired records, and stops on detected
IP/MAC ownership conflicts or ambiguous device names. Address overlap across
VRFs/sites requires a deliberate design; this minimal bootstrap does not
resolve it automatically. Loopback/link-local addresses are excluded by default.
Bond/VLAN/shared-MAC topologies also require explicit interface identity review.
BMC LAN channel and motherboard FRU ID are configurable inventory variables.

Review tool stderr and parsed fields, validate the BMC channel/FRU selection,
set `bootstrap_primary_ipv4` to a discovered management address if the
first eligible LAN IP is not appropriate, then apply the same selected target
without `--check`. Run it again and require
zero changes. Expand the inventory only after this smoke test. Prerequisites
(site, role, generic type, and custom fields) are ensured during apply; the
hardware type remains a placeholder unless you configure a real type.

The script preserves unavailable fields and stale records. It does not move
existing IP/MAC assignments, infer cabling, or promise to reconcile hardware
replacement. NVMe entries identify namespace paths and reported model/serial;
multiple namespaces of one physical drive need an explicit identification policy.
[FPGA_EXTENSION.md](FPGA_EXTENSION.md) shows how to add one reviewed read-only
SDK block once its exact command, output format, privileges and environment are known.
