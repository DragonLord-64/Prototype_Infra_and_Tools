# Switch container

A lightweight simulated network switch: one Prometheus exporter process,
stdlib-only Python on Alpine, reporting 32 interfaces x 3 values each
(96 series total):

- `switch_interface_rx_bytes_total{interface="ethN"}` — counter, increments
  every half second while the link is up.
- `switch_interface_tx_bytes_total{interface="ethN"}` — counter, same.
- `switch_interface_link_up{interface="ethN"}` — gauge, 1 = up, 0 = down.

All series also carry a `switch` label (the `SWITCH_ID` env var, default
hostname) so Prometheus can tell replicas apart when several are running.

## Running

Part of the shared `demo-monitor-net` Docker network (created by the
Prometheus container's compose file):

```
docker compose -f docker-compose.yml up -d --build
```

Standalone, for local testing without the rest of the stack:

```
docker build -t switch-exporter .
docker run --rm -p 9101:9101 -v "$(pwd)/config:/config:ro" switch-exporter
curl localhost:9101/metrics
```

## Injecting a link failure

```
curl -X POST "localhost:9101/interfaces/eth3/link?state=down"
curl -X POST "localhost:9101/interfaces/eth3/link?state=up"
```

## Config

Mounted read-only from `./config/config.json`:

- `interface_count` (default 32)
- `interface_prefix` (default `eth`)
- `counter_start_min` / `counter_start_max` — starting value range for each
  counter
- `counter_step_min` / `counter_step_max` — random increment applied each
  tick while the link is up
- `tick_seconds` (default 0.5)
