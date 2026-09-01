---
id: demo-monitor/grafana/dashboards/vlan-topology.json
source_id: Prototype
title: VLAN Topology (diagram)
tags:
  - demo-monitor
  - vlan
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/dashboards/vlan-topology.json
kind: config
summary: Canvas-panel unit topology diagram (VCCU_1/VCCU_2/FSPU_5), real-data-bound, built after the flowchart plugin approach failed (Angular disabled).
summary_blob: da56494cf38cb63eff8c835bf267201ef1705733
---

Fixed unit-topology diagram (VCCU_1/VCCU_2/FSPU_5, 9 boxes: 3 switches + 6 servers) built with Grafana's core Canvas panel, real-data-bound via ColorDimensionConfig's field-name matching (background.color.field references each query's legendFormat, panel-wide thresholds red<1/green>=1). Built after the community agenty-flowcharting-panel plugin proved unusable (Angular plugins are hard-disabled on Grafana v13). Schema for the canvas panel (Placement, CanvasElementOptions, ColorDimensionConfig field-vs-fixed mode, TextConfig) was read directly from the running container's /usr/share/grafana/public/app/features/canvas and /app/features/dimensions source rather than guessed, then verified by round-tripping the dashboard through Grafana's own /api/dashboards/uid endpoint (parses back with all 9 elements/targets intact) and confirming all 9 underlying PromQL queries return live '1' values. Not visually confirmed in a browser (no browser access in this session) -- API-level schema validation + live data confirmation only.
