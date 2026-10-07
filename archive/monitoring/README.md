# Monitoring: visible component values

Keep this whole folder together. Each component's settings are visible in its own file:

| File | Contents |
| --- | --- |
| [values/prometheus.yaml](../../monitoring/prometheus.yaml) | Switch collector plus eight node9100/custom9101 target pairs, Ceph storage, retention, bundled Alertmanager |
| [values/telegraf.yaml](../../monitoring/telegraf.yaml) | John's Cisco DME listener and Prometheus output |
| [values/elasticsearch.yaml](../../monitoring/elasticsearch.yaml) | Fresh Elasticsearch9.5.5, bds1data volume, existing Secret |
| [values/kibana.yaml](../../monitoring/kibana.yaml) | Kibana9.5.5 overlay for the same Elastic release |
| [values/grafana.yaml](../../monitoring/grafana.yaml) | Optional reference only; current running Grafana is excluded |

Use namespace **mid-cbf-monitoring**. Custom exporter **9101 is provisional**; verify it. Prometheus requests **50G**, retains up to fifteen days, and limits retained blocks to **37GB** (about39.7decimalGB). WAL/head/compaction use additional space;37GB is not a hard total-disk quota. The confirmed block-backed class is **bds1**.

## Review locally

```sh
./monitoring/render.sh prometheus
./monitoring/render.sh telegraf
./monitoring/render.sh elastic
```

With no argument, the helper renders those three releases. **It never renders Grafana by default and never installs, upgrades, applies, or contacts the cluster.** It uses the included pinned chart packages. Edit the visible values and render again; later deploy each reviewed release explicitly after checking existing release ownership and storage. No automatic adoption or data migration is implemented.

## Deploy only the component you choose

These are operator commands, not actions already performed. Check existing Helm release ownership first; use the existing owning release when updating a component, and do not adopt the running Grafana. No full-stack deploy script is included.

```sh
# Choose ONE command; each uses namespace mid-cbf-monitoring.
helm upgrade --install monitoring-prometheus monitoring/reference/umbrella/charts/prometheus-29.35.0.tgz -n mid-cbf-monitoring -f monitoring/values/prometheus.yaml
helm upgrade --install switch-telegraf monitoring/reference/umbrella/charts/telegraf-1.8.77.tgz -n mid-cbf-monitoring -f monitoring/values/telegraf.yaml
helm upgrade --install logging monitoring/elastic-small -n mid-cbf-monitoring -f monitoring/values/elasticsearch.yaml -f monitoring/values/kibana.yaml
# Only if you deliberately want a NEW separate Grafana instance:
helm upgrade --install optional-grafana monitoring/reference/umbrella/charts/grafana-13.2.7.tgz -n mid-cbf-monitoring -f monitoring/values/grafana.yaml
```

Only a chosen Elastic installation needs `elastic-credentials`; only optional Grafana needs `monitoring-grafana-admin`. Prometheus/Telegraf need neither login Secret in these values. The namespace and storage prerequisites must already exist.

Elasticsearch and Kibana share the local [elastic-small chart](elastic-small/README.md). Use both values overlays in one release; Elasticsearch-only rendering omits Kibana. For a new Elasticsearch-only installation, omit the Kibana overlay. On a release that already includes Kibana, applying only the Elasticsearch file sets Kibana disabled and can remove it, so keep both overlays whenever Kibana is desired. The existing `elastic-credentials` Secret and Elasticsearch node prerequisites are still required. These files are a fresh install, not an upgrade of older Elastic data.

## Keep existing Grafana

Leave its deployment and Helm release unchanged. When central Prometheus is available, manually add a Prometheus data source in the existing Grafana pointing to:

`http://monitoring-prometheus.mid-cbf-monitoring.svc:9090`

That address is reachable from Grafana inside the cluster; an external Grafana needs an appropriate private reachable endpoint. [dashboards/switch-dashboard.json](dashboards/switch-dashboard.json) is an optional classic-format adaptation of John's three tables with datasource UID `prometheus`. Match that UID on the new data source or select the intended source during import. The [Slack alert template](node-exporter-slack.yaml) and [its setup guide](SLACK.md) are separate; do not change Grafana provisioning or enable Slack before the administrator supplies the Secret.

## Authentication

Prometheus9090 and Telegraf's metrics9273 currently have **no endpoint authentication configured**. Telegraf has no web UI and no default username/password. Its DME listener57000 also has no authentication/TLS in these values. Grafana's existing login is separate; adding a Prometheus data source does not add authentication to Prometheus itself.

If endpoint authentication is required later, configure a Prometheus web-config file or an authenticated proxy and reference credentials through Secrets. For Telegraf, configure the relevant plugin's supported credentials/TLS. Never put real credentials in these values. Elasticsearch/Kibana already use Secret-backed authentication; no Secret values are printed or included here.

The prior [umbrella chart](reference/umbrella/README.md), [upstream source](upstream-switch/README.md), and [design](DESIGN.md) remain references. They are not the default deployment interface. The optional Grafana values can be inspected with `render.sh grafana`; that still only renders and does not change the running instance.
