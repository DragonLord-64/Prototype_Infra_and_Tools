---
id: demo-monitor/server/entrypoint.sh
source_id: Prototype
title: Dual-process entrypoint
tags:
  - docker
  - server
  - supervision
source_path: $DOTWORLD_ROOT/demo-monitor/server/entrypoint.sh
kind: code
summary: POSIX shell entrypoint for the server container. Starts node_exporter in the background listening on $NODE_EXPORTER_PORT (default 9100), then starts the Python custom exporter (exporter.py) in the background too, and records both PIDs. Registers a TERM/INT trap that kills both children and waits on them before exiting. Polls once a second with kill -0 to see if either process has died; as soon as one has, it runs the same cleanup/exit path. Keeps the container's lifecycle tied to both processes without a supervisor daemon.
summary_blob: eaf501e7b7efb5375e5426a857f32b39a7f5dd5f
---

Runs node_exporter and the custom exporter as two background jobs and polls kill -0 on both once a second to detect either exiting. Deliberately NOT using 'wait -n' (would be the obvious simplification): the container's /bin/sh is busybox ash on Alpine, and busybox's wait doesn't support -n, so that pattern silently breaks signal/exit handling on this base image. SIGTERM/SIGINT are trapped to kill both children before exit.
