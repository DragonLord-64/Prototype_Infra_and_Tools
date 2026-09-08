# FHS Prometheus rule tables

This tool converts the FHS Prometheus exporter's recording rules into readable
threshold, aggregation, and derived-metric tables. The checked-in `rules.md`
was generated for tag `0.0.5-rc3`.

It requires Python 3.11+ and PyYAML, and reads an existing exporter checkout;
it does not fetch one. From this repository, point `--repo` at that checkout:

```sh
python3 tools/fhs-rule-tables/generate_rule_tables.py \
  --repo ../ska-mid-cbf-fhs-prometheus-exporter \
  -o tools/fhs-rule-tables/rules.md
```

Other useful forms:

```sh
# Markdown on stdout
python3 tools/fhs-rule-tables/generate_rule_tables.py --repo /path/to/exporter

# One CSV file per table
python3 tools/fhs-rule-tables/generate_rule_tables.py \
  --repo /path/to/exporter --format csv -o ./csv

# Fail if an expression cannot be described
python3 tools/fhs-rule-tables/generate_rule_tables.py \
  --repo /path/to/exporter --strict
```

When copied inside the exporter repository, `--repo` is optional: the script
walks upward from its location and the working directory to find
`etc/prometheus_config/threshold_rules.yml`.

## Inputs and layout

The tool reads:

- `etc/prometheus_config/{threshold,aggregation}_rules.yml`
- `src/fhs_prometheus_exporter/*_collector.py`
- `src/fhs_prometheus_exporter/common.py`

The modules beside the entry point form a small pipeline: `promql.py` parses
expressions, `collectors.py` extracts metric labels without importing collector
code, `rules.py` loads and resolves rules, `describe.py` produces plain-English
rows, and `render.py` writes Markdown or CSV. Keep these files together.

Unrecognized expressions are listed under **Not described** and produce a
warning. `--strict` makes those warnings fail the command, which is useful in
CI. Startup diagnostics on stderr identify the source checkout and the number
of rules, metrics, and collectors found.
