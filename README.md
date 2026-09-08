# Infrastructure prototypes and tools

This repository collects the infrastructure services and supporting utilities
currently being developed for the lab.

## Layout

- [`air-gapped-mirror/`](air-gapped-mirror/) contains the mirror service, Helm
  chart, images, and integration tests.
- [`monitoring/`](monitoring/) contains the monitoring stack, Ansible roles,
  and the local monitoring demo.
- [`tools/`](tools/) contains standalone utilities, including the NetBox
  inventory importer and local Minikube setup.

## Local Kubernetes

Run `./tools/minikube/setup.sh` to install Minikube and create the current
single-node `monitoring` cluster. See
[`tools/minikube/README.md`](tools/minikube/README.md) for prerequisites and
configuration options.
