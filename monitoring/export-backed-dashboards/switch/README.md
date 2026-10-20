# Switch ports from the supplied Nexus export

The compact native Grafana Canvas follows the earlier port/breakout prototype,
using the metric names and label structure in the captured switch export. The
capture has **34 physical ports and 62 interfaces**, including ports 33/34 and
mixed one-, two- and four-interface parents. The view preserves those actual
interfaces rather than manufacturing 128 lanes. The first four rows contain
ports 1–32; the final row contains 33/34.

Open `/d/switch-export-backed` for the overview or
`/d/switch-export-detail?var-port=1` for details. A visible details link and the
physical-port dropdown provide navigation alongside Canvas element links.

## What each field means

- Interface Up/Down comes from the `operSt` label on
  `nexus_interfaces_ifIndex`, not from nonzero traffic, `ifIndex`, or an
  undocumented numeric status code. Other or absent states show Unknown.
- Interface quality is Error for a positive five-minute increase in
  `nexus_interfaces_cRCAlignErrors`, otherwise Drop for a positive increase in
  `nexus_interfaces_dropEvents`, otherwise Good only when both increases are
  available and zero. Missing rate history shows Unknown. Error wins over Drop.
- A parent turns red if any interface has a recent Error/Drop. Otherwise the
  parent remains **Unknown**, because this export contains no per-port optic
  temperature, voltage, or aggregate sensor health. It cannot establish a
  healthy green parent. Link Down alone does not imply an overheating port.
- RX/TX use `rate(nexus_interfaces_octets[5m]) * 8` and the `dbgIfHCIn` /
  `dbgIfHCOut` distinguished-name suffixes. Lifetime CRC/drop counts remain
  separately visible in the detail dashboard. An old nonzero CRC counter does
  not imply a new fault.
- Detail configuration displays exported mode, VLAN IDs, speed, administrative
  state and operational reason labels. Allowed-VLAN labels may be absent on
  access interfaces. VLAN names are not in this export and are not invented.
- Chassis temperature sensors and their exported minor thresholds appear
  separately. The sensor named XCVR is a chassis sensor, not per-port DOM. PSU
  state uses the exported `operSt` label; `softwareAlarm=0` does not make the
  captured shut/unpowered PSU healthy.

The snapshot is replayed with unchanged counter values. After sufficient scrape
history, rates and recent increments are zero. This validates schema and query
behavior; it does not demonstrate historical live throughput. Initial windows
with fewer than two samples show Unknown. The export's recorded `up` sample is
captured data, so the demo gates queries on the actual `replay-switch` target.
Known layout positions receive explicit Unknown values when that target is
unavailable or recent interface history is absent; the boxes stay visible.

## Regenerate or import against live metrics

From `monitoring/export-backed-dashboards`:

```bash
python3 switch/generate_dashboard.py
python3 switch/generate_dashboard.py --live --output-dir /tmp/fhs-switch-live
```

The default writes the two provisioned replay dashboards. The live command
writes separate import files with live banners and availability checks against
the original `switch-telegraf` scrape job. The check joins `up` to the selected
switch's interface series on `instance,job`. Keep those labels consistent; adapt
the job name in the generator if the production scrape configuration differs.

Import both generated files into Grafana and use a Prometheus datasource whose
UID is `export-backed-prometheus`, or change that UID in the generator before
regenerating. Choose the actual source in the Switch dropdown. The same UIDs
are used in live and replay output, so use a separate Grafana instance/folder
workflow if keeping both variants. Grafana dashboard UIDs are instance-wide.

Enable Grafana's `canvasPanelPanZoom` feature toggle for the Canvas panel's
automatic fit-to-content behavior, for example
`GF_FEATURE_TOGGLES_ENABLE=canvasPanelPanZoom` in the container environment.
The supplied test stack enables it. The panel uses pan/zoom plus zoom-to-content
so all ports remain in the field when the browser or panel changes size.
Grafana documents this dependency in its
[Canvas pan and zoom guidance](https://grafana.com/whats-new/2025-07-31-canvas-pan-and-zoom-improvements/).

The topology is generated from fixture `ifIndex` distinguished names. Pass
`--fixture path/to/new-export.json` and regenerate after changing breakout
configuration or adding ports; Canvas positions do not add themselves at
runtime. That input is a Prometheus instant-query JSON response, not a raw
exposition file. `topology.json` records the generated parent/interface map.

Focused tests cover the actual export's grouping, exact port boundaries,
operational-label usage, counter-rate behavior, absence of fabricated DOM/VLAN
names, and the live/replay availability distinction.

For the real Prometheus query engine's recent-fault tests, generate the test
input and run it with a local `promtool` (the container's binary also works):

```bash
python3 tests/test_switch_dashboard.py --promtool-json > /tmp/switch-promql-test.json
promtool test rules /tmp/switch-promql-test.json
```

These histories cover simultaneous CRC/drop events, drop-only events, unchanged
historical CRC counts, Fault/Unknown parent aggregation and Up/Down/Unknown link
labels. The test specification is JSON, which Prometheus accepts as YAML input.
