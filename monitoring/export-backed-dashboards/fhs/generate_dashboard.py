"""Build the FHS dashboard from the actual metric contract, without derived exporters."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DS = {"type": "prometheus", "uid": "export-backed-prometheus"}
LIVE = False
LIMITS = {"temperature_warn": 70, "temperature_fail": 85,
          "fan_warn": 4000, "fan_fail": 1000}
STATE = {0: ("Healthy", "green"), 1: ("Degraded", "orange"),
         2: ("Failed", "red"), 3: ("Unknown", "#8e8e8e")}


def source_up(node_job=False):
    if LIVE:
        return f'up{{{labels(node_job)}}}'
    return 'up{job="replay-node"}' if node_job else 'up{job="replay-fhs"}'


def labels(node_job=False):
    if LIVE:
        job, instance = ("node_job", "node_instance") if node_job else ("job", "instance")
        return f'node_name=~"$node",job=~"${job}",instance=~"${instance}"'
    return 'node_name=~"$node",' + ('job="node"' if node_job else 'job="fhs-exporter"')


def gate(node_job=False):
    return f'and on({"job,instance" if LIVE else ""}) ({source_up(node_job)} == 1)'


def select(metric, source=None, extra=None, node_job=False):
    matchers = [labels(node_job)]
    if source:
        matchers.append(f'source="{source}"')
    if extra:
        matchers.append(extra)
    return f'({metric}{{{",".join(matchers)}}} {gate(node_job)})'


def rate(name, extra='device!="lo"', bits=False):
    return f'rate({name}{{{labels(True)},{extra}}}[$__rate_interval])' + (' * 8 ' if bits else ' ') + gate(True)


def query_variable(name, label, expression):
    return {"name": name, "label": label, "type": "query", "datasource": DS,
            "definition": expression, "query": {"query": expression, "refId": name},
            "refresh": 1, "sort": 1, "multi": False, "includeAll": False, "options": []}


def live_variables():
    return [
        {"name": "ds", "label": "Datasource", "type": "datasource", "query": "prometheus", "refresh": 1, "options": []},
        query_variable("job", "FHS job", 'label_values(num_metrics_total{source="FPGA0"}, job)'),
        query_variable("node", "Nodename", 'label_values(up{job=~"$job",node_name!=""}, node_name)'),
        query_variable("instance", "FHS instance", 'label_values(up{job=~"$job",node_name=~"$node"}, instance)'),
        query_variable("node_job", "Node job", 'label_values(node_uname_info{node_name=~"$node"}, job)'),
        query_variable("node_instance", "Node instance", 'label_values(up{job=~"$node_job",node_name=~"$node"}, instance)'),
    ]


def metric(name, label, unit="short", decimals=0, **kw):
    return {"name": name, "label": label, "unit": unit, "decimals": decimals, **kw}


def temp(name, label="Temperature"):
    return metric(name, label, "celsius", 1, kind="temperature")


# Only groups represented by real samples. Fan 3–6 and PSU analog readings are absent.
COMPONENTS = [
    {"title": f"FPGA {i}", "source": f"FPGA{i}", "readings": [
        temp("fpga_temperature_celcius", "Core"), temp("front_temperature_celcius", "Front"), temp("fpga_fabric_temperature_celcius", "Fabric"),
        temp("fpga_ftile_temperature_celcius", "F-tile"), temp("fpga_bmc_temperature_celcius", "Card BMC"),
        metric("total_input_power_watts", "Input power", "watt", 1)]} for i in range(2)
] + [
    {"title": f"PSU {i}", "source": f"PSU{i}", "unverified_flags": True, "readings": [
        metric(f"sts_psu{i}", "Status flag"), metric(f"sts_psu{i}_fan", "Fan flag"),
        metric(f"sts_psu{i}_ac_lost", "AC lost flag")]} for i in (1, 2)
] + [
    {"title": f"Fan {i}", "source": "FAN", "readings": [
        metric(f"fan{i}_rpm", "Speed", "suffix: RPM", kind="fan"),
        temp("fsc_temperature_celcius", "Controller")]} for i in (1, 2)
] + [
    {"title": "CPU", "source": "CPU", "unverified_flags": True, "readings": [
        temp("cpu_temperature_celcius"), metric("prochot_cpu", "PROCHOT flag"),
        metric("cpu1_thermtrip", "Trip flag"), metric("sts_cpu_mce", "MCE flag")]},
    {"title": "NIC", "source": "NIC",
     "readings": [temp("nic_temperature_celcius")]},
    {"title": "Network LAN", "source": "LAN", "readings": [temp("lan_temperature_celcius")]},
    {"title": "Motherboard", "source": "x550_bmc", "readings": [
        temp("mb1_temperature_celcius", "Board 1"), temp("mb2_temperature_celcius", "Board 2"),
        temp("outlet1_temperature_celcius", "Outlet 1"), temp("outlet2_temperature_celcius", "Outlet 2")]},
    {"title": "BMC telemetry", "source": "x550_bmc", "unverified_flags": True, "readings": [
        metric("volt_12v_volts", "12 V rail", "volt", 2), metric("volt_3v_volts", "3 V rail", "volt", 2),
        metric("watchdog2", "Watchdog flag"), metric("chassis_intr", "Chassis flag")]},
] + [
    {"title": f"DIMM {s.upper()}1", "source": "DIMM", "readings": [temp(f"ddr5_{s}1_temperature_celcius")]} for s in "abceghik"
] + [
    {"title": f"NVMe {i}", "source": None, "sensor_coverage": True, "readings": [
        {**temp("node_hwmon_temp_celsius", "Composite"), "node_job": True,
         "extra": f'chip="nvme_nvme{i}",sensor="temp1"'},
        {**temp("node_hwmon_temp_celsius", "Hottest sensor"), "node_job": True,
         "extra": f'chip="nvme_nvme{i}"'},
        metric("node_nvme_info", "Controller live", node_job=True,
               extra=f'device="nvme{i}"', state="live", kind="state"),
    ]} for i in range(2)
]


def reading_expr(reading, source):
    name = reading["name"]
    if name.startswith("{"):
        # Merge the name matcher with node/source matchers, preserving all actual names.
        expr = select("", source, name[1:-1])
    else:
        expr = select(name, source, reading.get("extra"), reading.get("node_job", False))
    if reading.get("state"):
        live = select(name, source, reading["extra"] + f',state="{reading["state"]}"', reading.get("node_job", False))
        return f'(max({live}) or on() (max({expr}) * 0))'
    return f'{reading["aggregate"]}({expr})' if reading.get("aggregate") else f"max({expr})"


def component_query(component):
    source = component["source"]
    failed, degraded, known = [], [], []
    for r in component["readings"]:
        expr = reading_expr(r, source)
        known.append(f"({expr} == {expr})")
        if r.get("kind") == "temperature":
            failed.append(f'({expr} >= {LIMITS["temperature_fail"]})')
            degraded.append(f'({expr} >= {LIMITS["temperature_warn"]})')
        elif r.get("kind") == "fan":
            failed.append(f'({expr} < {LIMITS["fan_fail"]})')
            degraded.append(f'({expr} < {LIMITS["fan_warn"]})')
        elif r.get("kind") == "state":
            failed.append(f'({expr} == 0)')
    for name in component.get("required_names", []):
        known.append(f"(max({select(name, source)}) == max({select(name, source)}))")
    # A missing/partial source never becomes healthy merely because some values exist.
    complete = " and on() ".join(known)
    if not component.get("sensor_coverage"):
        complete += f" and on() (max({select('num_metrics_unavailable', source)}) == 0)"
        complete += f" and on() (max({select('num_metrics_total', source)}) > 0)"
    if component.get("unverified_flags") or component.get("no_completeness"):
        complete += " and on() (vector(0) == 1)"
    branches = []
    if failed:
        branches.append("(vector(2) and on() (" + " or on() ".join(failed) + "))")
    # Full completeness is required for Healthy/Degraded; a known failure wins over missing data.
    if degraded:
        branches.append("(vector(1) and on() (" + " or on() ".join(degraded) + ") and on() (" + complete + "))")
    branches.append("(vector(0) and on() (" + complete + "))")
    return " or on() ".join(branches) + " or on() vector(3)"


def status_defaults():
    return {"decimals": 0, "noValue": "Unknown", "mappings": [{"type": "value", "options": {
        str(k): {"text": v[0], "color": v[1]} for k, v in STATE.items()}}],
        "color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [
            {"color": STATE[3][1], "value": None},
            *[{"color": v[1], "value": k} for k, v in STATE.items()]]}}


def target(expr, ref="A", legend=None, instant=True, table=False):
    return {"refId": ref, "expr": expr, "instant": instant, "range": not instant,
            "legendFormat": legend or "", **({"format": "table"} if table else {})}


def build_dashboard(live=False):
    global LIVE, DS
    previous_live, previous_ds = LIVE, DS
    LIVE = live
    DS = {"type": "prometheus", "uid": "${ds}"} if live else previous_ds
    try:
        return _build_dashboard()
    finally:
        LIVE, DS = previous_live, previous_ds


def _build_dashboard():
    panels = []
    def add(p):
        p["id"] = len(panels)+1
        panels.append(p)
        return p
    add({"title": "", "type": "text", "transparent": True, "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
         "options": {"mode": "markdown", "content": "**FHS · EXPORT REPLAY** — Captured readings with synthetic identities. Separate FPGA, DIMM and NVMe cards. Gray means incomplete or unverified readings. **Illustrative limits:** temperature 70/85 °C; fan 4,000/1,000 RPM. Status covers displayed sensors; PSU/CPU/BMC flag meanings are unverified. [Switch overview](./d/switch-export-backed/switch-ports) · Raw metric tables below."}})
    for col, (title, expr, unit) in enumerate([
        ("FHS source" if LIVE else "FHS replay source", f'max({source_up()}) or on() vector(0)', "short"),
        ("Node exporter" if LIVE else "Node replay source", f'max({source_up(True)}) or on() vector(0)', "short"),
        ("Unavailable readings · source totals", f'sum({select("num_metrics_unavailable")})', "short"),
        ("Memory used", f'100 * (1 - max({select("node_memory_MemAvailable_bytes",node_job=True)}) / max({select("node_memory_MemTotal_bytes",node_job=True)}))', "percent")]):
        d = {"unit": unit, "decimals": 0, "noValue": "Unknown", "color": {"mode": "fixed", "fixedColor": "text"}}
        if col < 2:
            d["mappings"] = [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}, "1": {"text": "UP", "color": "green"}}}]
        add({"title": title, "type": "stat", "datasource": DS, "gridPos": {"x": 6*col, "y": 3, "w": 6, "h": 3},
             "targets": [target(expr)], "fieldConfig": {"defaults": d, "overrides": []},
             "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "value", "graphMode": "none", "textMode": "value", "justifyMode": "center"}})
    for n, c in enumerate(COMPONENTS):
        x, y = 12*(n % 2), 6 + 4*(n//2)
        desc = "Status covers displayed readings, not a comprehensive hardware diagnostic. A known failure wins; incomplete or unverified readings are Unknown. "
        desc += (f'Source label: {c["source"]}. ' if c["source"] else 'Node Exporter hwmon and NVMe controller telemetry. ')
        desc += 'Flags are raw; their healthy/fault encoding is unverified.'
        add({"title": "", "description": desc, "type": "stat", "datasource": DS,
             "gridPos": {"x": x, "y": y, "w": 2, "h": 4}, "targets": [target(component_query(c))],
             "fieldConfig": {"defaults": status_defaults(), "overrides": []},
             "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "orientation": "horizontal", "colorMode": "background_solid", "textMode": "value", "graphMode": "none", "justifyMode": "center", "text": {"valueSize": 10}}})
        overrides = []
        for r in c["readings"]:
            properties = [{"id": "unit", "value": r["unit"]}, {"id": "decimals", "value": r["decimals"]}]
            if r.get("kind") == "state":
                properties.append({"id": "mappings", "value": [{"type": "value", "options": {"0": {"text": "Not live", "color": "red"}, "1": {"text": "Live", "color": "green"}}}]})
            overrides.append({"matcher": {"id": "byName", "options": r["label"]}, "properties": properties})
        add({"title": c["title"], "description": desc, "type": "stat", "datasource": DS,
             "gridPos": {"x": x+2, "y": y, "w": 10, "h": 4},
             "targets": [target(reading_expr(r, c["source"]), chr(65+i), r["label"]) for i,r in enumerate(c["readings"])],
             "fieldConfig": {"defaults": {"noValue": "Unknown", "color": {"mode": "fixed", "fixedColor": "text"}}, "overrides": overrides},
             "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "orientation": "vertical", "colorMode": "value", "textMode": "value_and_name", "graphMode": "none", "justifyMode": "center", "wideLayout": False, "text": {"valueSize": 19, "titleSize": 11}}})
    bottom = 6 + 4*((len(COMPONENTS)+1)//2)
    add({"title": "Node interfaces · OS state and traffic", "description": "All exported non-loopback OS interfaces; FPGA and BMC ports require their own telemetry if absent here. Carrier and node_network_up describe observed operational link state, not administrative configuration.",
         "type": "table", "datasource": DS, "gridPos": {"x": 0, "y": bottom, "w": 24, "h": 9},
         "targets": [target(select(name, extra='device!="lo"', node_job=True), chr(65+i), table=True) for i,name in enumerate(["node_network_carrier", "node_network_up"])],
         "transformations": [{"id": "joinByField", "options": {"byField": "device", "mode": "outer"}}, {"id": "organize", "options": {"excludeByName": {"Time": True, "__name__": True, "instance": True, "job": True, "node_name": True}, "renameByName": {"device": "Interface", "Value #A": "Carrier", "Value #B": "Operational link"}}}],
         "fieldConfig": {"defaults": {"noValue": "Unknown", "custom": {"filterable": True}}, "overrides": [{"matcher": {"id": "byRegexp", "options": "Carrier|Operational link"}, "properties": [{"id": "mappings", "value": [{"type": "value", "options": {"0": {"text": "Down", "color": "red"}, "1": {"text": "Up", "color": "green"}}}]}]}]}, "options": {"showHeader": True, "cellHeight": "sm"}})
    add({"title": "Interface traffic · bits/s", "description": "rate() from actual node exporter counters. Snapshot replay is flat; no live traffic is implied.", "type": "timeseries", "datasource": DS,
         "gridPos": {"x": 0, "y": bottom+9, "w": 12, "h": 8}, "targets": [target(rate(name, bits=True), chr(65+i), label, False) for i,(name,label) in enumerate([("node_network_receive_bytes_total", "{{device}} RX"), ("node_network_transmit_bytes_total", "{{device}} TX")])],
         "fieldConfig": {"defaults": {"unit": "bps", "min": 0}, "overrides": []}, "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}})
    add({"title": "Interface error / drop rates", "description": "A cumulative historical error count is not a current fault. These are per-second rates; missing data is not forced to zero.", "type": "timeseries", "datasource": DS,
         "gridPos": {"x": 12, "y": bottom+9, "w": 12, "h": 8}, "targets": [target(rate(name), chr(65+i), label, False) for i,(name,label) in enumerate([("node_network_receive_errs_total", "{{device}} RX errors"), ("node_network_transmit_errs_total", "{{device}} TX errors"), ("node_network_receive_drop_total", "{{device}} RX drops"), ("node_network_transmit_drop_total", "{{device}} TX drops")])],
         "fieldConfig": {"defaults": {"unit": "ops", "min": 0}, "overrides": []}, "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}})
    add({"title": "NVMe I/O · bytes/s", "description": "Per-drive read/write rates from Node Exporter. Missing telemetry remains absent.", "type": "timeseries", "datasource": DS,
         "gridPos": {"x": 0, "y": bottom+17, "w": 24, "h": 8},
         "targets": [target(rate(name, extra='device=~"nvme[0-9]+n[0-9]+"'), chr(65+i), label, False) for i,(name,label) in enumerate([("node_disk_read_bytes_total", "{{device}} Read"), ("node_disk_written_bytes_total", "{{device}} Write")])],
         "fieldConfig": {"defaults": {"unit": "Bps", "min": 0}, "overrides": []}, "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}})
    for n,(title,expr) in enumerate([
        ("Everything else · FHS raw readings", select("", extra='__name__!~"up|scrape_.*"')),
        ("Everything else · node readings", select("", extra='__name__=~"$node_metric"', node_job=True))]):
        add({"title": title, "description": "Raw metric values retain original names, labels, and units encoded in names. Use table column filters. Values may be historical counters, flags, or info markers; this is not a uniform health table.", "type": "table", "datasource": DS,
             "gridPos": {"x": 0, "y": bottom+25+12*n, "w": 24, "h": 12}, "targets": [target(expr, table=True)],
             "transformations": [{"id": "organize", "options": {"excludeByName": {"Time": True, "instance": True, "job": True, "node_name": True}, "renameByName": {"__name__": "Metric", "source": "Source", "Value": "Value"}}}],
             "fieldConfig": {"defaults": {"decimals": 3, "custom": {"filterable": True, "align": "left"}}, "overrides": []}, "options": {"showHeader": True, "cellHeight": "sm", "sortBy": [{"displayName": "Metric", "desc": False}]}})
    result = {"uid": "fhs-export-backed", "title": "FHS server · Export-backed", "description": "Actual FHS and node exporter metric contracts with sanitized captured replay. No real-time hardware connection. Health limits are illustrative; missing or unverified sensor coverage is Unknown.",
            "schemaVersion": 39, "version": 1, "editable": True, "timezone": "browser", "refresh": "5s", "tags": ["fhs", "export-replay", "prototype"], "time": {"from": "now-15m", "to": "now"}, "annotations": {"list": []},
            "templating": {"list": [
                {"name": "node", "label": "Server", "type": "query", "datasource": DS, "definition": "label_values(fpga_temperature_celcius, node_name)", "query": {"query": "label_values(fpga_temperature_celcius, node_name)", "refId": "node"}, "refresh": 1, "multi": False, "includeAll": False},
                {"name": "node_metric", "label": "Node metric (raw table)", "type": "textbox", "current": {"text": "node_(load.*|memory_Mem.*|filesystem_.*|network_.*)", "value": "node_(load.*|memory_Mem.*|filesystem_.*|network_.*)"}, "options": []}]}, "panels": panels}
    if LIVE:
        result["title"] = "FHS server · Live sources"
        result["description"] = "FHS and node exporter metrics selected by node_name. Illustrative health limits; incomplete or unverified coverage is Unknown. Confirm equipment limits and flag encodings before operational use."
        result["tags"] = ["fhs", "prototype", "live-sources"]
        result["templating"]["list"] = live_variables() + result["templating"]["list"][1:]
        panels[0]["options"]["content"] = "**FHS · LIVE SOURCES** — Select Datasource → FHS job → Nodename → FHS instance. Node job/instance follow the same Nodename at their own exporter endpoint. Separate FPGA0/1, eight DIMMs and two NVMe drives. Gray means incomplete or unverified readings. **Illustrative limits:** temperature 70/85 °C; fan 4,000/1,000 RPM. Status covers displayed sensors; PSU/CPU/BMC flags need verified meanings. [Switch overview](./d/switch-export-backed/switch-ports?var-ds=${ds:percentencode})"
        for p in panels:
            if p["title"] == "Interface traffic · bits/s":
                p["description"] = "Bits/s calculated from node exporter byte-counter rates."
    # Explicit browser navigation avoids Grafana's SPA treating ./d as a route
    # beneath the current dashboard. The base href retains deployment subpaths.
    panels[0]["options"]["content"] = re.sub(r"\[([^]]+)\]\((\./d/[^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>', panels[0]["options"]["content"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use actual FHS/node scrape UP, not replay target UP")
    parser.add_argument("--output-dir", type=Path, help="Defaults to ../live-import for --live, otherwise the replay dashboard directory")
    args = parser.parse_args()
    output_dir = args.output_dir or (ROOT.parent / "live-import" if args.live else ROOT / "grafana/dashboards")
    output = output_dir / "fhs-export-backed.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_dashboard(args.live), indent=2)+"\n")
    print(output)
