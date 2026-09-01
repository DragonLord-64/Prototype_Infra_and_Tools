---
id: demo-monitor/prometheus/rules.yml
source_id: Prototype
title: Prometheus alerting rules
tags: []
source_path: $DOTWORLD_ROOT/demo-monitor/prometheus/rules.yml
kind: file
summary: 'Basic threshold alerting rules for demo-monitor, loaded via prometheus.yml''s rule_files. Server params (a/b/c) monitored against data-informed bands; switch_interface_link_up watched per interface; up==0 watched per scrape job. Also a cross-switch VLAN packet-rate parity check: alerts if any switch''s rate(switch_vlan_packets_total[10m]) for a given vlan deviates >30% from the cross-switch average for that vlan, sustained 5m -- currently max deviation observed is ~10%, well under threshold. Has a documented caveat: once FPGA-link broadcast traffic goes live (fpga-vlan-forwarding-plan.md), FSPU_5''s shared switch is expected to legitimately run hotter on vlans 100-111 (4 servers fan into one switch there vs 1:1 for VCCU), which will need this rule revisited. No other aggregation/recording rules yet.'
summary_blob: 5f8a57610fa92cc8b237a385f8be8dccea838605
---

