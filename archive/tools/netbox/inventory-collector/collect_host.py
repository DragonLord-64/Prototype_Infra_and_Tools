#!/usr/bin/env python3
"""Collect one Linux host's NetBox-relevant hardware inventory as JSON."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import subprocess
from pathlib import Path


def run(argv, warnings, name):
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"{name}: {exc}")
        return ""
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().replace("\n", "; ")
        warnings.append(f"{name}: exit {result.returncode}: {detail[:300]}")
        return ""
    return result.stdout


def dmidecode(kind, warnings):
    return run(["dmidecode", "--type", kind], warnings, f"dmidecode {kind}")


def dmi_records(text):
    records = []
    for block in re.split(r"\n\s*\n", text):
        values = {}
        for line in block.splitlines():
            match = re.match(r"\s*([^:\t]+):\s*(.*)$", line)
            if match:
                values[match.group(1).strip()] = match.group(2).strip()
        if values:
            records.append(values)
    return records


def useful(value):
    return bool(value and value.lower() not in {"unknown", "not specified", "none", "no module installed"})


def os_release():
    values = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def network(warnings):
    links_raw = run(["ip", "-j", "link", "show"], warnings, "ip link")
    addresses_raw = run(["ip", "-j", "address", "show"], warnings, "ip address")
    try:
        links = json.loads(links_raw or "[]")
        addresses = json.loads(addresses_raw or "[]")
    except json.JSONDecodeError as exc:
        warnings.append(f"network JSON: {exc}")
        return []
    addresses_by_name = {item.get("ifname"): item.get("addr_info", []) for item in addresses}
    result = []
    for link in links:
        name = link.get("ifname")
        if not name or name == "lo":
            continue
        driver = run(["ethtool", "-i", name], [], f"ethtool -i {name}")
        driver_fields = dict(
            match.groups()
            for line in driver.splitlines()
            if (match := re.match(r"([^:]+):\s*(.*)", line))
        )
        bus_info = driver_fields.get("bus-info", "")
        pci = {}
        if re.fullmatch(r"(?:[0-9a-fA-F]{4}:)?[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]", bus_info):
            verbose = run(["lspci", "-s", bus_info, "-vv"], [], f"lspci {bus_info}")
            summary = run(["lspci", "-s", bus_info, "-mm"], [], f"lspci {bus_info} summary")
            quoted = re.findall(r'"([^"]*)"', summary)
            if len(quoted) >= 3:
                pci["manufacturer"] = quoted[1]
                pci["product"] = quoted[2]
            for pattern, key in (
                (r"\[PN\]\s*Part number:\s*(.*)", "part_id"),
                (r"\[SN\]\s*Serial number:\s*(.*)", "serial"),
                (r"Product Name:\s*(.*)", "product_name"),
            ):
                match = re.search(pattern, verbose, re.I)
                if match and useful(match.group(1)):
                    pci[key] = match.group(1).strip()
        transceiver = run(["ethtool", "-m", name], [], f"ethtool -m {name}")
        module = {}
        for label, key in (
            ("Identifier", "identifier"), ("Vendor name", "manufacturer"),
            ("Vendor PN", "part_id"), ("Vendor SN", "serial"), ("Vendor rev", "revision"),
        ):
            match = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.*?)\s*$", transceiver, re.M | re.I)
            if match and useful(match.group(1)):
                module[key] = match.group(1)
        result.append({
            "name": name,
            "mac_address": link.get("address", ""),
            "enabled": "UP" in link.get("flags", []),
            "mtu": link.get("mtu"),
            "driver": driver_fields.get("driver", ""),
            "firmware": driver_fields.get("firmware-version", ""),
            "bus_info": bus_info,
            "pci": pci,
            "addresses": [
                f"{entry['local']}/{entry['prefixlen']}" for entry in addresses_by_name.get(name, [])
                if entry.get("family") in ("inet", "inet6") and entry.get("scope") != "link"
            ],
            "transceiver": module,
        })
    return result


def extra_probes(specs, warnings):
    results = []
    for spec in specs:
        name, command = spec.get("name", "custom"), spec.get("command", "")
        if not command:
            continue
        try:
            proc = subprocess.run(
                command, shell=True, executable="/bin/bash", text=True,
                capture_output=True, timeout=int(spec.get("timeout", 30)), check=False,
            )
            results.append({"name": name, "category": spec.get("category", "custom"),
                            "command": command, "returncode": proc.returncode,
                            "stdout": proc.stdout, "stderr": proc.stderr})
            if proc.returncode:
                warnings.append(f"custom probe {name}: exit {proc.returncode}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            warnings.append(f"custom probe {name}: {exc}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra-probes-json", default="[]")
    args = parser.parse_args()
    warnings = []
    system = (dmi_records(dmidecode("system", warnings)) or [{}])[0]
    boards = dmi_records(dmidecode("baseboard", warnings))
    memory = [r for r in dmi_records(dmidecode("memory", warnings)) if useful(r.get("Serial Number"))]
    bios = (dmi_records(dmidecode("bios", warnings)) or [{}])[0]
    bmc = dmi_records(run(["ipmitool", "mc", "info"], warnings, "ipmitool mc info"))
    fru = dmi_records(run(["ipmitool", "fru", "print"], warnings, "ipmitool fru print"))
    try:
        probes = json.loads(args.extra_probes_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid --extra-probes-json: {exc}")
    data = {
        "schema_version": 1,
        "hostname": socket.getfqdn(),
        "short_hostname": socket.gethostname(),
        "machine": platform.machine(),
        "kernel": platform.release(),
        "os_release": os_release(),
        "system": system,
        "bios": bios,
        "baseboards": boards,
        "memory": memory,
        "network_interfaces": network(warnings),
        "bmc": bmc,
        "fru": fru,
        "custom_probes": extra_probes(probes, warnings),
        "warnings": warnings,
    }
    print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
