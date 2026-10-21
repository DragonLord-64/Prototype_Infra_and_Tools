# FHS and switch dashboards from exported metrics

This is a separate, runnable Grafana lab based on the FHS, Node Exporter and
switch Telegraf snapshots in `ska-mid-cbf-fhs-baremetal` development commit
`6569833`, under `monitoring/example_output`. The earlier
[dashboard prototypes](../dashboard-prototypes/README.md) remain separate.

The three test sources preserve every metric name, label key, series count and
numeric value in those exports. Inventory identities are replaced consistently
with synthetic values before publication. Names such as
`fpga_temperature_celcius` deliberately retain the exporter's spelling. See the
[source contract and provenance](sources/README.md).

| Source | Captured series | Metric names |
| --- | ---: | ---: |
| FHS | 103 | 67 |
| Node Exporter | 9,989 | 7,175 |
| Switch Telegraf | 8,641 | 193 |

These are **static snapshot replays**, not a reconstruction of the original
device's history. Counters remain fixed, so calculated rates settle at zero.
Prometheus assigns new scrape timestamps; those timestamps do not mean the
original device data is fresh. The source API export has no metric-type metadata,
so the replay does not invent HELP/TYPE declarations.

## Start the lab

Requirements: Docker Engine and Python 3.9 or newer. From the repository root:

```bash
cd monitoring/export-backed-dashboards
python3 run.py
```

The Docker CLI launcher works without the Compose plugin. It starts three
replay sources, Prometheus and Grafana. Only the two web applications are
published, on loopback. Existing dashboards on ports 3001 and 3002 are unaffected.

- [FHS server](http://localhost:3003/d/fhs-export-backed)
- [Switch overview](http://localhost:3003/d/switch-export-backed)
- [Switch port details](http://localhost:3003/d/switch-export-detail?var-port=1)
- [Prometheus targets](http://localhost:9093/targets)

Use Grafana's normal first-run login (`admin` / `admin` for a fresh local volume).
The existing local-demo preference is to keep the default login. This lab is
intended for local testing.

```bash
python3 run.py status
python3 run.py stop
```

Stopping the lab retains its named data volumes. Re-running `run.py` starts its
existing containers without replacing configuration. To choose ports before the
first launch:

```bash
EXPORT_GRAFANA_PORT=3004 EXPORT_PROMETHEUS_PORT=9094 python3 run.py
```

Grafana provisioning watches the dashboard directories. Regenerated dashboard
JSON reloads automatically. Sources load fixtures at startup; after changing a
fixture, restart only its container, for example
`docker restart fhs-export-backed-switch`. Changing container environment,
ports or bind-mount locations requires recreating the affected lab containers;
do not remove the data volumes if you want to retain Grafana settings/history.
The launcher refuses to reuse a container owned by another application or bound
to a different checkout.

### Docker Compose alternative

Use one launcher per instance. Compose uses separate resources and volumes from
the Docker CLI launcher; both defaults bind the same ports.

```bash
docker compose config --quiet
docker compose up -d
docker compose down
```

Compose configuration and mounts are checked, but Compose execution was not
available on the test host. Images are pinned to the verified local digests.
Both launchers enable Grafana's `canvasPanelPanZoom` feature for the switch
overview's fit-to-content behavior.

## Dashboard behavior

The [FHS view](fhs/README.md) keeps the small component-health tile beside wider
key readings. It displays 21 separate component cards supported by these exports, plus
interface traffic/error histories and raw metric tables. The FPGA cards are named
`FPGA 0`/`FPGA 1`; all eight DIMMs and both NVMe drives are individual cards. FHS and Node Exporter are selected by their shared `node_name`,
not their different endpoint ports. No extra fans or PSU electrical readings are
invented. Partial coverage or unverified flag meanings show Unknown; a known
temperature/fan failure takes precedence. Limits are explicitly illustrative.

The [switch view](switch/README.md) shows the exported 34 parent ports and their
62 actual interfaces, including mixed breakout sizes. Interface link state comes
from `operSt`; recent CRC/drop increases determine Error/Drop/Good. Parent ports
turn red for observed recent errors/drops and otherwise remain Unknown because
per-port optical health telemetry is absent. Chassis temperatures use the
exported sensor thresholds and are kept separate from per-port optics. Port
details expose actual mode/VLAN ID labels, rates and lifetime counters. VLAN
names and optical DOM readings are not supplied in this export.

## Use your real Prometheus

Import the ready-to-use JSON files in [live-import/](live-import/README.md),
**not** the provisioned replay JSON under `fhs/grafana` or `switch/grafana`.
Choose your existing Prometheus in the **Datasource** dropdown. Every live panel
and query variable uses that selection; no datasource rename or UID replacement
is required. The selectors follow Grafana's [data source and chained variable
pattern](https://grafana.com/docs/grafana/latest/visualizations/dashboards/variables/add-template-variables/).

FHS has **Datasource → FHS job → Nodename → FHS instance**, followed by
**Node job → Node instance** for the same node name. Separate instances are
necessary because FHS and Node Exporter have different endpoint ports. Jobs and
instances are discovered, not hard-coded. Switch dashboards have
**Datasource → Job → Switch → Instance**, plus Physical port on the detail view.

Regenerate the portable files from this directory:

```bash
python3 fhs/generate_dashboard.py --live
python3 switch/generate_dashboard.py --live
```

Live mode defaults to `live-import/`; replay mode still defaults to each
provisioned replay dashboard directory. `--output-dir` overrides either path.
Live and replay dashboards retain the same UIDs, so importing live files can
replace an existing replay dashboard with that UID. The live files do not
require any `replay-*` jobs or a replay exporter. FHS still requires the shared
`node_name` scrape label, including on `up`; this is already configured in the
supplied bare-metal scrape configuration. This change does not deploy anything
to production. The separate rack prototype still needs real rack metadata and
health integration before it can be used with production Prometheus.

## Run the checks

From this folder:

```bash
python3 -m unittest discover -s tests -v
EXPORT_LIVE_TEST=1 python3 -m unittest discover -s tests -v
```

The second command also queries the running lab. An optional local comparison
against the original private exports can be enabled with
`PROMETHEUS_ORIGINAL_EXPORT_DIR=/path/to/monitoring/example_output`.
Original exports and identity mappings are not required by, or bundled with,
the public lab.

The health acceptance suites execute the actual dashboard PromQL in Promtool:

```bash
python3 tests/test_fhs_dashboard.py --write-promql-tests /tmp/fhs-health.test.json
python3 tests/test_switch_dashboard.py --promtool-json > /tmp/switch-health.test.json
docker exec -i fhs-export-backed-prometheus promtool test rules /dev/stdin < /tmp/fhs-health.test.json
docker exec -i fhs-export-backed-prometheus promtool test rules /dev/stdin < /tmp/switch-health.test.json
```

Checks cover exact source/schema parity, HTTP exposition, all dashboard queries,
real link counts, missing readings, source failure, health precedence and recent
error/drop behavior. [Verification record](VALIDATION.md) documents the tested
results and remaining production assumptions.

Prometheus references: [text exposition](https://prometheus.io/docs/instrumenting/exposition_formats/)
and [`honor_labels` configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/).
