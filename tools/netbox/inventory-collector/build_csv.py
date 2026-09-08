#!/usr/bin/env python3
"""Convert collect_host.py JSON files into CSVs accepted by csv-import."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


FIELDS = {
    "Manufacturers": ["name", "slug"],
    "DeviceRoles": ["name", "slug", "color"],
    "DeviceTypes": ["manufacturer", "model", "slug", "u_height"],
    "Sites": ["name", "slug", "status"],
    "Devices": ["name", "device_type", "role", "site", "status", "serial", "description"],
    "Interfaces": ["device", "name", "type", "enabled", "description"],
    "MACAddresses": ["address", "device", "interface", "primary", "description"],
    "InventoryItems": ["device", "name", "manufacturer", "part_id", "serial", "parent", "role", "description"],
    "IPAddresses": ["address", "device", "interface", "status", "primary"],
}


def clean(value, fallback=""):
    if value is None:
        return fallback
    value = str(value).strip()
    if value.lower() in {"unknown", "not specified", "none", "no module installed"}:
        return fallback
    return value


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def add_item(rows, manufacturers, device, name, values, parent="", role="", description=""):
    manufacturer = clean(values.get("Manufacturer") or values.get("manufacturer"))
    if manufacturer:
        manufacturers.add(manufacturer)
    rows.append({"device": device, "name": name, "manufacturer": manufacturer,
                 "part_id": clean(values.get("Part Number") or values.get("part_id")),
                 "serial": clean(values.get("Serial Number") or values.get("serial")),
                 "parent": parent, "role": role, "description": description})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="directory containing per-host JSON")
    parser.add_argument("output", type=Path, help="directory to create CSV files in")
    parser.add_argument("--site", default="Prototype Lab")
    parser.add_argument("--role", default="Server")
    parser.add_argument("--primary-interface", default="")
    args = parser.parse_args()
    docs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.input.glob("*.json"))]
    if not docs:
        raise SystemExit(f"no JSON files found in {args.input}")
    rows = {name: [] for name in FIELDS}
    manufacturers = set()
    rows["Sites"].append({"name": args.site, "slug": slug(args.site), "status": "active"})
    rows["DeviceRoles"].append({"name": args.role, "slug": slug(args.role), "color": "9e9e9e"})
    device_types = set()
    warnings = []
    for doc in docs:
        device = clean(doc.get("short_hostname") or doc.get("hostname"), "unnamed-host")
        system = doc.get("system", {})
        manufacturer = clean(system.get("Manufacturer"), "Unknown")
        model = clean(system.get("Product Name"), "Unknown server")
        manufacturers.add(manufacturer)
        if (manufacturer, model) not in device_types:
            rows["DeviceTypes"].append({"manufacturer": manufacturer, "model": model,
                                        "slug": slug(f"{manufacturer}-{model}"), "u_height": ""})
            device_types.add((manufacturer, model))
        os_name = clean(doc.get("os_release", {}).get("PRETTY_NAME"))
        kernel = clean(doc.get("kernel"))
        rows["Devices"].append({"name": device, "device_type": model, "role": args.role,
                                "site": args.site, "status": "active",
                                "serial": clean(system.get("Serial Number")),
                                "description": "; ".join(filter(None, [os_name, f"kernel {kernel}" if kernel else ""]))})
        item_rows = rows["InventoryItems"]
        for index, board in enumerate(doc.get("baseboards", []), 1):
            add_item(item_rows, manufacturers, device, f"System board {index}", board,
                     role="System board", description=clean(board.get("Product Name")))
        for index, dimm in enumerate(doc.get("memory", []), 1):
            locator = clean(dimm.get("Locator"), f"DIMM {index}")
            desc = " ".join(filter(None, [clean(dimm.get("Size")), clean(dimm.get("Type")),
                                           clean(dimm.get("Speed"))]))
            add_item(item_rows, manufacturers, device, locator, dimm, role="Memory", description=desc)
        bios = doc.get("bios", {})
        if bios:
            add_item(item_rows, manufacturers, device, "System BIOS", bios, role="Firmware",
                     description=clean(bios.get("Version")))
        for index, bmc in enumerate(doc.get("bmc", []), 1):
            values = {"Manufacturer": bmc.get("Manufacturer Name"),
                      "Part Number": bmc.get("Device ID"), "Serial Number": ""}
            desc = "Firmware " + clean(bmc.get("Firmware Revision"))
            add_item(item_rows, manufacturers, device, f"BMC {index}", values, role="BMC", description=desc.strip())
        for index, fru in enumerate(doc.get("fru", []), 1):
            values = {"Manufacturer": fru.get("Product Manufacturer") or fru.get("Board Mfg"),
                      "Part Number": fru.get("Product Part Number") or fru.get("Board Part Number"),
                      "Serial Number": fru.get("Product Serial") or fru.get("Board Serial")}
            if any(clean(value) for value in values.values()):
                name = clean(fru.get("FRU Device Description"), f"BMC FRU {index}")
                add_item(item_rows, manufacturers, device, name, values, role="FRU")
        for iface in doc.get("network_interfaces", []):
            description = " ".join(filter(None, [clean(iface.get("driver")),
                                                   f"firmware {clean(iface.get('firmware'))}" if clean(iface.get("firmware")) else "",
                                                   clean(iface.get("bus_info"))]))
            rows["Interfaces"].append({"device": device, "name": iface["name"], "type": "other",
                                       "enabled": str(bool(iface.get("enabled"))).lower(),
                                       "description": description})
            if clean(iface.get("mac_address")):
                rows["MACAddresses"].append({"address": clean(iface.get("mac_address")),
                                              "device": device, "interface": iface["name"],
                                              "primary": "true", "description": "Collected from Linux"})
            pci = iface.get("pci", {})
            if pci:
                add_item(item_rows, manufacturers, device, f"{iface['name']} NIC", pci,
                         role="NIC", description=clean(pci.get("product_name") or pci.get("product")))
            for address in iface.get("addresses", []):
                rows["IPAddresses"].append({"address": address, "device": device,
                                            "interface": iface["name"], "status": "active",
                                            "primary": str(iface["name"] == args.primary_interface).lower()})
            module = iface.get("transceiver", {})
            if module:
                add_item(item_rows, manufacturers, device, f"{iface['name']} transceiver", module,
                         role="Transceiver", description=clean(module.get("identifier")))
        for probe in doc.get("custom_probes", []):
            # Vendor-specific output is retained verbatim for a later parser; a
            # placeholder item makes the unparsed FPGA/component visible now.
            role = clean(probe.get("category"), "Custom").upper()
            description = f"Unparsed custom probe; see raw JSON ({probe.get('command', '')})"
            add_item(item_rows, manufacturers, device, clean(probe.get("name"), "Custom probe"), {},
                     role=role, description=description)
        warnings.extend(f"{device}: {message}" for message in doc.get("warnings", []))
    rows["Manufacturers"] = [{"name": name, "slug": slug(name)} for name in sorted(manufacturers)]
    args.output.mkdir(parents=True, exist_ok=True)
    for name, fieldnames in FIELDS.items():
        with (args.output / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows[name])
    (args.output / "collection-warnings.txt").write_text("\n".join(warnings) + ("\n" if warnings else ""), encoding="utf-8")
    print(f"Wrote {len(docs)} host(s) to {args.output}; {len(warnings)} collection warning(s)")


if __name__ == "__main__":
    main()
