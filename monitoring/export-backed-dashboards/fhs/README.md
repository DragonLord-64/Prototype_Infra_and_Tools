# FHS server dashboard

This native Grafana dashboard keeps the component status square and wider readings
panel from the server-health prototype. It queries the captured FHS and node
exporter schemas directly, using datasource UID `export-backed-prometheus`.
The **Server** selector uses `node_name`: FHS and node exporter use different
`instance` ports, so joining them by `instance` would be incorrect.

The replay uses sanitized identities and captured values. Repeated snapshots do
not reproduce historical traffic; interface counter rates settle at zero after
two samples. The source UP panels mean the replay endpoint is reachable, not that
the original hardware has just been contacted.

## What is displayed

| Display | Source label / actual metric names | Coverage |
| --- | --- | --- |
| Component 1 / 2 | `FPGA0` / `FPGA1`; `fpga_temperature_celcius`, fabric/F-tile/card-BMC temperatures, `total_input_power_watts` | Source reports 3 / 6 unavailable readings. |
| PSU 1 / 2 | `PSU1` / `PSU2`; `sts_psu1`, fan and AC-lost flags (and PSU2 equivalents) | Source reports 5 unavailable readings each; no PSU temperature/power/current/voltage samples exist. |
| Fan 1 / 2 | `FAN`; `fan1_rpm`, `fan2_rpm`, `fsc_temperature_celcius` | Source reports 5 unavailable readings. Fan 3–6 are not invented. |
| CPU | `CPU`; `cpu_temperature_celcius`, PROCHOT/trip/MCE flags | Temperature is available; flag encoding is unverified. |
| Memory | `DIMM`; eight `ddr5_*1_temperature_celcius` readings | Hottest DIMM shown; all eight are required for complete coverage. |
| NIC | `NIC`; `nic_temperature_celcius` | No `num_metrics_unavailable` coverage gauge is present for this source. |
| Network LAN | `LAN`; `lan_temperature_celcius` | Temperature only; there is no asserted mapping to an OS interface. |
| Motherboard | `x550_bmc`; board/outlet temperatures | Board temperature health, with source completeness required. |
| BMC telemetry | `x550_bmc`; voltage rails, watchdog/chassis flags | No separate BMC die temperature is supplied; raw flags remain unverified. |
| OS interfaces | `node_network_carrier`, `node_network_up`, RX/TX bytes and error/drop counters | All non-loopback interfaces shown without guessing their relation to hardware labels. |

Metric names intentionally preserve the exporter spelling **`celcius`**. Raw tables
below show FHS values and a filterable subset of node values, including readings
that do not fit the component cards. The Node metric textbox accepts a metric-name
regular expression for the raw node table.

## Health policy and limits

`generate_dashboard.py` contains editable illustrative limits: temperature warning
70 °C, failure 85 °C; fan warning below 4,000 RPM, failure below 1,000 RPM.
These are demonstration values, not equipment specifications. Regenerate the JSON
after changing them:

```bash
python3 fhs/generate_dashboard.py
```

For an actual Prometheus datasource, generate a **separate** live-source copy:

```bash
python3 fhs/generate_dashboard.py --live --output-dir /tmp/fhs-live-dashboards
```

Import `/tmp/fhs-live-dashboards/fhs-export-backed.json` into the destination
Grafana. Its Prometheus datasource must have UID `export-backed-prometheus`;
alternatively replace that UID in the generated JSON with the destination
datasource's actual UID. The live queries expect `job="fhs-exporter"` and
`job="node"`, with the same `node_name` label attached to both scrape targets
including their `up` metric. Adjust those job strings in the generator if your
Prometheus scrape jobs differ. Live mode checks those real source-UP metrics,
removes capture-only text, and does not overwrite the default replay JSON when
the separate output directory above is used. The live/replay copies share a UID,
so import live mode into a separate Grafana or intentionally replace the replay.
Live mode retains the conservative health policy and illustrative limits.

A known temperature/fan failure takes precedence over missing data. Otherwise,
all displayed required readings must exist, the source availability count must be
zero, and a positive total count must exist before Healthy/Degraded is possible.
The memory group additionally requires all eight supplied DIMM metric names.
Incomplete data becomes **Unknown** rather than Healthy. A reachable exporter
alone never proves a component is healthy.

The sample and repository do not establish flag bit meanings. PSU, CPU and BMC
aggregate states therefore remain Unknown unless a separate observed temperature
failure proves failure. Raw flag values remain visible. NIC temperature alone is
also insufficient to assert complete NIC health; its status is Unknown while the
reading remains visible. Confirm flag encoding and equipment limits before using
this policy operationally. No bitstream-present value is represented as link UP.

The unavailable-reading summary sums the exporter's per-source reported numbers;
it is not a count of unique physical sensors. No hardware condition is inferred
from old cumulative interface errors: rates are shown separately.

## Verification

The focused test file emits a `promtool test rules` acceptance suite using the
actual dashboard PromQL. It covers complete Healthy/Degraded data, partial data,
missing readings, stopped replay source, failure precedence, unverified flags,
and the DIMM completeness check:

```bash
python3 -m unittest discover -s tests -p test_fhs_dashboard.py
python3 tests/test_fhs_dashboard.py --write-promql-tests /tmp/fhs-health.test.json
promtool test rules /tmp/fhs-health.test.json
```

JSON is valid YAML for Promtool's test loader. Source-format fidelity tests and
container launch instructions live in the parent directory.
