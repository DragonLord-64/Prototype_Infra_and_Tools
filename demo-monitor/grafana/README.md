# Grafana

Grafana for the demo-monitor lab, provisioned entirely from files in this
folder — no manual clicking required.

## Run

Requires the `demo-monitor-net` network and `prometheus` container from
`../docker/docker-compose.yml` to be up first:

```
docker compose -f ../docker/docker-compose.yml up -d
docker compose -f docker-compose.yml up -d
```

Then visit http://localhost:3000 (admin/admin, or browse anonymously —
anonymous viewer access is enabled for the demo).

## Layout

- `docker-compose.yml` — the Grafana service. Joins `demo-monitor-net`
  (external, created by the Prometheus compose file) so it can reach
  Prometheus by container name.
- `provisioning/datasources/` — auto-registers the Prometheus datasource
  (`http://prometheus:9090`, uid `prometheus`).
- `provisioning/dashboards/` — tells Grafana to load any dashboard JSON
  dropped in `dashboards/`.
- `dashboards/demo-monitor.json` — the starter dashboard: server up/load/mem
  from node_exporter, and switch link status + RX/TX rates from the custom
  exporter.

## Pending

The switch-panel queries use the metric names `switch-container` proposed
in DotWorld comms (`switch_interface_link_up`, `switch_interface_rx_bytes_total`,
`switch_interface_tx_bytes_total`, labeled by `interface`). Update the
dashboard's `targets` if the exporter lands with different names or labels.
