---
id: demo-monitor/prometheus/prometheus.yml
source_id: Prototype
title: Prometheus scrape config
tags: []
source_path: $DOTWORLD_ROOT/demo-monitor/prometheus/prometheus.yml
kind: file
summary: 'Prometheus scrape + alerting config for demo-monitor: scrapes itself plus a fleet of 6 named server units (VCCU_1:FHS_1, VCCU_2:FHS_2, FSPU_5:FHS_1..4, each on node_exporter:9100 and custom exporter:9101) and 3 named switches (VCCU_1/VCCU_2/FSPU_5:SWITCH on :9101), every 15s. Each static target carries a server_id/switch_id label with its literal unit name. Also loads rules.yml (rule_files) for basic threshold alerting on the server params and switch link status. All targets reached over the demo-monitor-net compose network, none published to the host.'
summary_blob: 128ad889394b4f2cca5101e5ee51ff798dd97253
---

