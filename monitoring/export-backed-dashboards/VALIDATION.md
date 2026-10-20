# Verification — 2026-10-20

The independent Docker CLI lab was launched with Grafana 13.2.4 on loopback port
3003 and Prometheus on loopback port 9093. Existing prototype instances on
3001/3002 were kept running. The FHS bare-metal repository was only fast-forwarded
to development `6569833` to read the three supplied exports; no provisioning or
exporter deployment was run there.

## Executed checks

- **24 Python tests passed**, including the optional original-export parity and
  live integration tests. The seven source checks cover numeric/timestamp/schema
  parity, fixture hashes/cardinality, escaped label exposition, nonfinite values,
  invalid/duplicate samples and HTTP responses from all three sources.
- All **79 replay dashboard queries** execute successfully against Prometheus:
  63 FHS queries and 16 switch overview/detail queries. The sibling implementations
  also checked their live-source variants against the captured real job labels.
- Actual Promtool health acceptance suites pass. FHS covers complete healthy and
  degraded readings, partial coverage, absent readings, unavailable scrape,
  observed-failure precedence, unverified flags and DIMM completeness. Switch
  injects recent CRC/drop increments, error precedence, historical counters,
  up/down/unknown links, parent aggregation and stopped-source unknown fallback.
- Promtool validates the running Prometheus configuration. All three real replay
  scrape targets report UP. Scraped captured-series counts equal 103, 9,989 and
  8,641; replay-generated scrape metrics remain under separate `replay-*` jobs.
- Compose YAML, all bind-mount source paths, image digests and Python syntax
  validate. The Compose plugin is unavailable on this host, so Compose itself was
  not executed; `python3 run.py` is the verified launcher.

## Browser checks

Native Grafana was inspected in Chrome at its normal 913 × 931 viewport.

- [FHS overview](screenshots/fhs-overview.jpg): actual temperatures, card power,
  flag values and fan RPM are visible beside status tiles. Missing/partial or
  unverified data shows Unknown. The baseline has three Healthy component groups
  and nine Unknown groups under the stated conservative policy.
- [Switch overview](screenshots/switch-overview.jpg): all 34 parent ports and 62
  actual interfaces fit in one field. The snapshot contains 35 links Up and 27
  Down. Background elements do not render edit placeholders; Canvas fit requires
  the enabled `canvasPanelPanZoom` feature.
- [Switch detail](screenshots/switch-detail.jpg): clicking Port 01 opens exactly
  its four child interfaces with exported mode, VLAN IDs, reason, RX/TX rates,
  lifetime CRC and recent error/drop histories. Its historical CRC count of one
  does not create a recent Error. The dropdown was then used to select Port 33;
  it showed `eth1/33`, Up, access mode and the supplied VLAN ID.

## Limits before operational use

The test sources freeze one captured value per series; zero replay traffic rates
are not an observation of present hardware traffic. Scrape timestamps describe
the lab's current scrape, not original device freshness. Metric-type metadata was
not included in the exports. Per-port optical DOM and VLAN names are absent.
FHS flag encoding and equipment-specific temperature/fan limits still require
confirmation; the dashboard makes those gaps visible. Switch geometry is generated
from the supplied interface layout and must be regenerated for another topology.
Production deployment and physical-device fault injection were not performed.
