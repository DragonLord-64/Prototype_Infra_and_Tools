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
from http.server import BaseHTTPRequestHandler, HTTPServer

CONFIG_PATH = os.environ.get("EXPORTER_CONFIG", "/config/exporter_config.json")
INSTANCE_ID = os.environ.get("SERVER_ID", socket.gethostname())


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


config = load_config()
PORT = int(os.environ.get("EXPORTER_PORT", config.get("port", 9101)))
INTERVAL = float(config.get("update_interval_seconds", 2))

_lock = threading.Lock()
_values = {p["name"]: float(p["start_value"]) for p in config["parameters"]}
_max_deltas = {p["name"]: float(p.get("max_delta", 1.0)) for p in config["parameters"]}


def fluctuate():
    while True:
        time.sleep(INTERVAL)
        with _lock:
            for name in _values:
                _values[name] += random.uniform(-_max_deltas[name], _max_deltas[name])


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
            body = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=fluctuate, daemon=True).start()
    HTTPServer(("0.0.0.0", PORT), MetricsHandler).serve_forever()
