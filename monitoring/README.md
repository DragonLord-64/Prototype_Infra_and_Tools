# Monitoring

Monitoring is split into three independent prototypes:

- [`values.yaml`](values.yaml) configures `kube-prometheus-stack` for a Kubernetes lab cluster.
- [`ansible/`](ansible/README.md) installs Filebeat on standalone hosts.
- [`demo-monitor/`](demo-monitor/README.md) is a local Docker Compose demo with simulated servers, switches, Prometheus, and Grafana.

## Kubernetes stack

The Helm deployment includes Prometheus, Alertmanager, Grafana, kube-state-metrics, and node-exporter. It uses persistent volumes and does not configure public ingress or an external alert receiver.

From this directory:

```sh
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring

cp k8s/grafana-admin-secret.example.yaml k8s/grafana-admin-secret.yaml
# Replace the example password, then keep this file out of Git.
kubectl apply -f k8s/grafana-admin-secret.yaml

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  -f values.yaml
```

Open Grafana locally:

```sh
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```

Grafana is then available at <http://localhost:3000>. Prometheus and Alertmanager can similarly be forwarded from `svc/monitoring-kube-prometheus-prometheus:9090` and `svc/monitoring-kube-prometheus-alertmanager:9093`.

To monitor a host outside Kubernetes, run node_exporter on that host and add its `host:9100` address under `prometheus.prometheusSpec.additionalScrapeConfigs` in `values.yaml`. Re-run the Helm command after changing values.

Do not expose Grafana, Prometheus, or Alertmanager outside a trusted network without adding ingress authentication and TLS. Configure a real receiver under `alertmanager.config.receivers` before relying on alerts for notification.
