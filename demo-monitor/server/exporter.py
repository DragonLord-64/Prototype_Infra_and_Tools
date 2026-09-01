#!/usr/bin/env python3
"""Custom Prometheus exporter simulating a handful of fluctuating server metrics.

Stdlib only, on purpose: this runs alongside node_exporter in a container we
intend to scale to many replicas, so no pip install layer.
"""

import json
import os
import random
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

CONFIG_PATH = os.environ.get("EXPORTER_CONFIG", "/config/exporter_config.json")
INSTANCE_ID = os.environ.get("SERVER_ID", socket.gethostname())

# FPGA link counters (see ../fpga-vlan-forwarding-plan.md) -- optional: only
# wired up when FPGA_LINKS_CONFIG is set, so this is a no-op for anything not
# part of the VCC/FSP fleet.
FPGA_LINKS_CONFIG = os.environ.get("FPGA_LINKS_CONFIG")
SWITCH_HOST = os.environ.get("SWITCH_HOST")
SWITCH_PORT = os.environ.get("SWITCH_PORT", "9101")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


config = load_config()
PORT = int(os.environ.get("EXPORTER_PORT", config.get("port", 9101)))
INTERVAL = float(config.get("update_interval_seconds", 2))

_lock = threading.Lock()
_values = {p["name"]: float(p["start_value"]) for p in config["parameters"]}
_max_deltas = {p["name"]: float(p.get("max_delta", 1.0)) for p in config["parameters"]}


def load_fpga_links():
    """Load the {interface, vlan} list and whether wire names need this
    server's hostname prefixed (FSPU_5's switch aggregates 48 interfaces
    across 4 servers, so their wire names must be unique; VCCU switches
    are 1:1 with a single server so plain names are fine).

    Returns interface -> {"vlan": N, "wire_name": str}.
    """
    if not FPGA_LINKS_CONFIG:
        return {}
    with open(FPGA_LINKS_CONFIG) as f:
        cfg = json.load(f)
    prefix = socket.gethostname() + "-" if cfg.get("prefix_with_hostname") else ""
    return {
        link["interface"]: {"vlan": link["vlan"], "wire_name": prefix + link["interface"]}
        for link in cfg["links"]
    }


_fpga_links = load_fpga_links()
_fpga_by_wire = {v["wire_name"]: k for k, v in _fpga_links.items()}
_fpga_lock = threading.Lock()
_fpga_tx = {name: 0 for name in _fpga_links}
_fpga_rx = {name: 0 for name in _fpga_links}


def fluctuate():
    while True:
        time.sleep(INTERVAL)
        with _lock:
            for name in _values:
                _values[name] += random.uniform(-_max_deltas[name], _max_deltas[name])


def send_fpga_packet(name, link):
    """POST one simulated packet, tagged with this link's VLAN, to the
    switch. Fire-and-forget: the switch may not be up yet, or may not
    implement the endpoint yet -- just skip and retry next tick.
    """
    url = f"http://{SWITCH_HOST}:{SWITCH_PORT}/interfaces/{link['wire_name']}/tx"
    body = json.dumps({"vlan": link["vlan"]}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=2)
    except (urllib.error.URLError, TimeoutError, OSError):
        return
    with _fpga_lock:
        _fpga_tx[name] += 1


def fpga_ticker():
    if not (_fpga_links and SWITCH_HOST):
        return
    while True:
        time.sleep(INTERVAL)
        for name, link in _fpga_links.items():
            send_fpga_packet(name, link)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        with _lock:
            lines = []
            for name, value in _values.items():
                lines.append(f"# HELP {name} Simulated telemetry value")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f'{name}{{instance="{INSTANCE_ID}"}} {value:.4f}')
        if _fpga_links:
            with _fpga_lock:
                lines.append("# HELP server_fpga_link_tx_packets_total Simulated packets sent on the FPGA link.")
                lines.append("# TYPE server_fpga_link_tx_packets_total counter")
                for name in _fpga_links:
                    lines.append(f'server_fpga_link_tx_packets_total{{instance="{INSTANCE_ID}",interface="{name}"}} {_fpga_tx[name]}')
                lines.append("# HELP server_fpga_link_rx_packets_total Simulated packets received on the FPGA link.")
                lines.append("# TYPE server_fpga_link_rx_packets_total counter")
                for name in _fpga_links:
                    lines.append(f'server_fpga_link_rx_packets_total{{instance="{INSTANCE_ID}",interface="{name}"}} {_fpga_rx[name]}')
        body = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "fpga_links" or parts[2] != "rx":
            self.send_response(404)
            self.end_headers()
            return
        name = _fpga_by_wire.get(parts[1])
        if name is None:
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)  # body is always just {"vlan": N}, not needed to bump the counter
        with _fpga_lock:
            _fpga_rx[name] += 1
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=fluctuate, daemon=True).start()
    threading.Thread(target=fpga_ticker, daemon=True).start()
    HTTPServer(("0.0.0.0", PORT), MetricsHandler).serve_forever()
