#!/usr/bin/env python3
"""Launch the isolated export-backed Grafana lab using Docker CLI."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
PREFIX = 'fhs-export-backed'
LABEL = 'org.export-backed.owner'
NETWORK = PREFIX + '-net'
IMAGES = {
    'python': 'python@sha256:6857d2dae63e052057f2db389a7061188ac9a92a3fa8d402bde68f36df6fada1',
    'grafana': 'grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f',
    'prometheus': 'prom/prometheus@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e',
}


def docker(*args, check=True):
    result = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def bind(source, target):
    path = ROOT / source
    if not path.exists():
        raise FileNotFoundError(path)
    return ['--mount', f'type=bind,src={path},dst={target},readonly']


def owned(info):
    return info.get('Config', {}).get('Labels', {}).get(LABEL) == PREFIX


def start(service, image, args, command=()):
    name = PREFIX + '-' + service
    previous = docker('inspect', name, check=False)
    if previous.returncode == 0:
        info = json.loads(previous.stdout)[0]
        if not owned(info):
            raise RuntimeError(f'Refusing to reuse unowned container {name}')
        # A checkout move must never silently keep serving a different fixture.
        for mount in info.get('Mounts', []):
            if mount['Type'] == 'bind' and not Path(mount['Source']).is_relative_to(ROOT):
                raise RuntimeError(f'{name} uses another checkout; stop and remove this lab container before relaunching')
        docker('start', name)
    else:
        docker('run', '-d', '--name', name, '--label', f'{LABEL}={PREFIX}',
               '--network', NETWORK, '--network-alias', service, '--restart', 'unless-stopped',
               *args, image, *command)
    print(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'status', 'stop'], nargs='?', default='up')
    args = parser.parse_args()
    if args.action == 'status':
        print(docker('ps', '-a', '--filter', f'label={LABEL}={PREFIX}',
                     '--format', '{{.Names}}\t{{.Status}}\t{{.Ports}}').stdout, end='')
        return
    if args.action == 'stop':
        ids = docker('ps', '-q', '--filter', f'label={LABEL}={PREFIX}').stdout.split()
        if ids:
            print(docker('stop', *ids).stdout, end='')
        return
    grafana_port = int(os.environ.get('EXPORT_GRAFANA_PORT', '3003'))
    prometheus_port = int(os.environ.get('EXPORT_PROMETHEUS_PORT', '9093'))
    if any(not 1 <= port <= 65535 for port in (grafana_port, prometheus_port)):
        raise ValueError('Port must be in 1..65535')
    if grafana_port == prometheus_port:
        raise ValueError('Grafana and Prometheus ports must differ')
    found = docker('network', 'inspect', NETWORK, check=False)
    if found.returncode:
        docker('network', 'create', '--label', f'{LABEL}={PREFIX}', NETWORK)
    elif json.loads(found.stdout)[0].get('Labels', {}).get(LABEL) != PREFIX:
        raise RuntimeError('Refusing to reuse unowned network')
    for source in ['fhs', 'node', 'switch']:
        start(source, IMAGES['python'], [*bind('sources', '/app'), '-w', '/app'],
              ['python', '-B', 'replay.py', '--source', source, '--port', '9100'])
    start('prometheus', IMAGES['prometheus'], [
        *bind('prometheus.yml', '/etc/prometheus/prometheus.yml'),
        '-p', f'127.0.0.1:{prometheus_port}:9090',
        '-v', PREFIX + '-prometheus-data:/prometheus',
    ], ['--config.file=/etc/prometheus/prometheus.yml', '--storage.tsdb.path=/prometheus',
        '--storage.tsdb.retention.time=2d'])
    start('grafana', IMAGES['grafana'], [
        '-p', f'127.0.0.1:{grafana_port}:3000',
        '-e', 'GF_FEATURE_TOGGLES_ENABLE=canvasPanelPanZoom',
        '-v', PREFIX + '-grafana-data:/var/lib/grafana',
        *bind('grafana/provisioning', '/etc/grafana/provisioning'),
        *bind('fhs/grafana/dashboards', '/var/lib/grafana/dashboards/fhs'),
        *bind('switch/grafana/dashboards', '/var/lib/grafana/dashboards/switch'),
    ])
    print(f'Grafana: http://localhost:{grafana_port} | Prometheus: http://localhost:{prometheus_port}')
    print('Snapshot replay: captured values, synthetic scrape times. Existing container settings are retained.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc))
