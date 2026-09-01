---
id: demo-monitor/prometheus/rules.yml
source_id: Prototype
title: Prometheus alerting rules
tags: []
source_path: $DOTWORLD_ROOT/demo-monitor/prometheus/rules.yml
kind: file
summary: Basic threshold alerting rules for demo-monitor, loaded via prometheus.yml's rule_files. Three rules watch the custom server params (server_param_a/b/c) against arbitrary but data-informed bands (sized off live values, none currently tripped); one watches switch_interface_link_up per interface; three watch up==0 per scrape job (node_exporter, custom server exporter, switch exporter). No aggregation/recording rules yet -- deliberately deferred.
summary_blob: 504d57617b5091bcee095cb893ed4469e938d1fc
---

