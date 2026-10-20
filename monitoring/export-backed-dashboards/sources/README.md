# Captured-format test sources

These three Python standard-library HTTP exporters replay the supplied Prometheus
instant-vector exports. They retain every metric name, label key and numeric
sample, including the FHS `celcius` spelling and the node job named `node`.
Inventory identities are replaced with deterministic demo values before committing.

| Source | Series | Distinct metric names | Captured job |
| --- | ---: | ---: | --- |
| FHS | 103 | 67 | `fhs-exporter` |
| Node Exporter | 9,989 | 7,175 | `node` |
| Switch / Telegraf | 8,641 | 193 | `switch-telegraf` |

The shared server is `demo-server-01`; the switch is `demo-switch-01`. Instance
labels retain endpoint shape and original ports, with documentation-range IPs or
demo DNS names. Hostnames embedded in interface descriptions, MAC-based interface
names, serials, UUIDs and bitstream filenames are also sanitized. Equality between
identities and distinct-value cardinalities are preserved. The reverse inventory
mapping is deliberately absent.

## Run one source

From this directory, using Python 3:

```bash
python3 replay.py --source fhs --port 9110
python3 replay.py --source node --port 9100
python3 replay.py --source switch --port 9273
```

Each command is a separate process; run only the source you need or use the
[parent container launcher](../README.md). `/metrics` serves Prometheus text
exposition; `/health` and `/-/ready` return `OK`. Bind defaults to `0.0.0.0` for
container access; pass `--bind 127.0.0.1` for a host-local process.

Prometheus must scrape with `honor_labels: true` so the captured `job` and
`instance` labels retain their shape. Use distinct scrape jobs such as
`replay-fhs`, `replay-node` and `replay-switch`. The captures also contain `up` and
`scrape_*` series: these are captured values, not proof the replay endpoint is
reachable. Use Prometheus's own `up{job="replay-fhs"}` (and equivalents) for
current exporter availability.

## Snapshot limits

This is **static captured-value replay**, not traffic generation. A single instant
sample cannot establish live traffic rates or counter increments. Repeated counter
samples produce zero rates after the history window fills. Historical recording
rule values included in the switch export remain captured values, not freshly
calculated rates. No synthetic increments are silently added.

Original timestamps remain in the JSON fixtures for provenance, but `/metrics`
omits explicit timestamps so Prometheus assigns the current scrape time. This
makes the test source usable now; it does **not** establish the freshness of the
original device data. Timestamp-valued metrics such as boot times retain their
captured numeric values as well. Dashboard refresh and source-device freshness
are different things.

## Evidence and regeneration

[fixtures/manifest.json](fixtures/manifest.json) records the source repository and
commit, source/fixture SHA-256 hashes, series and metric counts, metric/label-key
schemas and label-value cardinalities. Its schemas are intentionally complete,
including the large Node Exporter/ethtool metric family. Original private exports
are not copied into this repository.

To regenerate from a local, authorized copy of the three original API responses:

```bash
python3 build_fixtures.py /path/to/monitoring/example_output
```

Expected input names are `fhs-prometheus-sample.json`,
`node-prometheus-sample.json` and `switch-prometheus-sample.json`. Review the
sanitized fixture diff before publishing; a different inventory or label schema
may require additional identity sanitization rules. Restart source processes after
regeneration because each loads and validates its fixture at startup.

From the parent directory, run the source tests:

```bash
python3 -m unittest discover -s tests -p test_sources.py -v
```

For an additional local parity check against the private originals:

```bash
PROMETHEUS_ORIGINAL_EXPORT_DIR=/path/to/monitoring/example_output \
  python3 -m unittest discover -s tests -p test_sources.py -v
```

The tests validate fixture hashes, full series counts and label cardinalities,
metric names, numeric strings, escaping, non-finite Prometheus values, duplicate
rejection and all three HTTP endpoints. The optional parity check compares every
original numeric sample and timestamp, metric name and label-key set without
publishing private label values.
