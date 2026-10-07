# Historical umbrella reference

The current interface is [visible component values](../../README.md). Do not use this chart to adopt or upgrade existing Grafana. Its Grafana dependency is disabled by default. Vendored packages preserve this reference; the original local dependency path is historical, so use current component sources rather than regenerating dependencies here.

# One monitoring Helm release

This umbrella chart combines Prometheus, Telegraf, Grafana, Alertmanager, and the local Elasticsearch/Kibana chart. Copy the entire `monitoring/` folder; dependencies and their lockfile are included. No controller-side chart download is needed for lint/render/install; regenerating dependencies requires access to their chart repositories.

## Configuration

Edit [values.yaml](values.yaml). Its `servers` list contains the eight supplied addresses, with node_exporter on 9100 and the custom exporter on **9101 provisionally**. Both jobs use `/metrics`; confirm that custom port/path before applying. A per-server port override is available. No node_exporter or custom exporter is installed on those servers, and no per-server Prometheus is created. `host` defaults to the supplied address unless a name is supplied.

The rendered jobs are `node`, `fhs`, and `switch-telegraf`. Grafana's provisioned `prometheus` data source connects directly to the central Prometheus service in the Helm release namespace. The namespace is **mid-cbf-monitoring**, supplied by the Helm invocation; chart templates do not create namespaces or modify Ceph.

Prometheus uses **bds1** (the confirmed Ceph RBD class), requests **50G** (fifty decimal gigabytes), retains up to fifteen days, and sets `--storage.tsdb.retention.size=37GB` (about39.7 decimal GB). That limit governs retained database blocks; WAL/head/compaction need the remaining space. It is not a hard37GB total filesystem quota. Verify the actual PV allocation and cluster free capacity separately. Grafana, Alertmanager, and Elasticsearch also use bds1; their independent claims are2Gi,1Gi,20Gi.

Create two existing Secrets in that namespace through your normal secret mechanism: `monitoring-grafana-admin` (`admin-user`, `admin-password`) and `elastic-credentials` (keys described in [the Elastic guide](../../elastic-small/README.md)). No credentials are embedded in this chart. The Elastic chart is a **fresh9.5.5 installation**, not a migration of existing older volumes.

Slack stays disabled until the administrator supplies `monitoring-slack`, key `webhook-url`. Set `slack.enabled: true` afterwards. Grafana then provisions the two-minute node-exporter alert and Slack contact point directly; it does not replace the notification-policy tree. Alertmanager starts with a receiver that sends nowhere. The working notification route is Grafana-managed; do not enable a duplicate Alertmanager Slack route for the same alert.

## Review and deploy

From the repository root, review locally:

```sh
helm lint monitoring/chart
helm template mid-monitoring monitoring/chart -n mid-cbf-monitoring
```

Before using the deployment command, map the existing separate releases and their volumes to this new release. Helm does not automatically adopt their resources, and this chart does not migrate Grafana state, metrics, or older Elastic data. Disable a component via its `enabled` value when continuing to use an existing separately managed instance, and point the dependent data source/scrape endpoint at that instance. Do not install a second working monitoring stack accidentally.

Once release ownership, Secrets, free storage, and Elasticsearch node prerequisites are ready, deploy explicitly:

```sh
helm upgrade --install mid-monitoring monitoring/chart \
  -n mid-cbf-monitoring --create-namespace --wait --wait-for-jobs --timeout 10m
kubectl -n mid-cbf-monitoring port-forward service/monitoring-grafana 3000:80
```

Prometheus/Grafana/Alertmanager/Elastic services are cluster-local. Telegraf alone retains the switch's gRPC LoadBalancer listener. Supply its actual reachable address in the switch's existing telemetry configuration; none is guessed or changed here.

All rendered application images are pinned Docker Hub images. Unneeded config-reloader/sidecar/test/chown helpers are disabled. ConfigMap target changes are picked up by Prometheus file discovery; rule/main-config changes require an explicit reload or normal rollout because auto-reload helpers are disabled. Secrets and Grafana's mounted alert file likewise require a normal pod restart/reprovision after changes.

John's v2 dashboard export is retained unchanged in `../../upstream-switch/`. This chart includes a classic file-provisioning adaptation: same three tables, queries, transformations, and field settings; the data-source UID is set to `prometheus`. That removes its dependency on John's instance-specific UID. The source license is retained in `files/LICENSE.SKAPROTOTYPING`.

Pinned Helm dependencies: Prometheus29.35.0, Grafana13.2.7, Telegraf1.8.77, local Elastic0.1.0. This is reviewed local configuration; no live deployment or upgrade was performed. Rendering tests cover service endpoints, all eight pairs of scrape targets, retention/PVC limits, namespace, images, dashboard queries, optional Slack and disabled components.
