"""Creates NetBox objects (via pynetbox) from parsed workbook rows.

Idempotent by design: every object is looked up by its natural key first
and only created if missing. Existing objects are never modified -- safe
to re-run against a workbook that's grown over time, and safe to hand-edit
objects in NetBox afterward without a later import clobbering them.
"""
from __future__ import annotations

import re

from .workbook import SHEET_ORDER

# NetBox 4.0+ calls a device's role field "role" (it was "device_role" in
# older versions). Flip this if you're running NetBox < 4.0.
DEVICE_ROLE_FIELD = "role"


def slugify(value):
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


class SyncStats:
    def __init__(self):
        self.created = 0
        self.existing = 0
        self.errors = []

    def note(self, status):
        if status == "created":
            self.created += 1
        elif status == "existing":
            self.existing += 1

    def __str__(self):
        lines = [f"created={self.created} existing={self.existing} errors={len(self.errors)}"]
        lines += [f"  ERROR: {e}" for e in self.errors]
        return "\n".join(lines)


def _get_or_create(endpoint, filter_kwargs, create_kwargs, dry_run, stats):
    obj = endpoint.get(**filter_kwargs)
    if obj:
        stats.note("existing")
        return obj
    if dry_run:
        stats.note("created")
        return None
    obj = endpoint.create(**create_kwargs)
    stats.note("created")
    return obj


def sync_manufacturers(nb, rows, dry_run, stats):
    cache = {}
    for row in rows:
        name = row["name"]
        slug = row.get("slug") or slugify(name)
        try:
            obj = _get_or_create(
                nb.dcim.manufacturers, {"slug": slug}, {"name": name, "slug": slug}, dry_run, stats
            )
        except Exception as exc:
            stats.errors.append(f"Manufacturers row {row}: {exc}")
            continue
        cache[name] = obj
    return cache


def sync_device_roles(nb, rows, dry_run, stats):
    cache = {}
    for row in rows:
        name = row["name"]
        slug = row.get("slug") or slugify(name)
        color = row.get("color") or "9e9e9e"
        try:
            obj = _get_or_create(
                nb.dcim.device_roles,
                {"slug": slug},
                {"name": name, "slug": slug, "color": color},
                dry_run,
                stats,
            )
        except Exception as exc:
            stats.errors.append(f"DeviceRoles row {row}: {exc}")
            continue
        cache[name] = obj
    return cache


def sync_device_types(nb, rows, refs, dry_run, stats):
    cache = {}
    for row in rows:
        model = row["model"]
        manufacturer_name = row["manufacturer"]
        manufacturer = refs["Manufacturers"].get(manufacturer_name)
        if manufacturer is None and not dry_run:
            stats.errors.append(f"DeviceTypes row {row}: unknown manufacturer {manufacturer_name!r}")
            continue
        slug = row.get("slug") or slugify(f"{manufacturer_name}-{model}")
        create = {
            "manufacturer": manufacturer.id if manufacturer else None,
            "model": model,
            "slug": slug,
        }
        if row.get("u_height") not in (None, ""):
            create["u_height"] = row["u_height"]
        try:
            obj = _get_or_create(nb.dcim.device_types, {"slug": slug}, create, dry_run, stats)
        except Exception as exc:
            stats.errors.append(f"DeviceTypes row {row}: {exc}")
            continue
        cache[model] = obj
    return cache


def sync_sites(nb, rows, dry_run, stats):
    cache = {}
    for row in rows:
        name = row["name"]
        slug = row.get("slug") or slugify(name)
        status = row.get("status") or "active"
        try:
            obj = _get_or_create(
                nb.dcim.sites, {"slug": slug}, {"name": name, "slug": slug, "status": status}, dry_run, stats
            )
        except Exception as exc:
            stats.errors.append(f"Sites row {row}: {exc}")
            continue
        cache[name] = obj
    return cache


def sync_racks(nb, rows, refs, dry_run, stats):
    cache = {}
    for row in rows:
        name = row["name"]
        site_name = row["site"]
        site = refs["Sites"].get(site_name)
        if site is None and not dry_run:
            stats.errors.append(f"Racks row {row}: unknown site {site_name!r}")
            continue
        site_id = site.id if site else None
        create = {"name": name, "site": site_id, "status": row.get("status") or "active"}
        if row.get("u_height") not in (None, ""):
            create["u_height"] = row["u_height"]
        try:
            obj = _get_or_create(
                nb.dcim.racks, {"name": name, "site_id": site_id}, create, dry_run, stats
            )
        except Exception as exc:
            stats.errors.append(f"Racks row {row}: {exc}")
            continue
        cache[name] = obj
    return cache


