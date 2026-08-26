# FHS Prometheus rule tables

`generate_rule_tables.py` turns the FHS exporter's Prometheus rules into two
tables that can be read without knowing PromQL:

1. **Threshold rules** — every check, the metrics it reads, and the condition
   that sets it to `1`.
2. **Aggregation rules** — every component health state, its **child metrics**,
   and what makes it fail.

A third table lists the intermediate calculations (utilisation percentages,
core counts) the threshold rules compare against.

[`rules.md`](rules.md) is the generated output for tag `0.0.5-rc3`.

## Usage

```sh
# clone the exporter at a tag and write markdown
./generate_rule_tables.py --ref 0.0.5-rc3 -o rules.md

# use a checkout you already have
./generate_rule_tables.py --repo ../ska-mid-cbf-fhs-prometheus-exporter

# spreadsheet-friendly output
./generate_rule_tables.py --ref 0.0.5-rc3 --format csv -o ./csv
```

`--strict` exits non-zero if any expression could not be described, which makes
it usable as a CI check when the rules change. Requires Python 3.11+, PyYAML
and `git`.

## Where the data comes from

Everything is derived from the exporter repository — nothing is hard-coded here.

| File | Used for |
| --- | --- |
| `etc/prometheus_config/threshold_rules.yml` | records, metrics, thresholds, `record_tag` |
| `etc/prometheus_config/aggregation_rules.yml` | records, selectors, structure |
| `src/fhs_prometheus_exporter/ipmitool_collector.py` | `source`/`data_type` for IPMI metrics |
| `src/fhs_prometheus_exporter/fpga_collector.py` | `source` = `FPGA0`/`FPGA1` |
| `src/fhs_prometheus_exporter/nvidia_nic_collector.py` | `source` = `NIC` |
| `src/fhs_prometheus_exporter/bist_collector.py` | `source` = `BIST` |
| `src/fhs_prometheus_exporter/common.py` | `MetricUnit`/`MetricDataType`, to rebuild series names (`volt_bat` + `volts`) |

The aggregation rules pick their inputs by label, e.g.
`{source='CPU', record_tag='component_critical'}`. `record_tag` is set in the
rule file, but `source` and `data_type` are attached by the collectors, so the
collector modules are parsed (via `ast`, not imported) to recover them. That is
why the child metrics are resolved rather than guessed.

Child metrics are listed one level deep: `psu_failed` lists `psu1_failed` and
`psu2_failed`, not the eight PSU checks underneath each.

## Layout

| File | Role |
| --- | --- |
| `generate_rule_tables.py` | CLI, table rendering |
| `promql.py` | parser for the PromQL subset the rule files use |
| `collectors.py` | reads `source`/`data_type` labels out of the collector modules |
| `rules.py` | rule model, label resolution, selector matching |
| `describe.py` | plain-English wording |

## Things the tables surface

- `cpu_degraded`, `dimm_degraded` and `nvme_degraded` have **no** child metrics:
  no warning-level check carries those labels, so they can never become `1`.
- `instance:fan_rpm:critical` is a **count** of fans below 200 rpm (0–7), not a
  0/1 flag. `fans_degraded` fires on exactly one, `fans_failed` on more than one.
- `instance:lan_temperature_celcius:{warning,critical}` and
  `instance:nic_temperature_celcius:critical` are added to their health states
  outside the label selector, because those series carry no `device` label. The
  addition means the health state can evaluate to `2` rather than `1` when the
  temperature check and another child trip together.
