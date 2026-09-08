# Switch container

A lightweight simulated network switch: one Prometheus exporter process,
stdlib-only Python on Alpine, reporting 32 interfaces x 3 values each
(96 series total), plus hundreds of simulated VLANs:

- `switch_interface_rx_bytes_total{interface="ethN"}` — counter, increments
  every half second while the link is up.
- `switch_interface_tx_bytes_total{interface="ethN"}` — counter, same.
- `switch_interface_link_up{interface="ethN"}` — gauge, 1 = up, 0 = down.
- `switch_vlan_packets_total{vlan="N"}` — counter, one series per VLAN on
  the switch (default 300, IDs starting at 100). Switch-wide and agnostic
  of any particular interface; increments every tick regardless of link
  state.
- `switch_interface_vlan_member{interface="ethN",vlan="N"}` — gauge, always
  1. Present only for VLANs actually trunked on that interface (absent =
  not a member), so cardinality stays proportional to actual membership
  rather than the full interface x VLAN matrix. Each interface is randomly
  assigned a subset of the switch's VLANs at startup (6-60 of them,
  configurable).

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
- `vlan_count` (default 300) — total VLANs on the switch
- `vlan_id_start` (default 100) — first VLAN id; ids run sequentially from
  there
- `vlan_min_per_interface` / `vlan_max_per_interface` (default 6 / 60) —
  range for how many VLANs are randomly trunked onto each interface at
  startup
- `vlan_counter_start_min` / `vlan_counter_start_max` — starting value
  range for each VLAN's counter
- `vlan_counter_step_min` / `vlan_counter_step_max` — random increment
  applied to each VLAN's counter every tick (unconditionally, unlike the
  per-interface counters)
