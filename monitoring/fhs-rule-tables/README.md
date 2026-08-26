# FHS Prometheus rule tables

`generate_rule_tables.py` turns the FHS exporter's Prometheus rules into tables
that can be read without knowing PromQL:

1. **Threshold rules** — every check, the metrics it reads, and the condition
   that sets it to `1`.
2. **Aggregation rules** — every component health state, its **child metrics**,
   and what makes it fail.
3. **Derived metrics** — the intermediate calculations the checks compare against.

[`rules.md`](rules.md) is the generated output for tag `0.0.5-rc3`.

## Where it belongs

The script is written to live in the exporter repository — drop it in as
`tools/generate_rule_tables.py` and run it with no arguments:

```sh
python3 tools/generate_rule_tables.py -o docs/src/rules.md
```

It finds the repository by walking up from its own location (then from the
working directory), so it works from anywhere inside a checkout — and reports
the ref it read, so the tables always say which rules they describe. It is a
single file with no imports beyond the standard library and PyYAML. The copy
here is the reference copy.

## Usage

```sh
python3 generate_rule_tables.py                       # markdown to stdout
python3 generate_rule_tables.py -o rules.md           # markdown to a file
python3 generate_rule_tables.py --format csv -o ./csv # one CSV per table
python3 generate_rule_tables.py --repo ../ska-mid-cbf-fhs-prometheus-exporter
```

`--strict` exits non-zero if any expression could not be described, which makes
it usable as a CI check when the rules change. It reads only a checkout you
already have — it never fetches anything. Requires Python 3.11+ and PyYAML.

## How it works

Everything is derived from the exporter repository — nothing is hard-coded.

| Input | Used for |
| --- | --- |
| `etc/prometheus_config/threshold_rules.yml` | records, metrics, thresholds, `record_tag` |
| `etc/prometheus_config/aggregation_rules.yml` | records, selectors, structure |
| `src/fhs_prometheus_exporter/*_collector.py` | the `source`/`data_type` label on each metric, and its documented meaning |
| `src/fhs_prometheus_exporter/common.py` | `MetricUnit`/`MetricDataType`, to rebuild series names (`volt_bat` + `volts`) |

Collectors are picked up by glob, so one added later is included without
touching the script.

1. **Parse** — both rule files are read with PyYAML and every `expr` is parsed
   into an AST by a small PromQL parser covering the subset the rules use.
2. **Label** — the aggregation rules select inputs by label, e.g.
   `{source='CPU', record_tag='component_critical'}`. `record_tag` comes from
   the rule file, but `source`/`data_type` are attached by the collectors, so
   each collector module is parsed with `ast` (never imported) to recover the
   `SourceName` enum, the exported series names, and the metric tables.
3. **Resolve** — each rule's inputs are followed through other records, so a
   rule inherits the labels of the metrics it ultimately reads. A selector then
   matches a rule only if every matcher matches, `device` included.
4. **Describe** — comparisons are pulled out of the AST, merged where they share
   an operator and threshold (`below 20 or above 85`), and the outer operator
   becomes the quantifier (`> bool 1` → "more than one"). Anything that matches
   no known shape is listed under "Not described" rather than dropped silently.

Each metric's `documentation=` string from its collector fills the *measures*
column, and glosses a child metric named in an aggregation condition — so
`instance:fan_temperature_celcius:critical` reads as the fan speed controller
temperature it actually watches. A child whose value is a count is glossed as
one, rather than being mistaken for a 0/1 flag.

On startup the script reports to stderr which checkout and ref it is reading,
and how many rules, metrics and collectors it found. If that says 0 metrics, the collector modules did not parse and every
health state will read "never becomes 1"; the table names the labels that went
unmatched.

Child metrics are listed one level deep: `psu_failed` lists `psu1_failed` and
`psu2_failed`, not the eight PSU checks underneath each.

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
