# Grafana

This standalone deployment runs Grafana on the local Minikube cluster. It is
separate from `kube-prometheus-stack`, allowing it to use an existing test
Prometheus instance without creating another Prometheus server.

## Deploy

From the repository root:

```sh
./deployments/grafana/deploy.sh
```

The first run generates an admin password and prints it once. To choose the
initial credentials instead, set them before the first deployment:

```sh
GRAFANA_ADMIN_USER=admin GRAFANA_ADMIN_PASSWORD='replace-me' \
  ./deployments/grafana/deploy.sh
```

The script preserves the existing Kubernetes Secret on subsequent runs. Set
`MINIKUBE_PROFILE` to target a profile other than `monitoring`.

Open the URL printed by the script, normally:

```text
http://$(minikube -p monitoring ip):30300
```

Grafana data is stored in a 2 GiB persistent volume claim. The service is a
Minikube NodePort and should only be exposed on a trusted development machine.

Grafana discovers the test container's `monitoring` network address and
provisions its port `9090` as the default Prometheus data source. Set
`PROMETHEUS_URL` to override it. Grafana uses server-side proxy access, so the
address must be reachable from the Minikube cluster.

The deployment also provisions a **Node Exporter Overview** dashboard in the
**Infrastructure** folder. It provides at-a-glance target status, uptime, CPU,
memory, load, disk, filesystem, and network panels. Its **Active problems**
table reports unreachable node-exporter targets, filesystem device errors, and
textfile collector scrape errors dynamically from Prometheus.

## Inspect

```sh
minikube -p monitoring kubectl -- -n grafana get pods,service,pvc
minikube -p monitoring kubectl -- -n grafana logs deployment/grafana
```
