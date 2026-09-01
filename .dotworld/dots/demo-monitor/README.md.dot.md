---
id: demo-monitor/README.md
source_id: Prototype
title: demo-monitor README
tags:
  - docs
  - overview
source_path: $DOTWORLD_ROOT/demo-monitor/README.md
kind: prose
summary: 'Top-level overview of the demo-monitor project: a Prometheus/Grafana demo with two simulated containers (server, switch), monitored by Prometheus and visualized in Grafana. Sections: Concept, Telemetry simulation, and one section per landed component -- Server (node_exporter + 3-param custom exporter, ~118MB image), Switch (32 simulated interfaces, rx/tx counters + link status, ~83MB image), Prometheus (compose location, scrape targets, network) -- each written by the agent that built that piece. Status line is stale, still says just getting started despite multiple components now implemented.'
summary_blob: c6efff69a0e70b3ccefcba05e5f70678c02b1a22
---

Shared, actively-edited file: multiple agents (server-container, switch-container, prometheus-agent, grafana-agent) each append their own section documenting their piece as it lands, rather than one owner rewriting the whole thing. This update added the Switch (switch-container) section, describing the 32-interface exporter, its metrics, and how link failures are injected at runtime. Check git blame/log for who wrote which section before editing someone else's.
