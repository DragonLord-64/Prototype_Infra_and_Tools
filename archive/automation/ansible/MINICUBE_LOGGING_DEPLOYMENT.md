# MiniCube logging deployment

Last verified: 2026-09-08

## Deployment

The local `monitoring` Minikube profile and the logging services share the
same Docker host. The complete deployment is reproducible with:

```sh
cd automation/ansible
sudo -g docker .venv/bin/ansible-playbook \
  -i inventory.minikube.ini \
  playbooks/deploy-minicube-logging.yml \
  -e @minicube-vars.yml
```

The playbook completed with 30 successful tasks, 7 changes, and no failures.

## Verified services

| Service | Image/version | State | Access |
| --- | --- | --- | --- |
| MiniCube | Minikube `monitoring`, Kubernetes v1.37.0 | Control plane, kubelet, and API server running | Docker network `monitoring`, `192.168.49.2` |
| Elasticsearch | `docker.elastic.co/elasticsearch/elasticsearch:9.3.3` | Running; all primary shards active | `http://127.0.0.1:9200` |
| Kibana | `docker.elastic.co/kibana/kibana:9.3.3` | Running; overall status `available` | `http://127.0.0.1:5601` |
| Filebeat | `docker.elastic.co/beats/filebeat:9.3.3` | Running; Elasticsearch connection established | No published port |

Filebeat collects local system, journald, and Docker container logs. At final
verification the `minicube-9.3.3` data stream contained more than 500,000
documents, confirming end-to-end ingestion.

Elasticsearch reports `yellow`, as expected for this single-node deployment:
all primary shards are active and the only unassigned shard is a replica that
cannot be placed on the same node.

## Resource and storage notes

- Elasticsearch is limited to 2 GiB RAM with a 1 GiB Java heap.
- Kibana is limited to 1 GiB RAM.
- Filebeat is limited to 512 MiB RAM and its Docker logs rotate at 10 MiB with
  three files retained.
- Elasticsearch data persists at `/var/lib/elastic-stack/elasticsearch`.
- Elasticsearch disk allocation protection remains enabled. Final
  verification showed 7.9 GiB free on the 62 GiB host filesystem.

This is a trusted-development-network configuration. Elasticsearch security
is disabled, but both HTTP services bind only to loopback. Use an SSH tunnel
for remote access and do not publish ports 9200 or 5601 to an untrusted
network.
