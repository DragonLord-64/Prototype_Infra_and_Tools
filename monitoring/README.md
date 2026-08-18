# Monitoring

Prometheus, Alertmanager, and Grafana for the lab, deployed via the
`prometheus-community/kube-prometheus-stack` Helm chart. The chart bundles
the Prometheus Operator, CRDs, default alert rules, kube-state-metrics,
and a node-exporter DaemonSet.

## What you get

| Component | Role |
| --- | --- |
| Prometheus Operator | Manages Prometheus/Alertmanager via CRDs (`ServiceMonitor`, `PodMonitor`, `PrometheusRule`) |
| Prometheus | Scrapes and stores metrics, 15d retention, 20Gi PVC |
| Alertmanager | Routes alerts (no external receiver wired up yet -- see `values.yaml`) |
| Grafana | Dashboards, credentials from a Secret, 5Gi PVC |
| kube-state-metrics | Cluster object state (pods, deployments, etc.) as metrics |
| node-exporter | DaemonSet, one per k8s node, host-level metrics |

## Install

Requires internet-reachable nodes (this is the normal-access cluster, not
the `air-gapped-mirror` one).

```sh
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring
# copy k8s/grafana-admin-secret.example.yaml to k8s/grafana-admin-secret.yaml
# (gitignored), set a real password, then:
kubectl apply -f k8s/grafana-admin-secret.yaml

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  -f values.yaml
```

Re-run the `helm upgrade --install` line whenever `values.yaml` changes.

## Accessing Grafana

No Ingress by default -- it's an internal lab tool.

```sh
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```

Then browse to `http://localhost:3000` with the admin credentials from
`grafana-admin-secret.yaml`. Prometheus and Alertmanager UIs work the
same way, via `svc/monitoring-kube-prometheus-prometheus` (port 9090) and
`svc/monitoring-kube-prometheus-alertmanager` (port 9093).

## Adding non-Kubernetes lab servers

The chart's node-exporter DaemonSet only covers nodes that are in the k8s
cluster. A small lab usually has other machines worth monitoring too --
a NAS, a hypervisor host, a switch's management OS, bare-metal boxes not
running k8s at all. For each of those:

1. Install and run [`node_exporter`](https://github.com/prometheus/node_exporter)
   on the host, listening on `:9100`.
2. Add `host:9100` to the `targets` list under
   `prometheus.prometheusSpec.additionalScrapeConfigs` in `values.yaml`.
3. Re-run the `helm upgrade --install` command above.

These targets are just internal IPs/hostnames, so they're tracked
directly in `values.yaml` rather than in a gitignored file.

## Alerting

`alertmanager.config` in `values.yaml` currently has no external
receiver -- alerts fire and are visible in the Alertmanager/Grafana UI,
but nothing pages anyone. Wire up a receiver (Slack webhook, email, etc.)
under `alertmanager.config.receivers` once you know where notifications
should go; the chart's default `PrometheusRule`s (`defaultRules.create:
true`) already cover the common host/cluster alert conditions.

## Security notes

- Grafana admin credentials live in a gitignored Secret
  (`k8s/grafana-admin-secret.yaml`), never in `values.yaml`.
- No Ingress/external exposure is configured -- reach everything via
  `kubectl port-forward` from inside the trusted lab network, or add your
  own Ingress/auth in front if you need always-on access.
- Prometheus and Alertmanager have no auth of their own by default (same
  trust model as the rest of this repo's internal-network services) --
  don't expose their Services outside the cluster without adding one.
