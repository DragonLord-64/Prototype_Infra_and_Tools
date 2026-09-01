---
id: demo-monitor/docker/docker-compose.yml
source_id: Prototype
title: Demo-monitor Docker Compose
tags: []
source_path: $DOTWORLD_ROOT/demo-monitor/docker/docker-compose.yml
kind: file
summary: 'Integrated compose for demo-monitor: brings up Prometheus, a fleet of 6 named server units (VCCU_1:FHS_1, VCCU_2:FHS_2, FSPU_5:FHS_1..4) and 3 named switches (VCCU_1/VCCU_2/FSPU_5:SWITCH), and includes grafana/docker-compose.yml, all on the demo-monitor-net bridge network it owns. Each server/switch service is distinguished by container_name (DNS target) and a SERVER_ID/SWITCH_ID env var carrying the literal unit name, embedded as a metric label. Also carries a prometheus_job=server/switch container label on each, for future docker_sd_configs discovery even though static targets are used today.'
summary_blob: c74afded40d1eec0443aa31932d560b14d105e4b
---

