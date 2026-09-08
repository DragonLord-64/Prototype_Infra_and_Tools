# Minimal Elastic Stack and Filebeat provisioning

## Minimal Elastic Stack

`playbooks/install-minimal-elastic-stack.yml` uses Docker to run one
Elasticsearch container and one Kibana container on a single node. It is the
low-volume prototype path: there is no Logstash, HAProxy, Metricbeat,
Prometheus exporter, replication, or multi-node discovery. Elasticsearch data
is retained under `/var/lib/elastic-stack/elasticsearch`.

Copy the example inventory and optionally the stack variables, then run:

```sh
cp inventory.example.ini inventory.ini
cp elastic-stack-vars.example.yml elastic-stack-vars.yml
ansible-playbook -i inventory.ini playbooks/install-minimal-elastic-stack.yml \
  -e @elastic-stack-vars.yml
```

Kibana is available on port `5601` and Elasticsearch on `9200`. Security is
deliberately disabled to keep this prototype minimal, so expose both ports
only on a trusted cluster network or restrict the bind addresses and use an
SSH tunnel. This is not an Internet-facing or production configuration.

The default memory limits are 2 GiB for Elasticsearch (1 GiB Java heap) and
1 GiB for Kibana. The host needs additional memory for its operating system
and Filebeat.

## Filebeat

This Ansible project installs containerized Filebeat on standalone servers and sends system, journald, or Docker logs to Elasticsearch. The prototype is Docker-only.

The vendored `filebeat` role comes from [`ska_collections.logging.beats`](https://gitlab.com/ska-telescope/sdi/ska-ser-ansible-collections) at commit `9248a0108a22117dfaff82aae002cdb7d5e3d17c` (BSD-3-Clause).

## Run

From `automation/ansible`:

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

Targets need a running Docker daemon. The default inventory group is `filebeat_servers`; override it with `-e filebeat_target=my_group`, and use `--limit server01` to select one host.

The example uses unauthenticated HTTP so it can send directly to the minimal
stack above. The vendored role has a small local extension for this mode. For
a secured deployment, use HTTPS with basic authentication, an API key, or
mutual TLS and protect the variables with Ansible Vault.

Keep `inventory.ini`, `filebeat-vars.yml`, and all credentials out of Git.

## MiniCube deployment

The tracked MiniCube configuration deploys the complete low-volume stack and
Filebeat to the local Docker host in one command:

```sh
ansible-playbook -i inventory.minikube.ini playbooks/deploy-minicube-logging.yml \
  -e @minicube-vars.yml
```

This creates `elasticsearch`, `kibana`, and `filebeat` containers. The
Elasticsearch data persists in `/var/lib/elastic-stack/elasticsearch`.
The deployment deliberately has no TLS or authentication and must remain on a
trusted development network.

`playbooks/configure-mirror-client.yml` configures DNS, Git, apt, and pip on a
host that consumes the air-gapped mirror:

```sh
ansible-playbook -i inventory.ini playbooks/configure-mirror-client.yml
```
