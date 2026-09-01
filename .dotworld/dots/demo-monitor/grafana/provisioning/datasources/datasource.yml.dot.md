---
id: demo-monitor/grafana/provisioning/datasources/datasource.yml
source_id: Prototype
title: Prometheus datasource provisioning
tags:
  - grafana
  - provisioning
  - prometheus
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/provisioning/datasources/datasource.yml
kind: file
summary: Provisions the Prometheus datasource at http://prometheus:9090 with a pinned uid for dashboards to reference.
summary_blob: c48dd5f06ef7261eb925818ecb86d228c281830c
---

Auto-registers Prometheus at http://prometheus:9090 with a pinned uid ('prometheus') so dashboards/demo-monitor.json can reference it by uid instead of name.
