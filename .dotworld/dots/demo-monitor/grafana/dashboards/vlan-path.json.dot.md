---
id: demo-monitor/grafana/dashboards/vlan-path.json
source_id: Prototype
title: VLAN Path dashboard
tags:
  - demo-monitor
  - vlan
  - grafana
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/dashboards/vlan-path.json
kind: config
summary: Node Graph dashboard (uid demo-monitor-vlan-path) visualizing one VLAN's broadcast domain on one switch -- switch node, member interfaces, and peer FHS servers for FPGA-linked interfaces once that metric lands. $switch/$vlan template variables for cross-linking from the VLAN Health overview.
summary_blob: 3bf9766fb98a45c939739c8731f35301ad215b76
---

Node Graph panel (Grafana core, no plugin) showing one VLAN's broadcast domain on one switch: switch + member interfaces + (once FPGA link metrics land) peer FHS servers, via $switch/$vlan variables. Complements the VLAN Health table (fleet-wide triage) -- this is the single-VLAN drilldown.
