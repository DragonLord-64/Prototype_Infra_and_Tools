"""Native Grafana views using only the Nexus series/labels in the supplied export."""
import argparse
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
DS = {"type": "prometheus", "uid": "export-backed-prometheus"}
GRAY = "#707681"
DN = r"sys/intf/phys-\\[([^]]+)\\]/.*"
REPLAY_GATE = '(max(up{job="replay-switch"}) == 1)'


def topology(results):
    ports = {}
    for result in results:
        metric = result["metric"]
        if metric["__name__"] != "nexus_interfaces_ifIndex":
            continue
        match = re.fullmatch(r"sys/intf/phys-\[(eth\d+/(\d+)(?:/\d+)?)\]/phys", metric["dn"])
        if not match:
            raise ValueError(f"Unrecognized physical interface DN: {metric['dn']}")
        ports.setdefault(int(match[2]), set()).add(match[1])
    return {port: sorted(interfaces) for port, interfaces in sorted(ports.items())}


def normalized(expr):
    return f'label_replace(({expr}), "interface", "$1", "dn", "{DN}")'


def selector(metric, extra=""):
    return f'{metric}{{source=~"$switch"{"," + extra if extra else ""}}}'


def query(ref, expr, legend="", instant=True, table=False, fallback=None):
    # Gate on the real replay scrape, never the captured fixture's historic up metric.
    expr = f'({expr}) and on() {REPLAY_GATE}'
    if fallback:
        label, values, unknown = fallback
        defaults = " or ".join(f'label_replace(vector({unknown}), "{label}", "{value}", "", "")' for value in values)
        expr = f'({expr}) or on({label}) ({defaults})'
    return {"refId": ref, "expr": expr, "legendFormat": legend, "instant": instant,
            "range": not instant, "format": "table" if table else "time_series"}


def link_expr():
    base = selector("nexus_interfaces_ifIndex")
    up = selector("nexus_interfaces_ifIndex", 'operSt="up"')
    down = selector("nexus_interfaces_ifIndex", 'operSt="down"')
    known = selector("nexus_interfaces_ifIndex", 'operSt=~"up|down"')
    return normalized(f"({up} * 0 + 1) or ({down} * 0) or (({base} unless {known}) * 0 + 2)")


def quality_expr():
    crc = normalized(f'increase({selector("nexus_interfaces_cRCAlignErrors")}[5m])')
    drops = normalized(f'increase({selector("nexus_interfaces_dropEvents")}[5m])')
    identity = "source,interface"
    # No recent samples stays Unknown. Historical lifetime errors never imply a current fault.
    return (f"(({crc} > 0) * 0 + 1) or on({identity}) "
            f"((({drops} > 0) * 0 + 2) unless on({identity}) ({crc} > 0)) or on({identity}) "
            f"((({crc} == 0) * 0) and on({identity}) ({drops} == 0))")


def parent_health_expr():
    def parent(expr):
        return f'label_replace(({expr}), "port", "$1", "interface", "eth[0-9]+/([0-9]+)(/.*)?")'
    faults = f'(max by(port) ({parent(quality_expr())}) > 0) * 0'
    unknown = f'max by(port) ({parent(normalized(selector("nexus_interfaces_ifIndex")))}) * 0 + 2'
    return f'({faults}) or on(port) ({unknown})'


def element(name, x, y, w, h, text="", field=None, bg=None, size=12, color="text"):
    item = {"name": name, "type": "metric-value", "placement": {"left": x, "top": y, "width": w, "height": h},
            "constraint": {"horizontal": "left", "vertical": "top"},
            "config": {"align": "left", "valign": "middle", "size": size,
                       "color": {"field": field, "fixed": color} if field else {"fixed": color},
                       "text": {"mode": "field" if field else "fixed", "field": field or "", "fixed": text}}}
    if bg:
        item["background"] = {"color": {"fixed": bg}}
        item["border"] = {"width": 1, "radius": 5, "color": {"fixed": "#4b5058"}}
    if not field and not text:
        item["type"] = "rectangle"
    return item


