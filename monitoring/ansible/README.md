# Filebeat provisioning

This directory provisions Filebeat on standalone servers and sends their
system, journald, Docker, or Podman logs to Elasticsearch.

The local `filebeat` role was copied from `ska_collections.logging.beats` in
[`ska-ser-ansible-collections`](https://gitlab.com/ska-telescope/sdi/ska-ser-ansible-collections),
commit `9248a0108a22117dfaff82aae002cdb7d5e3d17c` (BSD-3-Clause).
It is intentionally vendored so this prototype can run independently.

## Prerequisites

The target server must already run Docker or Podman. The Ansible controller
also needs the collections used by the selected container engine:

```sh
cd monitoring/ansible
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

## Configure and run

Copy `inventory.example.ini` and `filebeat-vars.example.yml`, then replace all
example addresses and `CHANGE_ME` values. Keep the resulting secrets file out
of Git and encrypt it with Ansible Vault.

```sh
ansible-vault encrypt filebeat-vars.yml
ansible-playbook -i inventory.ini playbooks/install-filebeat.yml \
  -e @filebeat-vars.yml --ask-vault-pass
```

The default inventory group is `filebeat_servers`. Select another group or a
single host with `-e filebeat_target=my_group` and/or `--limit server01`.

The example uses API-key authentication and a CA fingerprint. The SKA role
expects the API-key variable in its existing base64-encoded form and decodes
it when rendering Filebeat's `api_key` setting. For mutual TLS, set
`elasticsearch_http_authentication: required` and provision the CA, client
certificate, and private key under `certificates_dir` before running this
playbook.
