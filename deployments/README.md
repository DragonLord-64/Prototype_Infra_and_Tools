# Deployments

Runnable services are grouped here by workload.

- [`air-gapped-mirror/`](air-gapped-mirror/) provides Git, Python, and apt mirrors through Helm.
- [`monitoring/`](monitoring/) deploys the Kubernetes monitoring stack.
- [`monitoring-demo/`](monitoring-demo/) is the local Compose monitoring simulation.
- [`package-proxies/`](package-proxies/) deploys the Minikube package caches.

NetBox deployment files should be added as `deployments/netbox/`; its data
utilities already live under `tools/netbox/`.
