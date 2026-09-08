# Simulated switch exporter

This stdlib-only Python exporter models switch interfaces, VLAN membership, traffic counters, and fixed FPGA links. Metrics are served on port `9101`:

- `switch_interface_rx_bytes_total` and `switch_interface_tx_bytes_total`
- `switch_interface_link_up`
- `switch_vlan_packets_total`
- `switch_interface_vlan_member`

Every series has a `switch` label; interface metrics also have `interface`, and VLAN metrics have `vlan` where applicable.

## Run by itself

From `monitoring/demo-monitor/switch`:

```sh
docker build -t switch-exporter .
docker run --rm -p 9101:9101 \
  -v "$(pwd)/config:/config:ro" switch-exporter
```

In another terminal:

```sh
curl http://localhost:9101/metrics
curl -X POST "http://localhost:9101/interfaces/eth3/link?state=down"
curl -X POST "http://localhost:9101/interfaces/eth3/link?state=up"
```

The component `docker-compose.yml` instead joins an existing `demo-monitor-net` network and does not publish a host port. For the complete lab, use `../docker/docker-compose.yml`.

## Configuration

`config/config.json` controls interface count and prefix, counter ranges and increments, tick rate, VLAN range and per-interface membership, and FPGA peer links. The container mounts this directory read-only. Defaults are also defined in `exporter.py` for omitted settings.

The HTTP API provides `GET /metrics`, `GET /healthz`, link state changes at `POST /interfaces/<name>/link?state=up|down`, and simulated FPGA transmission at `POST /interfaces/<name>/tx` with a JSON body containing `vlan`.
