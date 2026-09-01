---
id: demo-monitor/grafana/dashboards/vlan-topology.json
source_id: Prototype
title: VLAN Topology (diagram)
tags:
  - demo-monitor
  - vlan
  - canvas
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/dashboards/vlan-topology.json
kind: config
summary: 'Canvas-panel topology diagram: 3-unit up/down boxes plus $vlan-driven switch-to-server connector highlighting, schema verified against Grafana''s own source and live Prometheus data (not visually rendered).'
summary_blob: b2b03595af86a027ca85bd280cc923f4a076ada0
---

Canvas panel (core, no plugin) fixed diagram of the 3-unit topology. Boxes colored by live up{} status (red<1/green>=1). New: a $vlan variable drives switch->server connector lines (source anchor on each switch's bottom edge, target anchor on the peer server's top edge), colored green if that server has any FPGA link on the selected VLAN (count(switch_interface_vlan_member{...,vlan="$vlan"})>=1, verified live: vlan=100 -> 1 for every unit's link0, vlan=200 -> 0 everywhere), red otherwise -- reusing the same red/green convention as box health, so red here means 'not on this VLAN' not 'down'. Schema for connections (per-source-element connections[] array: source/target {x,y} normalized -1..1 anchor coords, targetName referencing another element by name, color as a ColorDimensionConfig field-bound the same way background.color.field already works, size as fixed-only here) was read directly from this Grafana instance's own source (v13.0.2): app/features/canvas/element.ts (CanvasConnection interface) and app/plugins/panel/canvas/components/connections/Connections2.tsx (the literal object shape written when a user drags a connection in the UI), not guessed. Verified via Grafana's own dashboard API round-trip (schema accepted, connections/targetName/color.field intact) and via direct Prometheus queries for the count expressions -- rendering itself was never visually confirmed, no browser available in this environment.
