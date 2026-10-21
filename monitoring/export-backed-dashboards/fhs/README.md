# FHS server dashboard

This native Grafana dashboard keeps the component status square and wider readings
panel from the server-health prototype. It queries the captured FHS and node
exporter schemas directly, using datasource UID `export-backed-prometheus` in the replay lab. The
[portable live copy](../live-import/README.md) uses the selected Prometheus datasource.
The **Server** selector uses `node_name`: FHS and node exporter use different
`instance` ports, so joining them by `instance` would be incorrect.

The replay uses sanitized identities and captured values. Repeated snapshots do
not reproduce historical traffic; interface counter rates settle at zero after
two samples. The source UP panels mean the replay endpoint is reachable, not that
the original hardware has just been contacted.

## What is displayed

| Display | Source label / actual metric names | Coverage |
| --- | --- | --- |
| FPGA 0 / 1 | `FPGA0` / `FPGA1`; `fpga_temperature_celcius`, fabric/F-tile/card-BMC temperatures, `total_input_power_watts` | Source reports 3 / 6 unavailable readings. |
| PSU 1 / 2 | `PSU1` / `PSU2`; `sts_psu1`, fan and AC-lost flags (and PSU2 equivalents) | Source reports 5 unavailable readings each; no PSU temperature/power/current/voltage samples exist. |
| Fan 1 / 2 | `FAN`; `fan1_rpm`, `fan2_rpm`, `fsc_temperature_celcius` | Source reports 5 unavailable readings. Fan 3–6 are not invented. |
| CPU | `CPU`; `cpu_temperature_celcius`, PROCHOT/trip/MCE flags | Temperature is available; flag encoding is unverified. |
| Eight DIMMs | `DIMM`; individual A1, B1, C1, E1, G1, H1, I1, K1 `ddr5_*1_temperature_celcius` readings | Each DIMM has its own temperature and sensor status. |
| NVMe 0 / 1 | Node Exporter `node_nvme_info`, `node_hwmon_temp_celsius`, disk read/write byte counters | Individual controller state, composite/hottest temperatures, plus I/O rates. Missing telemetry remains Unknown. |
| NIC | `NIC`; `nic_temperature_celcius` | The supplied capture includes total/unavailable coverage gauges; a complete cool reading can be OK. |
| Network LAN | `LAN`; `lan_temperature_celcius` | Temperature only; there is no asserted mapping to an OS interface. |
| Motherboard | `x550_bmc`; board/outlet temperatures | Board temperature health, with source completeness required. |
| BMC telemetry | `x550_bmc`; voltage rails, watchdog/chassis flags | No separate BMC die temperature is supplied; raw flags remain unverified. |
| OS interfaces | `node_network_carrier`, `node_network_up`, RX/TX bytes and error/drop counters | All non-loopback interfaces shown without guessing their relation to hardware labels. |

Metric names intentionally preserve the exporter spelling **`celcius`**. Raw tables
below show FHS values and a filterable subset of node values, including readings
that do not fit the component cards. OS interfaces are discovered for the selected node endpoint rather than fixed
to seven/eight names. The supplied snapshot contains three non-loopback OS
interfaces; FPGA or BMC ports absent from Node Exporter require additional
telemetry and a verified mapping. `node_network_up` is operational state; it is
not treated as administrative configuration.

The Node metric textbox accepts a metric-name
regular expression for the raw node table.

## Health policy and limits

`generate_dashboard.py` contains editable illustrative limits: temperature warning
70 °C, failure 85 °C; fan warning below 4,000 RPM, failure below 1,000 RPM.
These are demonstration values, not equipment specifications. Regenerate the JSON
after changing them:

```bash
python3 fhs/generate_dashboard.py
```

For an actual Prometheus datasource, import the checked-in
[live dashboard](../live-import/fhs-export-backed.json) and choose Datasource,
FHS job, Nodename and FHS instance. Node job and Node instance follow that same
Nodename using their own endpoint. All dropdowns discover values from Prometheus;
no private server identity, replay job, or lab datasource UID is embedded in the
live definition. See the [import guide](../live-import/README.md) for details.
Regenerate it with `python3 fhs/generate_dashboard.py --live` from the parent
folder; the default destination is `live-import/`.

A known temperature/fan failure takes precedence over missing data. Otherwise,
all displayed required readings must exist. FHS cards additionally require a zero
unavailable count and positive total for their source. Each DIMM uses its own
temperature; the shared DIMM coverage count still signals incomplete source
telemetry. NVMe cards use Node Exporter controller state and hwmon temperatures
instead of FHS coverage counters. A non-live observed NVMe controller is Failed.
Healthy/Degraded describes these sensor checks, not a comprehensive diagnostic.
Incomplete data becomes **Unknown** rather than Healthy. A reachable exporter
alone never proves a component is healthy.

The sample and repository do not establish flag bit meanings. PSU, CPU and BMC
aggregate states therefore remain Unknown unless a separate observed temperature
failure proves failure. Raw flag values remain visible. NIC status uses temperature and the supplied coverage gauges;
that status describes reported sensor readings rather than all possible NIC faults. Confirm flag encoding and equipment limits before using
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
