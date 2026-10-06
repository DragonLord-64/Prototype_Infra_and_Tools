# End-to-end NetBox bootstrap demo

Start from an IP-only YAML inventory, gather facts over existing SSH keys,
and create/update NetBox directly. No CSV or intermediate inventory export.
The tested lab target is one Ubuntu 24.04 container. The controller uses
Python 3.14, Ansible Core 2.20.10, netbox.netbox 3.23.0 and NetBox 4.7.

From the repository root, install the isolated controller environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -r end-to-end-netbox/requirements.txt
.venv/bin/ansible-galaxy collection install -r end-to-end-netbox/requirements.yml -p .ansible/collections
```

If the host's Python lacks ensurepip, the existing environment was bootstrapped
with `python3 -m venv --without-pip .venv` and
`pip --python .venv install -r end-to-end-netbox/requirements.txt`.

From this directory:

```sh
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml --check
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml
```

`--check` gathers real SSH facts and makes only GET requests to NetBox. It
shows desired facts alongside existing device, interface and IP records; it
does not promise an exact object-by-object change plan. Apply ensures the
minimal site, role, manufacturer, device type and OS-version custom field,
then writes discovered devices, interfaces, IPv4 (including aliases), IPv6,
and available MAC addresses. NetBox 4.2+ uses standalone MAC objects and
interface primary-MAC associations. Reruns are idempotent for this demo.
Authentication can update NetBox's token usage timestamp on reads; preview
makes no inventory or change-log writes.

The single playbook uses named discovery, comparison, prerequisite, and apply
blocks, each with explicit privilege settings. `--tags facts` runs discovery only;
`--tags compare` gathers and compares without applying; `--tags apply` gathers,
reads existing inventory, and applies. Add `--check` for a write-free preview.
Discovery is tagged `always` so apply has the facts it needs. Hardware
discovery uses separate `bios`, `bmc`, `ddr`, and `nvme` blocks with
their own sudo/environment settings. `--tags ddr` runs facts plus memory
discovery only; add `--check` to a full run for a NetBox write-free preview.

The device name is the discovered hostname; OS version is `os_version`.
The generic type is a placeholder, not hardware identification. The test
inventory includes loopback addresses; real-target defaults exclude loopback
and link-local addresses. No management primary IP is inferred. Stale records
are preserved. Duplicate hostnames and IP/MAC ownership conflicts stop before
writes; resolving moves is left to explicit review. Vendor SDK discovery and
automatic hardware moves are not included.

The checked-in test inventory has one IP and shared SSH settings. For real
servers, replace that IP list and use the real shared user/key/port settings.
Private local files are ignored: `private/netbox.json` holds the NetBox URL,
modern API token, administrator username and password; the directory is mode
0700 and credentials/key are mode 0600. Supply your own equivalent JSON or
replace `vars_files` with Ansible Vault or another secret source. Never commit
credentials. NetBox is locally reachable at http://127.0.0.1:8000.

## Ubuntu test target

The running Docker container is `netbox-bootstrap-ubuntu`, with SSH on
127.0.0.1:2222 and hostname `netbox-demo-ubuntu`. Only dedicated SSH-key login
is enabled. The server address discovered inside the container is different
from its localhost SSH forwarding address.

To recreate it after explicitly removing the old test container:

```sh
mkdir -p private
chmod 700 private
ssh-keygen -t ed25519 -N '' -f private/test_ed25519
cp private/test_ed25519.pub test-target/authorized_keys
docker build -t netbox-bootstrap-ubuntu test-target
docker run -d --name netbox-bootstrap-ubuntu --hostname netbox-demo-ubuntu --restart unless-stopped -p 127.0.0.1:2222:22 netbox-bootstrap-ubuntu
ssh-keyscan -p 2222 127.0.0.1 > private/known_hosts
```

The private host-key file was obtained from the dedicated local test target;
verify host keys independently when switching to remote servers.

Verification completed: real SSH setup facts; all discovered IPs/interfaces
and primary MAC match NetBox; OS version and hostname match; second apply has
zero changes; preview leaves all inventory records and the change log unchanged.

References: [NetBox collection](https://github.com/netbox-community/ansible_modules),
[MAC module](https://docs.ansible.com/projects/ansible/latest/collections/netbox/netbox/netbox_mac_address_module.html),
[NetBox MAC model](https://netbox.readthedocs.io/en/stable/models/dcim/macaddress/).

## Reproducible NetBox deployment

[`netbox/`](netbox/README.md) contains the pinned Compose configuration and a
local secret generator. It creates an empty NetBox instance; create your
administrator and API token before running the inventory playbook. For the
current session, the already-running NetBox instance and its volumes stay in
place, and the ignored private credential file moved with this demo folder.
Do not start a second stack on the occupied port.

The container has Python, OpenSSH, iproute2, and CA certificates, plus
explicitly simulated hardware commands under `/opt/netbox-demo/bin`. It has
no real dmidecode/ipmitool installation or physical SMBIOS/IPMI device access.

## Simulated hardware test

The checked-in test inventory explicitly sets `hardware_simulation: true`.
Fixtures are synthetic; their motherboard/memory/drive serials use a `DEMO-`
prefix and the BMC IP is documentation-only address space. A marker, Docker
virtualization fact, and dedicated hostname guard simulation. The fixture
command directory is selected only in simulation mode; real-server mode uses
system binaries and sudo. A device tagged as simulated cannot silently become
a real hardware record. No privileged Docker or device mounts are used.

The Dockerfile installs these narrow stubs automatically. They reject all
other argument forms; no IPMI power/control or storage/firmware write command
is implemented. Sources and fixture data live under `test-target/`.

| Exact read command | NetBox mapping |
| --- | --- |
| `dmidecode --type bios` | Server custom field `bios_version` from BIOS Version |
| `ipmitool mc info` | Server custom field `bmc_firmware` from Firmware Revision |
| `ipmitool fru print 0` | `motherboard_part_number` and `motherboard_serial` from Board fields |
| `ipmitool lan print 1` | Server BMC interface/address and `oob_ip`; stored as an individual /32 address |
| `dmidecode --type memory` | Populated DDR5 slots become inventory items with part ID and serial |
| `nvme list -o json` | Flat `Devices` JSON becomes NVMe inventory items with model ID and serial |

`nvme-cli` reports a controller **model identifier**, not a standardized separate
manufacturer part number. This demo uses the fixture's vendor model identifier
as `part_id`; a real fleet may require a vendor-specific part-number source.
Current official nvme-cli non-verbose source confirms these flat JSON fields;
unexpected JSON shapes fail explicitly before mapping.
BMC LAN channel and motherboard FRU ID default to 1 and 0 and are configurable.
Motherboard identifiers describe the board, not a separate BMC chip identity.
No BIOS/firmware or IP fields are invented for DDR5/NVMe components.

The fixtures contain two DDR5 modules, an empty memory slot, and two NVMe
drives. Unknown/missing identifiers are omitted; existing NetBox values are
preserved rather than overwritten with blanks. Failed/missing tools are
reported. Stale components, addresses and MAC objects are not deleted.
Synthetic devices/components are marked explicitly in NetBox.

After building and starting the test target, run:

```sh
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml --check
../.venv/bin/ansible-playbook -i inventory.yml bootstrap.yml
../.venv/bin/python verify-demo.py
```

The verifier checks live SSH hostname/OS/IP/MAC facts, stored hardware mappings,
repeat apply, and no-write
preview/facts/comparison modes against a NetBox record/change-log snapshot.
Missing/unknown BIOS, BMC, motherboard, and partial DDR5 fields were also
tested: existing records stayed unchanged and omissions were reported.
The real-mode read-only flow also passed on this local host with native BIOS
and memory reads (DDR4). BMC, NVMe, DDR5 hardware and FPGA SDK execution still
require the intended-server smoke test.

References: [inventory items](https://docs.ansible.com/projects/ansible/latest/collections/netbox/netbox/netbox_inventory_item_module.html),
[ipmitool commands](https://github.com/ipmitool/ipmitool/blob/master/doc/ipmitool.1.in),
[nvme list](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-list.1).

[REAL_SERVER_RUN.md](REAL_SERVER_RUN.md) gives the one-server smoke-test flow
and real-tool prerequisites. [FPGA_EXTENSION.md](FPGA_EXTENSION.md) supplies a
small copyable discovery block without assuming a vendor SDK command.
