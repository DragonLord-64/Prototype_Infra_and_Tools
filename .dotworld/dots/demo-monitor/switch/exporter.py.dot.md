---
id: demo-monitor/switch/exporter.py
source_id: Prototype
title: Switch exporter
tags:
  - switch
  - exporter
  - prometheus
  - python
source_path: $DOTWORLD_ROOT/demo-monitor/switch/exporter.py
kind: code
summary: Stdlib-only Python Prometheus exporter simulating 32 switch interfaces (rx/tx counters + link-up gauge, 96 series). Counters random-walk while up, freeze on link-down. Link status is injectable at runtime via POST /interfaces/<name>/link.
summary_blob: 36ffb3a80b99347638a76090c5389ffc84d7ae36
---

Stdlib-only Prometheus exporter (no pip deps) simulating 32 network interfaces. Serves switch_interface_rx_bytes_total, switch_interface_tx_bytes_total (counters, random-walk +N every tick_seconds while the link is up, frozen while down) and switch_interface_link_up (gauge) on GET /metrics. Link status is mutable at runtime -- not just config-driven -- via POST /interfaces/<name>/link?state=up|down, so a demo can simulate a live port failure without restarting the container. State lives in-memory only (a dict guarded by one lock, shared between the HTTP handler thread and the background ticker thread); a restart resets counters to fresh random starting values from config/config.json.
