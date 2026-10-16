# Nexus post-POAP provisioning

Run `configure_nexus.yml` after POAP has enabled SSH and configured mgmt0. This
playbook **does not modify IP addresses or interfaces**. It sets the NetBox
hostname, provisions full-privilege local users, applies raw telemetry commands,
and saves the configuration.

## NetBox

Use your existing NetBox dynamic inventory, with the Nexus devices in the
`nexus` group (or pass `-e switch_group=YOUR_GROUP`). Each device's NetBox
name becomes its NX-OS hostname; inventory must supply a reachable
`ansible_host`.

Assign a config context to the switch role (or individual devices) containing
an ordered list of **global configuration-mode** commands:

```yaml
nxos_telemetry_commands:
  - "feature telemetry"
  # Add tested NX-OS telemetry CLI lines, including your collector IP.
```

Hardcode the collector IP in this context for now. Commands requiring nested
configuration modes may need a future structured `parents`/ `lines` design;
don't assume a flat list can enter and exit every NX-OS submode. Confirm that
your NetBox inventory exposes merged `config_context` (or flattened
`nxos_telemetry_commands`).

## Controller-local credentials

Create `credentials/` beside the playbook (or set `nexus_credentials_dir`).
The filename stem is the switch username; every managed user receives
`network-admin`. Examples:

```text
credentials/
  admin.hash
  dragon.pub
  dragon.hash
  automation.pub
```

- `USERNAME.pub`: one or more OpenSSH **RSA or Ed25519 public keys**, one per line. Only the first non-empty line is used; later lines are ignored. Creates
  or updates the named user and configures its SSH key.
- `USERNAME.hash`: one NX-OS type-5 MD5-crypt password hash beginning
  `$1$`. Sets that user's local password.
- `admin.hash` is **required**. The existing `admin` account is retained;
  its password is updated last, after telemetry. No users are deleted.
- A username may have both files. The playbook does not remove previously
  configured keys or passwords when files disappear.

Keep `credentials/` out of version control. Store private SSH keys elsewhere.
Type-5 hashes are a compatibility-oriented prototype choice, **not** a modern
password-storage recommendation. Verify support on your NX-OS release and
migrate to stronger supported methods before production. Don't use
`admin/admin` after takeover.

## Run

```sh
ansible-playbook -i /path/to/netbox-inventory.yml \
  development/switch-poap/configure_nexus.yml \
  -e switch_group=YOUR_SWITCH_GROUP
```

All playbook defaults are inside `configure_nexus.yml`. The initial SSH
login defaults to `admin/admin` unless inventory supplies credentials.
Use `-e nexus_credentials_dir=/secure/path` for another local directory.

**Access warning:** Changing admin's password can invalidate the current
bootstrap credentials. Test on one switch first and verify a *new* SSH login
using the configured key/password after running; do not rely on an existing
SSH session. The playbook has not been tested on live NX-OS hardware.
