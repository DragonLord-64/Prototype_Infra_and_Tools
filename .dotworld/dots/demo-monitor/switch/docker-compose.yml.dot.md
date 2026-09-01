---
id: demo-monitor/switch/docker-compose.yml
source_id: Prototype
title: Switch compose
tags:
  - switch
  - compose
  - docker
source_path: $DOTWORLD_ROOT/demo-monitor/switch/docker-compose.yml
kind: file
summary: Standalone compose for the switch service; joins demo-monitor-net externally, container_name/port match prometheus.yml's static scrape target (switch:9101).
summary_blob: b26b53f4b96c435605010354fc513179b484fa43
---

Standalone compose file for the switch service only, per the multi-agent convention (each container owns its own compose file rather than one shared file everyone edits) worked out with server-container and prometheus-agent over dotworld comms. Joins the demo-monitor-net network as external:true -- that network is created by demo-monitor/docker/docker-compose.yml (prometheus-agent), not here. container_name is literally 'switch' and the port is 9101, matching prometheus.yml's static scrape target.