def sync_devices(nb, rows, refs, dry_run, stats):
    cache = {}
    for row in rows:
        name = row["name"]
        device_type = refs["DeviceTypes"].get(row["device_type"])
        role = refs["DeviceRoles"].get(row["role"])
        site = refs["Sites"].get(row["site"])
        missing = [
            label
            for label, val in [("device_type", device_type), ("role", role), ("site", site)]
            if val is None
        ]
        if missing and not dry_run:
            stats.errors.append(f"Devices row {row}: unknown {', '.join(missing)}")
            continue
        site_id = site.id if site else None
        create = {
            "name": name,
            "device_type": device_type.id if device_type else None,
            DEVICE_ROLE_FIELD: role.id if role else None,
            "site": site_id,
            "status": row.get("status") or "active",
        }
        rack_name = row.get("rack")
        if rack_name:
            rack = refs["Racks"].get(rack_name)
            if rack is None and not dry_run:
                stats.errors.append(f"Devices row {row}: unknown rack {rack_name!r}")
                continue
            create["rack"] = rack.id if rack else None
            if row.get("position") not in (None, ""):
                create["position"] = row["position"]
            if row.get("face"):
                create["face"] = row["face"]
        if row.get("serial"):
            create["serial"] = row["serial"]
        try:
            obj = _get_or_create(
                nb.dcim.devices, {"name": name, "site_id": site_id}, create, dry_run, stats
            )
        except Exception as exc:
            stats.errors.append(f"Devices row {row}: {exc}")
            continue
        cache[name] = obj
    return cache


def sync_vlans(nb, rows, refs, dry_run, stats):
    cache = {}
    for row in rows:
        vid = row["vid"]
        name = row["name"]
        site = refs["Sites"].get(row.get("site")) if row.get("site") else None
        filter_kwargs = {"vid": vid}
        create = {"vid": vid, "name": name, "status": row.get("status") or "active"}
        if site:
            filter_kwargs["site_id"] = site.id
            create["site"] = site.id
        try:
            obj = _get_or_create(nb.ipam.vlans, filter_kwargs, create, dry_run, stats)
        except Exception as exc:
            stats.errors.append(f"VLANs row {row}: {exc}")
            continue
        cache[vid] = obj
    return cache


def sync_prefixes(nb, rows, refs, dry_run, stats):
    cache = {}
    for row in rows:
        prefix = row["prefix"]
        site = refs["Sites"].get(row.get("site")) if row.get("site") else None
        create = {"prefix": prefix, "status": row.get("status") or "active"}
        if site:
            create["site"] = site.id
        if row.get("description"):
            create["description"] = row["description"]
        try:
            obj = _get_or_create(nb.ipam.prefixes, {"prefix": prefix}, create, dry_run, stats)
        except Exception as exc:
            stats.errors.append(f"Prefixes row {row}: {exc}")
            continue
        cache[prefix] = obj
    return cache


def _get_or_create_interface(nb, device, iface_name, dry_run, stats):
    return _get_or_create(
        nb.dcim.interfaces,
        {"device_id": device.id, "name": iface_name},
        {"device": device.id, "name": iface_name, "type": "other"},
        dry_run,
        stats,
    )


def sync_ip_addresses(nb, rows, refs, dry_run, stats):
    for row in rows:
        address = row["address"]
        create = {"status": row.get("status") or "active"}
        device = None
        try:
            device_name = row.get("device")
            if device_name:
                device = refs["Devices"].get(device_name)
                if device is None and not dry_run:
                    stats.errors.append(f"IPAddresses row {row}: unknown device {device_name!r}")
                    continue
                if device:
                    iface_name = row.get("interface") or "eth0"
                    iface = _get_or_create_interface(nb, device, iface_name, dry_run, stats)
                    if iface:
                        create["assigned_object_type"] = "dcim.interface"
                        create["assigned_object_id"] = iface.id
            create["address"] = address
            obj = _get_or_create(nb.ipam.ip_addresses, {"address": address}, create, dry_run, stats)
        except Exception as exc:
            stats.errors.append(f"IPAddresses row {row}: {exc}")
            continue
        wants_primary = str(row.get("primary", "")).strip().lower() in ("true", "yes", "1")
        if wants_primary and device and obj and not dry_run:
            device.primary_ip4 = obj.id
            device.save()


# sheet name -> (sync function, sheets it needs already-synced refs for)
SYNC_FUNCS = {
    "Manufacturers": (sync_manufacturers, []),
    "DeviceRoles": (sync_device_roles, []),
    "DeviceTypes": (sync_device_types, ["Manufacturers"]),
    "Sites": (sync_sites, []),
    "Racks": (sync_racks, ["Sites"]),
    "Devices": (sync_devices, ["DeviceTypes", "DeviceRoles", "Sites", "Racks"]),
    "VLANs": (sync_vlans, ["Sites"]),
    "Prefixes": (sync_prefixes, ["Sites"]),
    "IPAddresses": (sync_ip_addresses, ["Devices"]),
}


def run_sync(nb, sheets, dry_run=False):
    """sheets: {sheet_name: [row_dict, ...]} from workbook.load_workbook.
    Returns a SyncStats summarizing created/existing/errors."""
    stats = SyncStats()
    refs = {}
    for sheet_name in SHEET_ORDER:
        rows = sheets.get(sheet_name)
        if not rows:
            continue
        func, deps = SYNC_FUNCS[sheet_name]
        if deps:
            refs[sheet_name] = func(nb, rows, refs, dry_run, stats)
        else:
            refs[sheet_name] = func(nb, rows, dry_run, stats)
    return stats
