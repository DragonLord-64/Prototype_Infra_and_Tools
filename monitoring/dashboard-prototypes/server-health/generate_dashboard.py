"""Generate the editable classic Grafana dashboard for the synthetic server."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
DS = {"type": "prometheus", "uid": "server-health-demo-prometheus"}
SELECTOR = 'server_component_health{server="demo-server-01"}'
UP = 'up{job="server-health-demo"} == 1'
panels = []

def panel(title, expr, x, y, w, h=4, status=True, color=None):
    defaults = {"decimals": 0, "noValue": "Unknown", "color": {"mode": "thresholds"}}
    if status:
        defaults["mappings"] = [{"type": "value", "options": {
            "0": {"text": "Healthy", "color": "green"},
            "1": {"text": "Degraded", "color": "orange"},
            "2": {"text": "Failed", "color": "red"},
            "3": {"text": "Unknown", "color": "#8e8e8e"}}}]
        defaults["thresholds"] = {"mode": "absolute", "steps": [
            {"color": "green", "value": None}, {"color": "orange", "value": 1},
            {"color": "red", "value": 2}, {"color": "#8e8e8e", "value": 3}]}
    else:
        defaults["color"] = {"mode": "fixed", "fixedColor": color}
    panels.append({"id": len(panels)+1, "title": title, "type": "stat",
        "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"refId": "A", "expr": expr, "instant": True, "range": False}],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "horizontal", "textMode": "value", "colorMode": "background_solid" if status else "value",
            "graphMode": "none", "justifyMode": "center", "wideLayout": True}})

def row(title, y):
    panels.append({"id": len(panels)+1, "title": title, "type": "row", "collapsed": False,
        "gridPos": {"x":0,"y":y,"w":24,"h":1}, "panels": []})

panels.append({"id": 1, "title": "", "type": "text", "transparent": True,
    "gridPos": {"x":0,"y":0,"w":24,"h":2}, "options": {"mode":"markdown", "content":
    "**DEMO SERVER 01 · SYNTHETIC DATA** — 14 components · Green: healthy · Amber: degraded · Red: failed · Gray: unknown. Status at left; key readings at right. Edit `mock-health.json` to try a scenario."}})

# Only current successfully scraped samples count. Missing samples become unknown.
live = f'({SELECTOR} and on(job, instance) ({UP}))'
known = f'count({live} < 3)'
overall = f'(vector(2) and on() (count({live} == 2) > 0)) or on() (max({live}) and on() (count({live}) == 14)) or on() vector(3)'
panel("Overall health", overall, 0,2,8,h=3)
for i,(name,code,color) in enumerate([("Healthy",0,"green"),("Degraded",1,"orange"),("Failed",2,"red")]):
    panel(name, f'count({live} == {code}) or on() vector(0)', 8+i*4,2,4,h=3,status=False,color=color)
panel("Unknown / missing", f'14 - ({known} or on() vector(0))',20,2,4,h=3,status=False,color="#8e8e8e")

def component(title, key, x,y, readings):
    expr = f'(server_component_health{{server="demo-server-01",component="{key}"}} and on(job, instance) ({UP})) or on() vector(3)'
    panel(title,expr,x,y,2,h=3)
    panels[-1]["title"] = ""
    panels[-1]["options"]["text"] = {"valueSize": 12, "titleSize":11}
    targets, overrides = [], []
    for i,(metric,label,unit,decimals) in enumerate(readings):
        targets.append({"refId":chr(65+i), "expr":f'{metric}{{server="demo-server-01",component="{key}"}} and on(job, instance) ({UP})',
            "instant":True,"range":False,"legendFormat":label})
        properties=[{"id":"unit","value":unit},{"id":"decimals","value":decimals}]
        if label == "Link":
            properties.append({"id":"mappings","value":[{"type":"value","options":{
                "0":{"text":"Down","color":"red"},"1":{"text":"Up","color":"green"}}}]})
        overrides.append({"matcher":{"id":"byName","options":label},"properties":properties})
    panels.append({"id":len(panels)+1,"title":f'{title} · readings',"type":"stat","datasource":DS,
        "gridPos":{"x":x+2,"y":y,"w":10,"h":3},"targets":targets,
        "fieldConfig":{"defaults":{"noValue":"Unknown","color":{"mode":"fixed","fixedColor":"text"}},"overrides":overrides},
        "options":{"reduceOptions":{"calcs":["lastNotNull"],"fields":"","values":False},"orientation":"vertical",
            "textMode":"value_and_name","colorMode":"value","graphMode":"none","justifyMode":"center",
            "text":{"valueSize":20,"titleSize":11},"wideLayout":False}})

temp=("server_component_temperature_celsius","Temperature","celsius",0)
link=("server_component_link_up","Link","short",0)
power=("server_component_power_watts","Power","watt",0)
voltage=("server_component_voltage_volts","Voltage","volt",1)
current=("server_component_current_amperes","Current","amp",1)
rpm=("server_component_fan_rpm","Speed","suffix: RPM",0)
row("COMPONENT HEALTH · STATUS + KEY READINGS",5)
left=[("Component 1","fpga-1",[temp,link]),("Component 2","fpga-2",[temp,link]),
      ("PSU 1","psu-1",[temp,power,voltage,current]),("PSU 2","psu-2",[temp,power,voltage,current]),
      ("NIC","nic-1",[temp,link]),("Motherboard","motherboard",[temp]),("BMC","bmc",[temp])]
right=[(f"Fan {i}",f"fan-{i}",[rpm]) for i in range(1,7)]+[("Network LAN","network-lan",[link])]
for i,(a,b) in enumerate(zip(left,right)):
    component(a[0],a[1],0,6+i*3,a[2])
    component(b[0],b[1],12,6+i*3,b[2])

row("EVERYTHING ELSE",27)
panels.append({"id":len(panels)+1,"title":"Everything else","type":"table","datasource":DS,
    "description":"Synthetic miscellaneous readings for reference. These informational rows do not change the 14-component health summary.",
    "gridPos":{"x":0,"y":28,"w":24,"h":12},
    "targets":[{"refId":"A","expr":f'server_misc_reading{{server="demo-server-01"}} and on(job, instance) ({UP})',
                "instant":True,"range":False,"format":"table"}],
    "transformations":[{"id":"organize","options":{
        "excludeByName":{"Time":True,"__name__":True,"instance":True,"job":True,"server":True},
        "indexByName":{"reading":0,"Value":1,"unit":2,"notes":3},
        "renameByName":{"reading":"Reading","Value":"Value","unit":"Unit","notes":"Notes"}}}],
    "fieldConfig":{"defaults":{"custom":{"align":"left","cellOptions":{"type":"auto"},"filterable":True},"decimals":1},
        "overrides":[{"matcher":{"id":"byName","options":name},"properties":[{"id":"custom.width","value":width}]} 
                     for name,width in [("Reading",290),("Value",120),("Unit",100)]]},
    "options":{"showHeader":True,"cellHeight":"sm","footer":{"show":False},
               "sortBy":[{"displayName":"Reading","desc":False}]}})

dashboard = {"uid":"server-health-demo","title":"Server Health · Demo","tags":["demo","server-health","synthetic"],
    "description":"Synthetic 14-component server health dashboard. Values are demo scenarios, not real hardware telemetry. Overall is worst component, unknown if any component/source is unavailable.",
    "schemaVersion":39,"version":1,"editable":True,"timezone":"browser","refresh":"5s",
    "time":{"from":"now-15m","to":"now"},"timepicker":{},"templating":{"list":[]},"annotations":{"list":[]},"panels":panels}
(ROOT / "grafana/dashboards/server-health.json").write_text(json.dumps(dashboard,indent=2)+"\n")
print(f"Generated {len(panels)} panels covering 14 components")
