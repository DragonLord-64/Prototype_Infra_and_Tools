---
id: demo-monitor/server/exporter.py
source_id: Prototype
title: Custom telemetry exporter
tags:
  - python
  - server
  - exporter
  - prometheus
source_path: $DOTWORLD_ROOT/demo-monitor/server/exporter.py
kind: code
summary: 'Standalone Python (stdlib only) Prometheus exporter. On startup it loads parameter definitions (name, starting value, max per-tick delta) and the update interval/port from a JSON config file (EXPORTER_CONFIG env var, default /config/exporter_config.json). A daemon thread wakes every interval and nudges each value by a random amount in [-max_delta, max_delta]. An http.server.HTTPServer serves GET /metrics in Prometheus text format, one HELP/TYPE/value block per parameter, each value tagged with an instance label from SERVER_ID (default: hostname). Any other path returns 404.'
summary_blob: 99b2a4bc2fb93e9bc77912931abe51bb6d86dc31
---

Deliberately stdlib-only (http.server, no prometheus_client pip dependency) to avoid adding a pip-install layer to an image meant to be run as many replicas. Config (parameter names/starting values/max step/update interval/port) is read once from EXPORTER_CONFIG at process start -- editing the mounted JSON file requires a container restart to take effect, it is not live-reloaded. SERVER_ID (default: hostname) is attached to every metric as an instance label so replicas are distinguishable.
