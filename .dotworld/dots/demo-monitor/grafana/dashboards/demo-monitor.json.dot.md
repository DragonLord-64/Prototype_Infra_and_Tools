---
id: demo-monitor/grafana/dashboards/demo-monitor.json
source_id: Prototype
title: Demo Monitor dashboard
tags:
  - grafana
  - dashboard
  - demo-monitor
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/dashboards/demo-monitor.json
kind: config
summary: 'Starter Grafana dashboard: server panels from node_exporter, switch panels using switch-container''s provisional metric names pending confirmation.'
summary_blob: 8d6f8a68ae90efbb52d6d6005528ea27218ec787
---

Starter Grafana dashboard: server panels (up/load/memory) from node_exporter job server-node-exporter, switch panels (link status, RX/TX byte rate) from job switch-exporter. Switch metric names (switch_interface_link_up, switch_interface_rx_bytes_total, switch_interface_tx_bytes_total) are switch-container's proposed naming from DotWorld comms, not yet confirmed against the landed exporter -- update the panel targets if the real names differ.
