#!/usr/bin/env python3
"""Create public-safe replay fixtures from the three private captured API vectors.

Never writes an original-to-placeholder inventory map. All samples retain their
original numeric strings and metric names; only identity-bearing labels change.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import uuid
from replay import load_samples

IDENTITY_LABELS = {'serial', 'ser', 'uuid', 'wwn', 'loaded_bitstream', 'programmed_bitstreams', 'board_asset_tag', 'chassis_asset_tag', 'board_id'}
MAC = re.compile(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}')
# Keep suffixes such as c0.0/1 attached to the same parent server identity.
HOST = re.compile(r'\bsys\d+|\bnx\d+[a-z]+\d+\b', re.I)
IPV4 = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
ENX = re.compile(r'\benx[0-9a-f]{12}\b', re.I)


def schema(samples):
    result = collections.Counter((x['metric']['__name__'], tuple(sorted(x['metric']))) for x in samples)
    return [{'metric': name, 'label_keys': list(keys), 'series': count} for (name, keys), count in sorted(result.items())]


def build(input_dir: Path, output_dir: Path):
    originals = {name: load_samples(input_dir / f'{name}-prometheus-sample.json') for name in ('fhs', 'node', 'switch')}
    all_values = [value for samples in originals.values() for sample in samples for value in sample['metric'].values()]
    hosts = sorted({m.group() for value in all_values for m in HOST.finditer(value)})
    # Shared server identity across FHS and node must remain shared after anonymization.
    primary = originals['fhs'][0]['metric'].get('node_name')
    hosts = ([primary] if primary in hosts else []) + [x for x in hosts if x != primary]
    replacements = {value: (f'demo-server-{i + 1:02}' if value.lower().startswith('sys') else f'demo-switch-{sum(not x.lower().startswith("sys") for x in hosts[:i])+1:02}') for i, value in enumerate(hosts)}
    ips = sorted({m.group() for value in all_values for m in IPV4.finditer(value) if m.group() not in ('0.0.0.0', '127.0.0.1', '255.255.255.255')})
    for i, value in enumerate(ips):
        ipaddress.IPv4Address(value)
        replacements[value] = f'192.0.2.{i + 1}'
    macs = sorted({m.group() for value in all_values for m in MAC.finditer(value) if m.group().lower() not in ('00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff')})
    for i, value in enumerate(macs):
        replacements[value] = ':'.join(f'{byte:02x}' for byte in (2, 0, 0, (i + 1) >> 16, ((i + 1) >> 8) & 255, (i + 1) & 255))
    for i, value in enumerate(sorted({m.group() for value in all_values for m in ENX.finditer(value)})):
        replacements[value] = f'enx02000000{i+1:04x}'
    for key in sorted(IDENTITY_LABELS):
        values = sorted({sample['metric'][key] for samples in originals.values() for sample in samples if sample['metric'].get(key)})
        for i, value in enumerate(values):
            if value in replacements:
                continue
            if key == 'uuid':
                replacements[value] = str(uuid.uuid5(uuid.NAMESPACE_URL, f'public-demo-uuid-{i+1}'))
            elif key in ('loaded_bitstream', 'programmed_bitstreams'):
                replacements[value] = f'demo_bitstream_{i+1:02}.rbf'
            else:
                replacements[value] = f'DEMO-{key.upper()}-{i+1:03}'
    # These exporter endpoints are identities, not meaningful metric semantics.
    replacements.update({'switch-telegraf:9273': 'demo-switch-exporter:9273', 'telegraf-polling-service': 'demo-polling-service'})
    changed = collections.Counter()
    def clean(key, value):
        result = value
        for original, replacement in sorted(replacements.items(), key=lambda pair: -len(pair[0])):
            result = result.replace(original, replacement)
        if key == 'mountpoint':
            result = re.sub(r'/run/user/\d+', '/run/user/1000', result)
        if result != value:
            changed[key] += 1
        return result
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    for name, samples in originals.items():
        result = [{'metric': {k: clean(k, v) for k, v in sample['metric'].items()}, 'value': list(sample['value'])} for sample in samples]
        destination = output_dir / f'{name}.json'
        document = {'status': 'success', 'data': {'resultType': 'vector', 'result': result}}
        destination.write_text(json.dumps(document, separators=(',', ':'), ensure_ascii=False) + '\n')
        validated = load_samples(destination)
        assert schema(validated) == schema(samples)
        assert [x['value'] for x in validated] == [x['value'] for x in samples]
        reports[name] = {'source_filename': f'{name}-prometheus-sample.json', 'source_sha256': hashlib.sha256((input_dir / f'{name}-prometheus-sample.json').read_bytes()).hexdigest(), 'fixture_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'series': len(samples), 'metric_names': len({x['metric']['__name__'] for x in samples}), 'schema': schema(samples), 'label_value_cardinality': {key: len({sample['metric'][key] for sample in samples if key in sample['metric']}) for key in sorted({key for sample in samples for key in sample['metric']})}}
    manifest = {'format': 1, 'source_repository': 'ska-mid-cbf-fhs-baremetal', 'source_commit': '6569833', 'mode': 'captured-static-values', 'numeric_values': 'unchanged, including source timestamps retained in fixture only', 'exposition_timestamps': 'omitted; Prometheus uses current scrape time, not device freshness', 'sanitization': {'identity_categories': ['hostnames', 'IP addresses', 'MAC addresses including MAC-based interface names', 'serials', 'UUIDs', 'WWNs', 'asset/board IDs', 'bitstream filenames', 'exporter endpoint identities', 'user runtime directory ID'], 'changed_label_occurrences': dict(sorted(changed.items())), 'mapping': 'Not persisted; deterministic placeholders preserve equality and topology.'}, 'sources': reports}
    (output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_dir', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent / 'fixtures')
    args = parser.parse_args()
    report = build(args.input_dir, args.output_dir)
    print(json.dumps({name: {'series': item['series'], 'metric_names': item['metric_names']} for name, item in report['sources'].items()}, indent=2))
