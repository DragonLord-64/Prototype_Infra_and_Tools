---
id: demo-monitor/grafana/dashboards/units.json
source_id: Prototype
title: 'Grafana dashboard: Units (VCC / FSP)'
tags:
  - grafana
  - dashboard
  - units
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/dashboards/units.json
kind: config
summary: 'Repeated-row dashboard grouping servers/switches by physical unit (VCCU_n = VCC unit: 1 FHS server + 1 switch; FSPU_n = FSP unit: 4 FHS servers + 1 switch), driven by a unit template variable extracted from switch_id.'
summary_blob: f34270b3006d436740ae3e7de561e4187405a92e
---

Repeated-row dashboard, one row per physical unit (VCCU_n / FSPU_n), each showing switch up/interfaces/RX-TX plus its FHS server(s) up/load. Units are discovered from the switch_id label; server panels additionally need a matching server_id label on the FHS server scrape targets (proposed to prometheus-agent/server-container over DotWorld comms, topic units-dashboard) before they show data.
