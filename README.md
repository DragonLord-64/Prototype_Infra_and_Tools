# Infrastructure prototypes and tools

This repository contains the small-cluster platform, deployable services,
host automation, and operator tools used by the lab.

## Layout

| Path | Purpose |
| --- | --- |
| [`platform/`](platform/) | Create and manage the local Kubernetes platform |
| [`deployments/`](deployments/) | Kubernetes, Helm, and Compose workloads |
| [`automation/`](automation/) | Ansible playbooks, roles, inventories, and variables |
| [`tools/`](tools/) | NetBox data utilities and other standalone tools |

Start with [`platform/minikube/`](platform/minikube/) to create the mini
cluster, then choose a workload under [`deployments/`](deployments/). NetBox
CSV tooling lives under [`tools/netbox/`](tools/netbox/).

## Default test environment

`./default-environment/up.sh` reconciles the complete lab. It creates the
`monitoring` Minikube profile; deploys Git, APT, and pip proxies, Grafana, and
NetBox there; starts host-local Elasticsearch and Kibana; and creates one
Docker test server with proxy settings, Filebeat, Prometheus, and
node_exporter. Set `PROTOTYPING_REPO` if `ska-mid-cbf-prototyping` is not a
sibling checkout. Docker, Helm, Python 3, curl, and OpenSSL are prerequisites.

| Part | Location / access |
| --- | --- |
| Minikube workloads | `deployments/{package-proxies,grafana,netbox}/` |
| Elasticsearch and Kibana | `automation/ansible/`; `127.0.0.1:9200` / `:5601` |
| Test server | `automation/ansible/tests/`; stable Minikube-network IP `192.168.49.3` |
| Prometheus / node_exporter | Test server ports `9090` / `9100`; Grafana reads Prometheus |
| Grafana | `http://$(minikube -p monitoring ip):30300` |
| NetBox | `kubectl -n netbox port-forward service/netbox 8000:80` |

Generated NetBox credentials are kept in the ignored file
`default-environment/default-environment.env`. Run
`./default-environment/status.sh` for a short health and endpoint summary.
