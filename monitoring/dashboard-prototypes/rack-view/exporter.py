#!/usr/bin/env python3
"""Synthetic textfile-collector stand-in; no NetBox runtime requests."""
import json
import math
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')
REQUIRED = {'server_id', 'rack', 'position_u', 'height_u', 'face'}

def inventory(root=ROOT):
    records = []
    seen = set()
    occupied = set()
    for path in sorted((root / 'inventory').glob('*.prom')):
        for line in path.read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            match = re.fullmatch(r'server_rack_info\{(.*)\} 1', line)
            if not match:
                raise ValueError(f'Invalid inventory metric: {path.name}')
            labels = dict(LABEL.findall(match[1]))
            if set(labels) != REQUIRED or labels['face'] not in ('front', 'rear'):
                raise ValueError('Required rack labels or face invalid')
            start, height = int(labels['position_u']), int(labels['height_u'])
            if not 1 <= start <= 42 or not 1 <= height <= 42 or start + height - 1 > 42:
                raise ValueError('Rack placement outside 1..42')
            if labels['server_id'] in seen:
                raise ValueError('Duplicate stable server_id')
            seen.add(labels['server_id'])
            for u in range(start, start + height):
                location = (labels['rack'], labels['face'], u)
                if location in occupied:
                    raise ValueError('Overlapping placement')
                occupied.add(location)
            records.append(labels)
    return records

def render(root=ROOT):
    records = inventory(root)
    health = json.loads((root / 'mock-health.json').read_text())
    lines = ['# HELP server_rack_info Provisioned machine-local inventory; position is lowest occupied U.', '# TYPE server_rack_info gauge',
             '# HELP rack_server_health Independent observed health: 0 OK, 1 Fault, 2 Unknown.', '# TYPE rack_server_health gauge']
    for labels in records:
        label_text = ','.join(k + '=' + json.dumps(v) for k, v in labels.items())
        lines.append(f'server_rack_info{{{label_text}}} 1')
        state = health.get(labels['server_id'])
        if state is not None:
            if isinstance(state, bool) or state not in (0, 1, 2):
                raise ValueError('Health must be 0, 1, 2, or omitted/null')
            lines.append(f'rack_server_health{{server_id={json.dumps(labels["server_id"])}}} {state}')
    return '\n'.join(lines) + '\n'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/metrics':
            self.send_error(404)
            return
        try:
            data = render().encode()
        except Exception as exc:
            self.send_error(503, 'Invalid demo source')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *_):
        pass

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 9104), Handler).serve_forever()
