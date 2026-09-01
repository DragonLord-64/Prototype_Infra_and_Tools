---
id: demo-monitor/server/docker-compose.yml
source_id: Prototype
title: Standalone server compose
tags:
  - docker
  - compose
  - server
source_path: $DOTWORLD_ROOT/demo-monitor/server/docker-compose.yml
kind: file
summary: Standalone Docker Compose file for the server container alone, used for local development and testing outside the full demo-monitor stack. Defines one service, 'server', built from the local Dockerfile, mounting ./config read-only to /config, exposing 9100/9101 internally only (nothing published to the host), and joining the pre-existing external network demo-monitor-net so it can be scraped by a Prometheus container running elsewhere on that network. Declares demo-monitor-net as an external network rather than creating it.
summary_blob: 20f80fbe39c6df55268d4b2ac53adb5686932f41
---

For building/running the server container on its own during development. The real multi-service stack for the demo is demo-monitor/docker/docker-compose.yml (owned by prometheus-agent), which builds this same server/ folder as one of its services -- keep the service name here as 'server' so it matches that stack's static scrape target (server:9100/9101).