def mapping(name, options):
    return {"matcher": {"id": "byName", "options": name}, "properties": [
        {"id": "mappings", "value": [{"type": "value", "options": options}]}]}


def panel(panel_id, kind, title, x, y, w, h, targets=None, unit="none"):
    return {"id": panel_id, "type": kind, "title": title, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets or [],
            "fieldConfig": {"defaults": {"unit": unit, "noValue": "Unknown"}, "overrides": []}, "options": {}}


def switch_var():
    return {"name": "switch", "label": "Switch", "type": "query", "datasource": DS,
            "query": {"query": "label_values(nexus_interfaces_ifIndex, source)", "refId": "variable"},
            "refresh": 1, "multi": False, "includeAll": False,
            "current": {"text": "demo-switch-01", "value": "demo-switch-01"}}


def build(ports, live=False):
    dash = {"uid": "switch-export-backed", "title": "FHS · Switch ports (export replay)", "schemaVersion": 39,
            "version": 1, "tags": ["fhs", "switch", "export-backed", "replay"], "editable": True,
            "refresh": "5s", "timezone": "browser", "time": {"from": "now-15m", "to": "now"},
            "annotations": {"list": []}, "templating": {"list": [switch_var()]}, "panels": []}
    p = dash["panels"]
    notice = panel(1, "text", "", 0, 0, 24, 2)
    notice["options"] = {"mode": "markdown", "content":
        f"**EXPORT REPLAY · {len(ports)} ports / {sum(map(len, ports.values()))} interfaces** — "
        "Port: red = recent CRC/drop; gray = Unknown (no DOM). Link: exported `operSt`. "
        "Quality: Error > Drop > Good over 5 minutes; frozen replay becomes zero after warm-up. "
        "[Open port details](/d/switch-export-detail?var-switch=${switch:percentencode}&var-port=1)."}
    p.append(notice)
    expressions = [
        ("Interfaces", f'count({selector("nexus_interfaces_ifIndex")})'),
        ("Link Up", 'count('+selector("nexus_interfaces_ifIndex", 'operSt="up"')+')'),
        ("Link Down", 'count('+selector("nexus_interfaces_ifIndex", 'operSt="down"')+')'),
        ("Chassis sensor faults", f'sum({selector("nexus_ch_tempValue")} >= bool on(source,dn) {selector("nexus_ch_minorThresh")})'),
    ]
    for i, (title, expr) in enumerate(expressions):
        stat = panel(2+i, "stat", title, i*6, 2, 6, 3, [query("A", expr)])
        stat["options"] = {"colorMode": "value", "graphMode": "none", "textMode": "value", "text": {"value": 26}, "reduceOptions": {"calcs": ["lastNotNull"], "values": False}}
        p.append(stat)
    interfaces=[interface for lanes in ports.values() for interface in lanes]
    board = panel(6, "canvas", "All physical ports · actual exported breakouts", 0, 5, 24, 14,
                  [query("A", link_expr(), "{{interface}} link", fallback=("interface",interfaces,2)),
                   query("B", quality_expr(), "{{interface}} quality", fallback=("interface",interfaces,3)),
                   query("C", parent_health_expr(), "Port {{port}} health", fallback=("port",ports,2))])
    elements = []; overrides = []
    for n, (port, interfaces) in enumerate(ports.items()):
        x, y = (n % 8)*139, (n // 8)*116
        first = len(elements)
        elements += [element(f"Port {port} background", x, y, 133, 109, bg="#292d34"),
                     element(f"Port {port} name", x+7, y+2, 53, 20, f"Port {port:02d}", size=11, color="#ffffff"),
                     element(f"Port {port} health", x+60, y+2, 67, 20, field=f"Port {port} health", size=11, color="#ffffff")]
        elements[first]["background"]["color"] = {"field": f"Port {port} health", "fixed": "#292d34"}
        elements[-1]["config"]["color"] = {"fixed": "#ffffff"}
        overrides.append(mapping(f"Port {port} health", {"0": {"text": "Fault", "color": "red"}, "2": {"text": "Unknown", "color": "#353a43"}}))
        for lane, interface in enumerate(interfaces):
            xx, yy = x+6+(lane % 2)*63, y+26+(lane//2)*39
            label = interface.rsplit("/", 1)[1] if len(interfaces)>1 else "IF"
            elements += [element(f"{interface} box", xx, yy, 59, 35, bg="#15181e"),
                         element(f"{interface} link", xx+3, yy, 55, 17, field=f"{interface} link", size=11),
                         element(f"{interface} quality", xx+3, yy+17, 55, 17, field=f"{interface} quality", size=10)]
            overrides += [mapping(f"{interface} link", {"0": {"text": f"{label} Down", "color": "red"}, "1": {"text": f"{label} Up", "color": "green"}, "2": {"text": f"{label} ?", "color": GRAY}}),
                          mapping(f"{interface} quality", {"0": {"text": "Good", "color": "green"}, "1": {"text": "Error", "color": "red"}, "2": {"text": "Drop", "color": "orange"}, "3": {"text": "Unknown", "color": GRAY}})]
        for el in elements[first:]:
            el["oneClickMode"] = "link"
            el["links"] = [{"title": f"Port {port} details", "url": f"/d/switch-export-detail?var-switch=${{switch:percentencode}}&var-port={port}", "oneClick": True, "targetBlank": False}]
    board["options"] = {"inlineEditing": False, "panZoom": True, "zoomToContent": True,
                        "tooltip": {"mode": "single"}, "root": {"name": "Root", "type": "frame", "elements": elements}}
    board["fieldConfig"]["overrides"] = overrides
    p.append(board)
    sensors = panel(7, "timeseries", "Chassis temperatures · separate from port optics", 0, 19, 16, 8,
                    [query("A", selector("nexus_ch_tempValue"), "{{descr}}", False)], "celsius")
    sensors["options"] = {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}
    p.append(sensors)
    psu = panel(8, "table", "PSU observed state · not inferred from softwareAlarm=0", 16, 19, 8, 8,
                [query("A", selector("nexus_ch_volt"), instant=True, table=True)], "volt")
    psu["transformations"] = [{"id": "organize", "options": {"includeByName": {"descr": True, "operSt": True, "typeCordConnected": True, "Value": True}, "renameByName": {"descr": "PSU", "operSt": "State", "typeCordConnected": "Input", "Value": "Voltage"}}}]
    psu["options"] = {"showHeader": True, "cellHeight": "sm"}
    p.append(psu)
    detail = copy.deepcopy(dash)
    detail.update(uid="switch-export-detail", title="FHS · Switch port details (export replay)")
    detail["templating"]["list"].append({"name": "port", "label": "Physical port", "type": "custom", "query": ",".join(map(str,ports)), "current": {"text": "1", "value": "1"}, "multi": False, "includeAll": False})
    detail["panels"] = []
    note = panel(1,"text","",0,0,24,3)
    note["options"] = {"mode":"markdown","content":"[← All ports](/d/switch-export-backed?var-switch=${switch:percentencode}) · **EXPORT REPLAY**. RX/TX are measured counter rates; frozen counters produce zero after warm-up. Link/mode/VLAN IDs come directly from interface labels. VLAN names and per-port optic DOM are absent; no names, temperatures or voltages are invented."}
    detail["panels"].append(note)
    port_re = r'dn=~"sys/intf/phys-\\[eth1/${port:regex}(/[0-9]+)?\\]/.*"'
    metadata = panel(2,"table","Interface configuration and operational state",0,3,24,7,
                     [query("A",normalized(selector("nexus_interfaces_ifIndex",port_re)),table=True)])
    keys = ["interface","operSt","adminSt","operStQual","operSpeed","operMode","allowedVlans","accessVlan","nativeVlan","operVlans","operDescr"]
    metadata["transformations"] = [{"id":"organize","options":{"includeByName":{k:True for k in keys},"indexByName":{k:i for i,k in enumerate(keys)},"renameByName":{"interface":"Interface","operSt":"Link","adminSt":"Admin","operStQual":"Reason","operSpeed":"Negotiated speed","operMode":"Mode","allowedVlans":"Allowed VLAN IDs","accessVlan":"Access VLAN","nativeVlan":"Native VLAN","operVlans":"Operational VLAN IDs","operDescr":"Description"}}}]
    metadata["options"]={"showHeader":True,"cellHeight":"sm","footer":{"show":False}}
    detail["panels"].append(metadata)
    rate_targets=[]
    for ref,suffix,direction in [("A","In","RX"),("B","Out","TX")]:
        metric=selector("nexus_interfaces_octets",r'dn=~"sys/intf/phys-\\[eth1/${port:regex}(/[0-9]+)?\\]/dbgIfHC'+suffix+'"')
        rate_targets.append(query(ref,normalized(f"rate({metric}[5m]) * 8"),"{{interface}} "+direction,False))
    rates=panel(3,"timeseries","Selected interfaces · RX / TX",0,10,24,8,rate_targets,"bps")
    rates["options"]={"legend":{"displayMode":"table","placement":"bottom","calcs":["lastNotNull"]},"tooltip":{"mode":"multi"}}
    detail["panels"].append(rates)
    for i,(metric,title) in enumerate([("nexus_interfaces_cRCAlignErrors","CRC / alignment errors"),("nexus_interfaces_dropEvents","Drop events")]):
        expr=selector(metric,port_re)
        counters=panel(4+i,"stat",title+" · lifetime counters",i*12,18,12,5,[query("A",normalized(expr),"{{interface}}")],"short")
        counters["options"]={"colorMode":"none","graphMode":"none","textMode":"value_and_name","reduceOptions":{"calcs":["lastNotNull"],"values":False}}
        detail["panels"].append(counters)
        recent=panel(6+i,"timeseries",title+" · increase over 5 minutes",i*12,23,12,7,[query("A",normalized(f"increase({expr}[5m])"),"{{interface}}",False)],"short")
        recent["options"]={"legend":{"displayMode":"list","placement":"bottom"},"tooltip":{"mode":"multi"}}
        detail["panels"].append(recent)
    if live:
        live_gate = '(max(up{job="switch-telegraf"} and on(instance,job) '+selector("nexus_interfaces_ifIndex")+') == 1)'
        for dashboard in (dash, detail):
            dashboard["title"] = dashboard["title"].replace("export replay", "live metrics")
            dashboard["tags"] = [tag for tag in dashboard["tags"] if tag != "replay"]
            for current_panel in dashboard["panels"]:
                for target in current_panel["targets"]:
                    target["expr"] = target["expr"].replace(REPLAY_GATE, live_gate)
                if current_panel["type"] == "text":
                    content = current_panel["options"]["content"]
                    content = content.replace("EXPORT REPLAY", "LIVE METRICS")
                    content = content.replace("; frozen replay becomes zero after warm-up", "")
                    content = content.replace("; frozen counters produce zero after warm-up", "")
                    current_panel["options"]["content"] = content
    return dash, detail


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fixture",type=Path,default=ROOT.parent/"sources/fixtures/switch.json")
    parser.add_argument("--live",action="store_true",help="Gate on the original switch-telegraf target, not the replay job")
    parser.add_argument("--output-dir",type=Path,default=ROOT/"grafana/dashboards")
    args=parser.parse_args()
    data=json.loads(args.fixture.read_text())
    results=data["data"]["result"]
    ports=topology(results)
    for dashboard in build(ports,live=args.live):
        destination=args.output_dir/(dashboard["uid"]+".json")
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(dashboard,indent=2)+"\n")
    (ROOT/"topology.json").write_text(json.dumps(ports,indent=2)+"\n")
    print(f"Generated {len(ports)} parent ports / {sum(map(len,ports.values()))} interfaces")


if __name__=="__main__":
    main()
