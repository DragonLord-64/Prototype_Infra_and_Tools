# Filebeat provisioning

This Ansible project installs containerized Filebeat on standalone servers and sends system, journald, Docker, or Podman logs to Elasticsearch.

The vendored `filebeat` role comes from [`ska_collections.logging.beats`](https://gitlab.com/ska-telescope/sdi/ska-ser-ansible-collections) at commit `9248a0108a22117dfaff82aae002cdb7d5e3d17c` (BSD-3-Clause).

## Run

From `monitoring/ansible`:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

cp inventory.example.ini inventory.ini
cp filebeat-vars.example.yml filebeat-vars.yml
# Replace the examples and CHANGE_ME values before continuing.
ansible-vault encrypt filebeat-vars.yml

ansible-playbook -i inventory.ini playbooks/install-filebeat.yml \
  -e @filebeat-vars.yml --ask-vault-pass
```

Targets need Docker or Podman. The default inventory group is `filebeat_servers`; override it with `-e filebeat_target=my_group`, and use `--limit server01` to select one host.

The example uses an API key and a CA fingerprint. The role expects the API key in its existing base64-encoded form. For mutual TLS, set `elasticsearch_http_authentication: required` and provision the CA, client certificate, and key under `certificates_dir`.

Keep `inventory.ini`, `filebeat-vars.yml`, and all credentials out of Git.
