#!/usr/bin/env python3
"""Simulated network switch Prometheus exporter. Stdlib only, no pip deps.

Exposes 32 interfaces x 3 values (switch_interface_rx_bytes_total,
switch_interface_tx_bytes_total, switch_interface_link_up), plus hundreds of
simulated VLANs each with their own switch-wide counter
(switch_vlan_packets_total) and a random subset (6-60) assigned to each
interface (switch_interface_vlan_member), on /metrics. Link status is
injectable at runtime via POST /interfaces/<name>/link.

Also models a fixed set of real FPGA-linked interfaces (config key
fpga_links, keyed by this switch's SWITCH_ID -- see
../fpga-vlan-forwarding-plan.md and ../FPGA_LINK_DESIGN.md). A connected
server POSTs /interfaces/<name>/tx {"vlan": N} for each simulated packet;
the switch bumps that interface + the VLAN counter, then broadcasts to
every other interface (generic or FPGA) trunked on that VLAN, calling the
peer server's /fpga_links/<name>/rx for any FPGA-linked recipient so its
RX counter moves too.
"""

import json
import os
import random
import socket
import threading
import time
import urllib.request
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
    "vlan_count": 300,
    "vlan_id_start": 100,
    "vlan_min_per_interface": 6,
    "vlan_max_per_interface": 60,
    "vlan_counter_start_min": 0,
    "vlan_counter_start_max": 1000,
    "vlan_counter_step_min": 1,
    "vlan_counter_step_max": 20,
    "fpga_links": {},  # {switch_id: [{interface, vlan, peer_url}, ...]}
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
    __slots__ = ("name", "rx", "tx", "link_up", "vlans", "simulated")

    def __init__(self, name, rx, tx, vlans, simulated=True):
        self.name = name
        self.rx = rx
        self.tx = tx
        self.link_up = True
        self.vlans = vlans  # sorted list of VLAN ids trunked on this interface
        # simulated=True gets the ambient per-tick random walk (the eth*
        # pool); real FPGA links only move from actual /tx traffic, so the
        # counters mean something in the demo instead of being noise.
        self.simulated = simulated


class SwitchState:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()

        vlan_ids = [
            cfg["vlan_id_start"] + i for i in range(cfg["vlan_count"])
        ]
        self.vlans = {
            vlan_id: random.randint(cfg["vlan_counter_start_min"], cfg["vlan_counter_start_max"])
            for vlan_id in vlan_ids
        }

        self.interfaces = {}
        max_per_iface = min(cfg["vlan_max_per_interface"], len(vlan_ids))
        min_per_iface = min(cfg["vlan_min_per_interface"], max_per_iface)
        for i in range(cfg["interface_count"]):
            name = f"{cfg['interface_prefix']}{i}"
            rx = random.randint(cfg["counter_start_min"], cfg["counter_start_max"])
            tx = random.randint(cfg["counter_start_min"], cfg["counter_start_max"])
            k = random.randint(min_per_iface, max_per_iface)
            iface_vlans = sorted(random.sample(vlan_ids, k))
            self.interfaces[name] = Interface(name, rx, tx, iface_vlans)

        # Real FPGA-connected interfaces for this switch (by SWITCH_ID), each
        # on a single fixed VLAN, with a peer URL to notify on broadcast.
        self.fpga_peers = {}
        for link in cfg["fpga_links"].get(SWITCH_ID, []):
            name = link["interface"]
            vlan = link["vlan"]
            self.vlans.setdefault(
                vlan, random.randint(cfg["vlan_counter_start_min"], cfg["vlan_counter_start_max"])
            )
            self.interfaces[name] = Interface(name, 0, 0, [vlan], simulated=False)
            self.fpga_peers[name] = link["peer_url"]

    def tick(self):
        lo, hi = self.cfg["counter_step_min"], self.cfg["counter_step_max"]
        vlan_lo, vlan_hi = self.cfg["vlan_counter_step_min"], self.cfg["vlan_counter_step_max"]
        with self.lock:
            for iface in self.interfaces.values():
                if iface.link_up and iface.simulated:
                    iface.rx += random.randint(lo, hi)
                    iface.tx += random.randint(lo, hi)
            for vlan_id in self.vlans:
                self.vlans[vlan_id] += random.randint(vlan_lo, vlan_hi)

    def set_link(self, name, up):
        with self.lock:
            iface = self.interfaces.get(name)
            if iface is None:
                return False
            iface.link_up = up
            return True

    def handle_fpga_tx(self, name, vlan):
        """A connected server sent one simulated packet on interface `name`,
        tagged `vlan`. Bump that interface + the VLAN counter, then
        broadcast: every other interface trunked on `vlan` gets a tx bump,
        and any of those that are themselves FPGA-linked get their peer
        server notified (fire-and-forget) so its RX counter moves too.
        """
        peers_to_notify = []
        with self.lock:
            iface = self.interfaces.get(name)
            if iface is None or vlan is None:
                return
            iface.rx += 1
            self.vlans[vlan] = self.vlans.get(vlan, 0) + 1
            for other in self.interfaces.values():
                if other is iface or vlan not in other.vlans:
                    continue
                other.tx += 1
                peer_url = self.fpga_peers.get(other.name)
                if peer_url:
                    peers_to_notify.append(peer_url)
        for peer_url in peers_to_notify:
            notify_peer(peer_url, vlan)

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
            lines.append("# HELP switch_vlan_packets_total Simulated switch-wide packet count for the VLAN, independent of any one interface.")
            lines.append("# TYPE switch_vlan_packets_total counter")
            for vlan_id, count in self.vlans.items():
                lines.append(
                    f'switch_vlan_packets_total{{switch="{SWITCH_ID}",vlan="{vlan_id}"}} {count}'
                )
            lines.append("# HELP switch_interface_vlan_member Whether the VLAN is trunked on the interface (always 1; absent = not a member).")
            lines.append("# TYPE switch_interface_vlan_member gauge")
            for iface in self.interfaces.values():
                for vlan_id in iface.vlans:
                    lines.append(
                        f'switch_interface_vlan_member{{switch="{SWITCH_ID}",interface="{iface.name}",vlan="{vlan_id}"}} 1'
                    )
        return "\n".join(lines) + "\n"


def notify_peer(url, vlan):
    """Fire-and-forget POST telling a connected server it received a
    broadcast packet on this VLAN. Best-effort: the peer may not be up yet,
    or its endpoint may not exist -- just skip, no retries."""
    body = json.dumps({"vlan": vlan}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=2)
    except Exception:
        pass


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
        elif len(parts) == 3 and parts[0] == "interfaces" and parts[2] == "tx":
            name = parts[1]
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                payload = {}
            self.state.handle_fpga_tx(name, payload.get("vlan"))
            self.send_response(200)
            self.end_headers()
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
