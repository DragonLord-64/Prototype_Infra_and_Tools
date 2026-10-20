# Synthetic server health source

This dependency-free demo contains invented readings for **14 components**.
It does not inspect a real server. The configured limits are demonstration values,
**not hardware specifications or validated operating limits**.

Run `python3 exporter.py`. It listens on `0.0.0.0:9100`.
`GET /metrics` serves Prometheus text; `GET /health` confirms valid configuration.
Each request reloads `mock-health.json`. Save edits atomically to avoid reading a
partial write. Invalid configuration returns HTTP 503 without stale metrics.
Missing readings are valid: `/health` remains 200 and metric health is unknown.

The JSON contains `synthetic: true`, `server: "demo-server-01"`, shared `limits`,
and exactly the supplied 14 `components`. Component objects contain readings only;
there is no manually set health field. An empty component object is allowed.
All readings and limits must be finite numbers. RPM, watts, volts and amperes
must be nonnegative. `link_up` must be integer `0` or `1`, not Boolean.

Required readings by component kind:

| Kind | Readings |
| --- | --- |
| FPGA, NIC | temperature_celsius, link_up |
| PSU | temperature_celsius, power_watts, voltage_volts, current_amperes |
| Fan | fan_rpm |
| Motherboard, BMC | temperature_celsius |
| Network LAN | link_up |

Other readings are rejected for each kind. A missing required reading produces
`unknown` for that metric; no raw sample is emitted for the missing reading.
Health states are `0 healthy`, `1 degraded`, `2 failed`, `3 unknown`.
The component rollup uses this precedence: **failed, unknown, degraded, healthy**.

```text
server_component_metric_health{server="demo-server-01",component="fan-4",kind="fan",metric="fan_rpm"} 1
server_component_health{server="demo-server-01",component="fan-4",kind="fan"} 1
server_component_fan_rpm{server="demo-server-01",component="fan-4",kind="fan"} 5100
```

The file initially makes fan-4 degraded (5100 RPM); everything else is healthy.
Limits use strict comparisons: `warning_above` / `failed_above` mean `>`;
`warning_below` / `failed_below` mean `<`. Failed conditions are evaluated first.
Equality at a threshold does not cross that threshold. Warning/failed pairs must
be strictly ordered, and voltage ranges must be nested. `link_up` has the fixed
condition `failed_equals: 0`; a link value of 1 is healthy.

| Metric | Degraded condition | Failed condition |
| --- | --- | --- |
| Temperature | >75 °C | >90 °C |
| Fan speed | <6000 RPM | <3000 RPM |
| PSU power | >450 W | >550 W |
| PSU voltage | <11.4 or >12.6 V | <10.8 or >13.2 V |
| PSU current | >37.5 A | >45.83 A |
| Link | — | 0 (down) |

Raw metrics use the prefix `server_component_` plus the JSON reading name.
The `server_health_demo_info{synthetic="true",...}` metric marks the source as
synthetic. HELP descriptions also identify invented values.

For Prometheus on the same Docker network with exporter service `health-exporter`:

```yaml
scrape_configs:
  - job_name: synthetic-server-health
    scrape_interval: 5s
    static_configs:
      - targets: ['health-exporter:9100']
```
