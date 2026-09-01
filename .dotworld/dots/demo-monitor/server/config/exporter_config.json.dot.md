---
id: demo-monitor/server/config/exporter_config.json
source_id: Prototype
title: Exporter defaults (edit me)
tags:
  - config
  - server
  - exporter
source_path: $DOTWORLD_ROOT/demo-monitor/server/config/exporter_config.json
kind: config
summary: Default configuration for the custom server exporter (exporter.py), meant to be bind-mounted read-only into the container at /config and edited from the host. Declares the listen port (9101), the update_interval_seconds between random-walk ticks (2), and three parameters -- server_param_a/b/c -- each with a starting value and a max_delta bounding how far it can move per tick. Read once at process start; a container restart is required to pick up edits.
summary_blob: 857683bb9cb755234510243aeebf0b00b7e1cfdd
---

This is the file meant to be edited from the host via the bind mount (server/config -> /config in the container) to change the simulated metrics' starting values, per-tick max step, or update interval without rebuilding the image. JSON has no comment syntax, hence this dot: restart the container after editing for changes to take effect (exporter.py reads it once at startup, no live reload).
