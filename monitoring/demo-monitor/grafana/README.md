# Grafana dashboards

Grafana is provisioned from this directory: the Prometheus data source is registered automatically and every JSON file in `dashboards/` is loaded on startup.

Run the complete demo from `monitoring/demo-monitor/docker`:

```sh
docker compose up -d --build
```

Open <http://localhost:3000>. Anonymous viewer access is enabled; the local admin credentials are `admin` / `admin`. These settings are for the demo only.

## Layout

- `provisioning/datasources/datasource.yml` points Grafana at `http://prometheus:9090`.
- `provisioning/dashboards/dashboards.yml` loads dashboard JSON from `dashboards/`.
- `dashboards/` contains server, inventory, unit, VLAN, and topology views.
- `docker-compose.yml` is a component-development service that joins an existing `demo-monitor-net` network.

For normal use, start only the complete stack; its Compose file already includes Grafana.
