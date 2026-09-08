"""Reads XLSX workbooks or directories of object-type CSV files."""
from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

# Sheets are synced in this order -- later sheets reference objects created
# by earlier ones (e.g. Devices needs DeviceTypes/DeviceRoles/Sites/Racks
# to already exist). Any sheet not in this list is ignored; any sheet in
# this list that's missing from the workbook is simply skipped.
SHEET_ORDER = [
    "Manufacturers",
    "DeviceRoles",
    "DeviceTypes",
    "Sites",
    "Racks",
    "Devices",
    "Interfaces",
    "MACAddresses",
    "InventoryItems",
    "VLANs",
    "Prefixes",
    "IPAddresses",
]

REQUIRED_COLUMNS = {
    "Manufacturers": ["name"],
    "DeviceRoles": ["name"],
    "DeviceTypes": ["manufacturer", "model"],
    "Sites": ["name"],
    "Racks": ["name", "site"],
    "Devices": ["name", "device_type", "role", "site"],
    "Interfaces": ["device", "name"],
    "MACAddresses": ["address", "device", "interface"],
    "InventoryItems": ["device", "name"],
    "VLANs": ["vid", "name"],
    "Prefixes": ["prefix"],
    "IPAddresses": ["address"],
}


class WorkbookError(ValueError):
    pass


def load_workbook(path):
    """Returns {sheet_name: [row_dict, ...]} for every recognized sheet
    present in the workbook. Blank rows (no value in the sheet's first
    required column) are skipped."""
    wb = openpyxl.load_workbook(path, data_only=True)
    result = {}
    for sheet_name in SHEET_ORDER:
        if sheet_name not in wb.sheetnames:
            continue
        result[sheet_name] = _read_sheet(wb[sheet_name], sheet_name)
    return result


def load_inventory(path):
    """Load an XLSX workbook or a directory containing ``<Sheet>.csv`` files."""
    path = Path(path)
    if path.is_dir():
        result = {}
        for sheet_name in SHEET_ORDER:
            csv_path = path / f"{sheet_name}.csv"
            if csv_path.exists():
                result[sheet_name] = _read_csv(csv_path, sheet_name)
        return result
    if path.suffix.lower() == ".xlsx":
        return load_workbook(path)
    raise WorkbookError("inventory must be an .xlsx workbook or a directory of CSV files")


def _read_csv(path, sheet_name):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            return []
        reader.fieldnames = [field.strip() for field in reader.fieldnames]
        missing = [column for column in REQUIRED_COLUMNS[sheet_name] if column not in reader.fieldnames]
        if missing:
            raise WorkbookError(
                f"CSV {path.name!r} is missing required column(s): {', '.join(missing)}"
            )
        anchor = REQUIRED_COLUMNS[sheet_name][0]
        rows = []
        for raw in reader:
            row = {key: value.strip() for key, value in raw.items() if key}
            if not row.get(anchor):
                continue
            rows.append(row)
        return rows


def _read_sheet(ws, sheet_name):
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = [str(c).strip() if c is not None else "" for c in next(rows_iter)]
    except StopIteration:
        return []

    missing = [c for c in REQUIRED_COLUMNS[sheet_name] if c not in header]
    if missing:
        raise WorkbookError(
            f"sheet {sheet_name!r} is missing required column(s): {', '.join(missing)}"
        )

    anchor = REQUIRED_COLUMNS[sheet_name][0]
    rows = []
    for raw in rows_iter:
        row = {k: v for k, v in zip(header, raw) if k}
        if row.get(anchor) in (None, ""):
            continue  # blank row
        rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
    return rows
