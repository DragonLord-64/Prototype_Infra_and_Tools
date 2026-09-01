---
id: demo-monitor/grafana/docker-compose.yml
source_id: Prototype
title: Grafana container (standalone)
tags:
  - grafana
  - docker-compose
  - demo-monitor
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/docker-compose.yml
kind: file
summary: Standalone Grafana container compose, joins demo-monitor-net externally; duplicated in the unified ../docker/ stack, keep both in sync.
summary_blob: be1aa6668db117cd5461f76fba5d81c69d8976a0
---

Standalone compose for running just the Grafana container, joining demo-monitor-net as an external network. The unified stack at ../docker/docker-compose.yml duplicates this service definition for the 'run everything together' path; keep the two in sync if ports, env vars, or volume mounts change here.
