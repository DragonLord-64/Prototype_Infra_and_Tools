---
id: demo-monitor/grafana/README.md
source_id: Prototype
title: Grafana setup for demo-monitor
tags:
  - grafana
  - demo-monitor
  - provisioning
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/README.md
kind: prose
summary: Grafana provisioning (datasource + starter dashboard) for demo-monitor, runnable standalone or via the unified stack; live on the VM at :3000.
summary_blob: d9ed6a37db47f96608e30408c92186d51d587c92
---

Grafana container config for the demo-monitor lab: provisioning (datasource + dashboard loader) plus one starter dashboard, run either standalone or as part of the unified stack in ../docker/. Currently live on the VM at :3000 with anonymous viewer access. Switch-panel queries use provisional metric names pending confirmation from the switch exporter.
