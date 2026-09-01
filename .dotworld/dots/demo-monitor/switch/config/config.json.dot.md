---
id: demo-monitor/switch/config/config.json
source_id: Prototype
title: Switch config
tags:
  - switch
  - config
source_path: $DOTWORLD_ROOT/demo-monitor/switch/config/config.json
kind: config
summary: 'Mounted, editable config for the switch exporter: interface count/prefix, counter start/step ranges, and tick interval. Change and restart to retune behavior without a rebuild.'
summary_blob: ab40f16f139f20ecdc52e2fad0c05d913914e2d3
---

Mounted read-only into the container at /config/config.json (path overridable via SWITCH_CONFIG env var). Controls interface_count/interface_prefix (which interfaces exist), counter_start_min/max (initial counter values), counter_step_min/max (random increment applied per tick while a link is up), and tick_seconds (how often counters advance). Editing this and restarting the container changes simulated behavior without a rebuild.
