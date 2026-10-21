# Portable Prometheus dashboards

Import these files into your existing Grafana using **Dashboards → New → Import**:

- [FHS server](fhs-export-backed.json)
- [Switch overview](switch-export-backed.json)
- [Switch port details](switch-export-detail.json)

Select your existing Prometheus in **Datasource**. Its name and UID can be
anything; you do not need a datasource named `export-backed-prometheus`.
All panels and dependent query variables refer to `${ds}`.

For FHS, select **FHS job → Nodename → FHS instance**, then verify **Node job →
Node instance**. The latter pair uses the same node name at the Node Exporter
endpoint, rather than reusing the FHS port. The shared `node_name` target label
must exist on both jobs, including `up`. The bare-metal configuration already
supplies it. Jobs and instances are discovered from the selected datasource.

For switches, select **Job → Switch → Instance**, then open port details.
The selection travels with the detail links. Navigation opens a new tab so
Grafana loads the complete route; `./d/` URLs follow its configured base subpath. The overview Canvas is generated
for the sample's 34 parent ports / 62 interfaces; regenerate the topology when
breakouts differ. These files use ordinary exporter metrics and source `up`
checks, with no replay jobs or extra derived exporter required.

The FHS view has two FPGA cards, one NIC, eight individual DIMMs, two NVMe drives,
and the other exported CPU, fan, PSU, motherboard and BMC readings. All
non-loopback OS interfaces are discovered from metrics. The snapshot exposes
three; FPGA/BMC links not exported by Node Exporter need their own verified
telemetry. Sensor health limits remain illustrative. Unverified flags or missing
sensor coverage remain Unknown; a successful data query is distinct from a
component being healthy. NVMe status covers observed controller state and
thermals; I/O rates are shown separately, without claiming SMART endurance data.

These imports share UIDs with the replay dashboards. Importing can overwrite
an existing replay dashboard with that UID; use another Grafana instance if
keeping both. The rack elevation prototype remains a separate integration task
because the real rack metadata and aggregate health metrics are not in these
exports.

From the parent directory, regenerate with:

```bash
python3 fhs/generate_dashboard.py --live
python3 switch/generate_dashboard.py --live
```

The default destination is this folder. `--output-dir` can specify another
folder. Running without `--live` regenerates the separate replay definitions.

Local verification screenshots are in [screenshots](screenshots/). These use the
captured fixtures and a second datasource UID to check portable imports; they
are not readings from current physical equipment.
