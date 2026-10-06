# Direct NetBox bootstrap, v1

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
Discovery is tagged `always` so apply has the facts it needs. Future hardware
groups can be added as separate tagged discovery blocks with their own sudo and
environment settings. No hardware group is implemented yet.

The device name is the discovered hostname; OS version is `os_version`.
The generic type is a placeholder, not hardware identification. This v1
includes loopback and link-local addresses as discovered, and does not choose
a management primary IP. It does not delete stale records or resolve hostname,
IP or MAC collisions/moves. Review before using against real fleets, especially
where loopback/link-local addresses repeat across hosts. No hardware/vendor
SDK collection is included.

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

The container currently has Python, OpenSSH, iproute2, and CA certificates.
It has no dmidecode or ipmitool, physical SMBIOS table access, or IPMI device
passthrough. Hardware inventory is not part of this committed demo.
