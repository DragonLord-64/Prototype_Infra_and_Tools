---
id: demo-monitor/grafana/dashboards/vlan-health.json
source_id: Prototype
title: VLAN Health Overview dashboard
tags:
  - demo-monitor
  - grafana
  - vlan
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/dashboards/vlan-health.json
kind: config
summary: 'Triage table: one row per (switch, VLAN), health/member-count/packet-rate rolled up via PromQL vector match against existing switch exporter metrics, sorted down-first, links out to the VLAN Path node-graph dashboard.'
summary_blob: b39c27364faa24dfba86756aca00dd67b03c12f8
---

Table dashboard, one row per (switch, VLAN) pair. Health computed via a vector-match join (switch_interface_link_up * on(switch,interface) group_right() switch_interface_vlan_member) rolled up by (switch_id, vlan) -- no new metrics needed, uses only what switch/exporter.py already emits. Sorted down-first for triage across hundreds of VLANs. Row cells link to the sibling VLAN Path node-graph dashboard (uid demo-monitor-vlan-path) via var-switch/var-vlan query params.
