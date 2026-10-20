#!/usr/bin/env python3
"""Replay sanitized Prometheus instant-vector samples as text exposition."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re

FIXTURES = Path(__file__).parent / 'fixtures'
METRIC_NAME = re.compile(r'[a-zA-Z_:][a-zA-Z0-9_:]*\Z')
LABEL_NAME = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*\Z')


def escape_label(value: str) -> str:
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')


def sample_value(value: str) -> str:
    # Prometheus uses exactly these spellings for non-finite float samples.
    if value in ('NaN', '+Inf', '-Inf'):
        return value
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid sample value: {value!r}') from exc
    if not math.isfinite(number):
        raise ValueError('Non-finite samples must use NaN, +Inf or -Inf')
    return value


def load_samples(path: Path) -> list[dict]:
    document = json.loads(path.read_text())
    if document.get('status') != 'success' or document.get('data', {}).get('resultType') != 'vector':
        raise ValueError('Expected successful Prometheus instant-vector API response')
    samples = document['data']['result']
    if not isinstance(samples, list) or not samples:
        raise ValueError('Expected nonempty vector')
    seen = set()
    for sample in samples:
        labels = sample.get('metric', {})
        if not isinstance(labels, dict) or not METRIC_NAME.fullmatch(labels.get('__name__', '')):
            raise ValueError('Invalid metric name')
        if not all(isinstance(v, str) and LABEL_NAME.fullmatch(k) for k, v in labels.items()):
            raise ValueError('Invalid label name/value')
        pair = sample.get('value')
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[1], str):
            raise ValueError('Expected [timestamp, numeric-string] sample')
        sample_value(pair[1])
        identity = tuple(sorted(labels.items()))
        if identity in seen:
            raise ValueError('Duplicate metric/label identity')
        seen.add(identity)
    return samples


def render(samples: list[dict]) -> bytes:
    lines = ['# Sanitized captured snapshot replay. Static values; scrape time is not device freshness.']
    for sample in samples:
        labels = sample['metric']
        name = labels['__name__']
        suffix = ','.join(f'{key}="{escape_label(value)}"' for key, value in sorted(labels.items()) if key != '__name__')
        # Deliberately omit source timestamps: Prometheus assigns current scrape time.
        lines.append(f'{name}{{{suffix}}} {sample_value(sample["value"][1])}')
    return ('\n'.join(lines) + '\n').encode()


def make_handler(payload: bytes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/metrics':
                data, kind = payload, 'text/plain; version=0.0.4; charset=utf-8'
            elif self.path in ('/health', '/-/ready'):
                data, kind = b'OK\n', 'text/plain; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *_):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, choices=('fhs', 'node', 'switch'))
    parser.add_argument('--port', type=int, default=9110)
    parser.add_argument('--bind', default='0.0.0.0')
    args = parser.parse_args()
    payload = render(load_samples(FIXTURES / f'{args.source}.json'))
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(payload))
    print(f'{args.source}: static captured-value replay on {args.bind}:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
