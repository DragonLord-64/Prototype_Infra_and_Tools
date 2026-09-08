# Deployments

Runnable services are grouped here by workload.

- [`air-gapped-mirror/`](air-gapped-mirror/) provides Git, Python, and apt mirrors through Helm.
- [`monitoring/`](monitoring/) deploys the Kubernetes monitoring stack.
- [`monitoring-demo/`](monitoring-demo/) is the local Compose monitoring simulation.
- [`netbox/`](netbox/) runs NetBox with PostgreSQL and Valkey through Helm.
- [`package-proxies/`](package-proxies/) deploys the Minikube package caches.
