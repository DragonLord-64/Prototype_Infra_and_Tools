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
