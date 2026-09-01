#!/usr/bin/env python3
"""Simulated network switch Prometheus exporter. Stdlib only, no pip deps.

Exposes 32 interfaces x 3 values (switch_interface_rx_bytes_total,
switch_interface_tx_bytes_total, switch_interface_link_up) on /metrics.
Link status is injectable at runtime via POST /interfaces/<name>/link.
"""

import json
import os
import random
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CONFIG_PATH = os.environ.get("SWITCH_CONFIG", "/config/config.json")
SWITCH_ID = os.environ.get("SWITCH_ID") or socket.gethostname()
LISTEN_PORT = int(os.environ.get("SWITCH_PORT", "9101"))

DEFAULT_CONFIG = {
    "interface_count": 32,
    "interface_prefix": "eth",
    "counter_start_min": 0,
    "counter_start_max": 1000,
    "counter_step_min": 1,
    "counter_step_max": 20,
    "tick_seconds": 0.5,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    return cfg


class Interface:
    __slots__ = ("name", "rx", "tx", "link_up")

    def __init__(self, name, rx, tx):
        self.name = name
        self.rx = rx
        self.tx = tx
        self.link_up = True


class SwitchState:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.interfaces = {}
        for i in range(cfg["interface_count"]):
            name = f"{cfg['interface_prefix']}{i}"
            rx = random.randint(cfg["counter_start_min"], cfg["counter_start_max"])
            tx = random.randint(cfg["counter_start_min"], cfg["counter_start_max"])
            self.interfaces[name] = Interface(name, rx, tx)

    def tick(self):
        lo, hi = self.cfg["counter_step_min"], self.cfg["counter_step_max"]
        with self.lock:
            for iface in self.interfaces.values():
                if iface.link_up:
                    iface.rx += random.randint(lo, hi)
                    iface.tx += random.randint(lo, hi)

    def set_link(self, name, up):
        with self.lock:
            iface = self.interfaces.get(name)
            if iface is None:
                return False
            iface.link_up = up
            return True

    def render_metrics(self):
        lines = [
            "# HELP switch_interface_rx_bytes_total Simulated received bytes on the interface.",
            "# TYPE switch_interface_rx_bytes_total counter",
        ]
        with self.lock:
            for iface in self.interfaces.values():
                lines.append(
                    f'switch_interface_rx_bytes_total{{switch="{SWITCH_ID}",interface="{iface.name}"}} {iface.rx}'
                )
            lines.append("# HELP switch_interface_tx_bytes_total Simulated transmitted bytes on the interface.")
            lines.append("# TYPE switch_interface_tx_bytes_total counter")
            for iface in self.interfaces.values():
                lines.append(
                    f'switch_interface_tx_bytes_total{{switch="{SWITCH_ID}",interface="{iface.name}"}} {iface.tx}'
                )
            lines.append("# HELP switch_interface_link_up Link status of the interface (1 = up, 0 = down).")
            lines.append("# TYPE switch_interface_link_up gauge")
            for iface in self.interfaces.values():
                lines.append(
                    f'switch_interface_link_up{{switch="{SWITCH_ID}",interface="{iface.name}"}} {1 if iface.link_up else 0}'
                )
        return "\n".join(lines) + "\n"


def ticker(state, interval):
    while True:
        time.sleep(interval)
        state.tick()


class Handler(BaseHTTPRequestHandler):
    state = None  # type: SwitchState

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            body = self.state.render_metrics().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "interfaces" and parts[2] == "link":
            name = parts[1]
            qs = parse_qs(parsed.query)
            desired = qs.get("state", ["up"])[0].lower()
            if desired not in ("up", "down"):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"state must be 'up' or 'down'\n")
                return
            ok = self.state.set_link(name, desired == "up")
            if ok:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f"{name} link set to {desired}\n".encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(f"unknown interface {name}\n".encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    cfg = load_config()
    state = SwitchState(cfg)
    Handler.state = state

    t = threading.Thread(target=ticker, args=(state, cfg["tick_seconds"]), daemon=True)
    t.start()

    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
