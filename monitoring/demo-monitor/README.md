# Demo monitor

A self-contained Docker Compose lab for exploring Prometheus and Grafana. Six simulated server units and three simulated switches publish metrics to Prometheus; Grafana loads the included dashboards automatically.

Each server runs node_exporter plus a small Python exporter for changing test values and FPGA-link counters. Each switch exporter models interface status, traffic, VLAN membership, and VLAN traffic. All custom telemetry is simulated.

## Run the complete demo

From `monitoring/demo-monitor/docker`:

```sh
docker compose up -d --build
docker compose ps
```

- Grafana: <http://localhost:3000> (`admin` / `admin`, or anonymous viewer)
- Prometheus: <http://localhost:9090>

Stop the stack with `docker compose down`. Add `-v` only when you also want to delete the Prometheus and Grafana volumes.

## Layout

- `docker/docker-compose.yml` runs the complete demo.
- `server/` contains the combined node and custom server exporter image.
- `switch/` contains the simulated switch exporter and its controls.
- `prometheus/` contains scrape configuration and alert rules.
- `grafana/` contains provisioned data sources and dashboards.

The server, switch, and Grafana directories also contain focused Compose files for component development. These join the external `demo-monitor-net` network; the complete stack creates that network automatically.

Configuration is mounted from `server/config/` and `switch/config/`, so most simulation changes do not require rebuilding images. See [`switch/README.md`](switch/README.md) for link-failure injection and switch metrics.
