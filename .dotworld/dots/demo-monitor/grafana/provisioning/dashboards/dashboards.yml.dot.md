---
id: demo-monitor/grafana/provisioning/dashboards/dashboards.yml
source_id: Prototype
title: Dashboard provisioning provider
tags:
  - grafana
  - provisioning
source_path: $DOTWORLD_ROOT/demo-monitor/grafana/provisioning/dashboards/dashboards.yml
kind: file
summary: Provisions Grafana's dashboard file provider, pointed at ../../dashboards.
summary_blob: 728e7c272d589b510b02524ebc5ac54f2705cc4a
---

Points Grafana at ../../dashboards for auto-loaded dashboard JSON (mounted at /var/lib/grafana/dashboards in the container).
