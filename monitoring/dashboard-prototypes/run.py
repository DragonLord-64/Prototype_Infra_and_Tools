#!/usr/bin/env python3
"""Start the isolated demo with Docker CLI when Compose is unavailable."""
from pathlib import Path
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parent
PREFIX = 'grafana-dashboard-prototypes'
LABEL = 'org.dashboard-prototypes.owner'
NETWORK = PREFIX + '-net'
PYTHON = 'python@sha256:6857d2dae63e052057f2db389a7061188ac9a92a3fa8d402bde68f36df6fada1'
GRAFANA = 'grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f'
PROMETHEUS = 'prom/prometheus@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e'

def docker(*args, check=True):
    return subprocess.run(['docker', *map(str, args)], check=check, text=True, capture_output=True)

def mount(source, target):
    return ['--mount', f'type=bind,src={ROOT / source},dst={target},readonly']

def start(service, image, args, command=()):
    name = PREFIX + '-' + service
    found = docker('container', 'inspect', name, check=False)
    if found.returncode == 0:
        info = json.loads(found.stdout)[0]
        if info['Config'].get('Labels', {}).get(LABEL) != PREFIX:
            raise RuntimeError(f'Refusing to reuse unowned container {name}')
        docker('start', name)
    else:
        docker('run', '-d', '--name', name, '--label', f'{LABEL}={PREFIX}',
               '--network', NETWORK, '--network-alias', service, *args, image, *command)
    print(name)

def main():
    port = int(os.environ.get('GRAFANA_DEMO_PORT', '3002'))
    if not 1 <= port <= 65535:
        raise ValueError('GRAFANA_DEMO_PORT must be between 1 and 65535')
    if docker('network', 'inspect', NETWORK, check=False).returncode != 0:
        docker('network', 'create', '--label', f'{LABEL}={PREFIX}', NETWORK)
    for folder, service in [
        ('server-health', 'server-health-demo-exporter'),
        ('cisco-switch', 'cisco-switch-demo-exporter'),
        ('vccu-fspu', 'vccu-fspu-demo-exporter'),
        ('vlan-net-viewer', 'vlan-net-viewer-demo-exporter'),
    ]:
        start(service, PYTHON, [*mount(folder, '/app'), '-w', '/app'], ['python', '-B', 'exporter.py'])
    start('prometheus', PROMETHEUS,
          [*mount('prometheus.yml', '/etc/prometheus/prometheus.yml'),
           '-v', PREFIX + '-prometheus-data:/prometheus'],
          ['--config.file=/etc/prometheus/prometheus.yml', '--storage.tsdb.path=/prometheus',
           '--storage.tsdb.retention.time=2d'])
    args = ['-p', f'127.0.0.1:{port}:3000', '-v', PREFIX + '-grafana-data:/var/lib/grafana',
            *mount('grafana/provisioning', '/etc/grafana/provisioning')]
    for folder in ['server-health', 'cisco-switch', 'vccu-fspu', 'vlan-net-viewer']:
        args += mount(folder + '/grafana/dashboards', '/var/lib/grafana/dashboards/' + folder)
    start('grafana', GRAFANA, args)
    print(f'Open http://localhost:{port}')
    print('Existing containers are started without changing their configuration. Use Compose for managed updates, or recreate only these labelled demo containers after changing launcher settings.')

if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or str(exc))
