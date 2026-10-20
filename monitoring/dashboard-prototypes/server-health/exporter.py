#!/usr/bin/env python3
"""Dependency-free, synthetic server health metrics; JSON reloads every scrape."""
import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

COMPONENTS = {
    **{f"fpga-{i}": "fpga" for i in range(1, 3)},
    **{f"psu-{i}": "psu" for i in range(1, 3)},
    "nic-1": "nic",
    **{f"fan-{i}": "fan" for i in range(1, 7)},
    "motherboard": "motherboard",
    "bmc": "bmc",
    "network-lan": "network_lan",
}
REQUIRED = {
    "fpga": ("temperature_celsius", "link_up"),
    "psu": ("temperature_celsius", "power_watts", "voltage_volts", "current_amperes"),
    "nic": ("temperature_celsius", "link_up"),
    "fan": ("fan_rpm",),
    "motherboard": ("temperature_celsius",),
    "bmc": ("temperature_celsius",),
    "network_lan": ("link_up",),
}
LIMIT_FIELDS = {
    "temperature_celsius": {"warning_above", "failed_above"},
    "fan_rpm": {"warning_below", "failed_below"},
    "power_watts": {"warning_above", "failed_above"},
    "voltage_volts": {"warning_below", "warning_above", "failed_below", "failed_above"},
    "current_amperes": {"warning_above", "failed_above"},
    "link_up": {"failed_equals"},
}
OPTIONAL = {
    "temperature_celsius": ("server_component_temperature_celsius", "Synthetic component temperature in degrees Celsius."),
    "fan_rpm": ("server_component_fan_rpm", "Synthetic fan speed in revolutions per minute."),
    "power_watts": ("server_component_power_watts", "Synthetic power supply output in watts."),
    "voltage_volts": ("server_component_voltage_volts", "Synthetic power supply output voltage in volts."),
    "current_amperes": ("server_component_current_amperes", "Synthetic power supply output current in amperes."),
    "link_up": ("server_component_link_up", "Synthetic component link status: 1 up, 0 down."),
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def load_data(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(data, dict) or set(data) - {"synthetic", "server", "components", "limits", "misc_readings"} or not {"synthetic", "server", "components", "limits"} <= set(data):
        raise ValueError("Expected synthetic, server, components, and limits fields")
    if data["synthetic"] is not True or data["server"] != "demo-server-01":
        raise ValueError("Data must be synthetic for demo-server-01")
    limits = data["limits"]
    if not isinstance(limits, dict) or set(limits) != set(LIMIT_FIELDS):
        raise ValueError("Limits must cover every demo metric")
    for metric, expected in LIMIT_FIELDS.items():
        rule = limits[metric]
        if not isinstance(rule, dict) or set(rule) != expected:
            raise ValueError(f"Invalid limit fields for {metric}")
        for value in rule.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"Invalid finite limit for {metric}")
            if metric != "temperature_celsius" and value < 0:
                raise ValueError(f"Negative limit for {metric}")
        if metric == "link_up":
            if type(rule["failed_equals"]) is not int or rule["failed_equals"] != 0:
                raise ValueError("link_up must fail at integer 0")
        elif metric == "voltage_volts":
            if not rule["failed_below"] < rule["warning_below"] < rule["warning_above"] < rule["failed_above"]:
                raise ValueError("Voltage limits must form nested warning/failed ranges")
        elif "warning_above" in rule:
            if not rule["warning_above"] < rule["failed_above"]:
                raise ValueError(f"Warning limit must be below failed limit for {metric}")
        elif not rule["failed_below"] < rule["warning_below"]:
            raise ValueError(f"Failed limit must be below warning limit for {metric}")
    components = data["components"]
    if not isinstance(components, dict) or set(components) != set(COMPONENTS):
        raise ValueError("Components must match the complete demo inventory")
    for name, item in components.items():
        if not isinstance(item, dict) or set(item) - set(REQUIRED[COMPONENTS[name]]):
            raise ValueError(f"Invalid fields for {name}")
        for key in OPTIONAL:
            if key in item:
                value = item[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"Invalid finite number for {name}.{key}")
                if key != "temperature_celsius" and value < 0:
                    raise ValueError(f"Negative value for {name}.{key}")
                if key == "fan_rpm" and COMPONENTS[name] != "fan":
                    raise ValueError("fan_rpm is only valid for fans")
                if key in {"power_watts", "voltage_volts", "current_amperes"} and COMPONENTS[name] != "psu":
                    raise ValueError(f"{key} is only valid for power supplies")
                if key == "link_up":
                    if COMPONENTS[name] not in {"fpga", "nic", "network_lan"}:
                        raise ValueError("link_up is only valid for FPGA, NIC, and network LAN components")
                    if not isinstance(value, int) or value not in (0, 1):
                        raise ValueError("link_up must be integer 0 or 1")
    miscellaneous = data.get("misc_readings", [])
    if not isinstance(miscellaneous, list):
        raise ValueError("misc_readings must be a list")
    names = set()
    for item in miscellaneous:
        if not isinstance(item, dict) or set(item) != {"reading", "value", "unit", "notes"}:
            raise ValueError("Each miscellaneous reading needs reading, value, unit, and notes")
        for field in ("reading", "unit", "notes"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError("Miscellaneous labels must be nonempty text")
        if item["reading"] in names:
            raise ValueError("Miscellaneous reading names must be unique")
        names.add(item["reading"])
        value = item["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Miscellaneous readings must be finite numbers")
    return data


def metric_health(item, metric, limits):
    """0 healthy, 1 degraded, 2 failed, 3 unknown; comparisons are strict."""
    if metric not in item:
        return 3
    value = item[metric]
    rule = limits[metric]
    if metric == "link_up":
        return 2 if value == rule["failed_equals"] else 0
    for level, status in (("failed", 2), ("warning", 1)):
        if f"{level}_above" in rule and value > rule[f"{level}_above"]:
            return status
        if f"{level}_below" in rule and value < rule[f"{level}_below"]:
            return status
    return 0


def component_health(statuses):
    for priority in (2, 3, 1):
        if priority in statuses:
            return priority
    return 0


def exposition(data):
    lines = [
        "# All data from this exporter is SYNTHETIC demonstration data.",
        "# HELP server_health_demo_info Identifies this synthetic demo source.",
        "# TYPE server_health_demo_info gauge",
        'server_health_demo_info{server="demo-server-01",synthetic="true"} 1',
        "# HELP server_component_health Derived synthetic health: 0 healthy, 1 degraded, 2 failed, 3 unknown. Failed wins over unknown over degraded.",
        "# TYPE server_component_health gauge",
    ]
    def labels(name):
        return f'server="demo-server-01",component="{name}",kind="{COMPONENTS[name]}"'
    for name, item in data["components"].items():
        statuses = [metric_health(item, metric, data["limits"]) for metric in REQUIRED[COMPONENTS[name]]]
        lines.append(f'server_component_health{{{labels(name)}}} {component_health(statuses)}')
    lines.extend([
        "# HELP server_component_metric_health Derived synthetic metric health: 0 healthy, 1 degraded, 2 failed, 3 unknown. Limits are demo values, not hardware specifications.",
        "# TYPE server_component_metric_health gauge",
    ])
    for name, item in data["components"].items():
        for metric in REQUIRED[COMPONENTS[name]]:
            status = metric_health(item, metric, data["limits"])
            lines.append(f'server_component_metric_health{{{labels(name)},metric="{metric}"}} {status}')
    for key, (metric, help_text) in OPTIONAL.items():
        lines.extend([f"# HELP {metric} {help_text}", f"# TYPE {metric} gauge"])
        for name, item in data["components"].items():
            if key in item:
                lines.append(f"{metric}{{{labels(name)}}} {item[key]}")
    lines.extend([
        "# HELP server_misc_reading Synthetic informational readings for the Everything else table.",
        "# TYPE server_misc_reading gauge",
    ])
    def quote(value):
        return value.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
    for item in data.get("misc_readings", []):
        fields = ','.join(f'{key}="{quote(item[key])}"' for key in ("reading", "unit", "notes"))
        lines.append(f'server_misc_reading{{server="demo-server-01",{fields}}} {item["value"]}')
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    source = None

    def do_GET(self):
        if self.path not in ("/health", "/metrics"):
            return self.reply(404, "Not found\n", "text/plain; charset=utf-8")
        try:
            data = load_data(self.source)
        except (ValueError, OSError, OverflowError, RecursionError):
            # Return no stale or partial metrics for an invalid configuration.
            return self.reply(503, "Synthetic demo source is invalid or unreadable\n", "text/plain; charset=utf-8")
        if self.path == "/health":
            return self.reply(200, "ok: synthetic demo source\n", "text/plain; charset=utf-8")
        self.reply(200, exposition(data), "text/plain; version=0.0.4; charset=utf-8")

    def reply(self, code, body, content_type):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(Path(__file__).with_name("mock-health.json")))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9100)
    args = parser.parse_args()
    load_data(args.data)
    Handler.source = args.data
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
